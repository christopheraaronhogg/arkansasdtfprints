import json
import threading
import time
import queue
import logging
from datetime import datetime, timedelta
from flask import current_app
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail as SGMail

logger = logging.getLogger(__name__)

# Global queue for email jobs
email_queue = queue.Queue()
# Flag to control the worker thread
_worker_running = False

def enqueue_email(email_type, data):
    """Add an email job to the queue"""
    email_queue.put({
        'type': email_type,
        'data': data,
        'attempts': 0,
        'created_at': time.time()
    })
    logger.info(f"Email job of type {email_type} enqueued")
    start_worker_if_needed()

def start_worker_if_needed():
    """Start the worker thread if it's not already running"""
    global _worker_running
    
    if not _worker_running:
        _worker_running = True
        thread = threading.Thread(target=process_email_queue)
        thread.daemon = True
        thread.start()
        logger.info("Started email worker thread")

def process_email_queue():
    """Worker function to process the email queue"""
    global _worker_running
    
    logger.info("Email queue worker started")
    try:
        while not email_queue.empty():
            try:
                job = email_queue.get(block=False)
                process_email_job(job)
                email_queue.task_done()
            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"Error processing email job: {str(e)}")
    finally:
        _worker_running = False
        logger.info("Email queue worker stopped")

def process_email_job(job):
    """Process a single email job"""
    from app import app, db, EmailJob  # Import here to avoid circular imports
    
    email_type = job['type']
    data = job['data']
    attempts = job['attempts']
    
    # Max retry limit
    MAX_ATTEMPTS = 3
    
    if attempts >= MAX_ATTEMPTS:
        logger.error(f"Email job of type {email_type} failed after {attempts} attempts: {data}")
        # Update email job status in database
        with app.app_context():
            email_job = EmailJob.query.get(data.get('email_job_id'))
            if email_job:
                email_job.status = 'failed'
                email_job.error_message = f"Failed after {attempts} attempts"
                email_job.updated_at = datetime.utcnow()
                db.session.commit()
        return
    
    logger.info(f"Processing email job of type {email_type}, attempt {attempts+1}")
    
    try:
        with app.app_context():
            # Update attempt count in database
            email_job = EmailJob.query.get(data.get('email_job_id'))
            if email_job:
                email_job.attempts += 1
                email_job.status = 'processing'
                email_job.updated_at = datetime.utcnow()
                db.session.commit()
            
            if email_type == 'customer_order_confirmation':
                success = send_customer_email(data)
            elif email_type == 'production_order_notification':
                success = send_production_email(data)
            else:
                logger.error(f"Unknown email type: {email_type}")
                success = False
                
            # Update database with result
            if email_job:
                if success:
                    email_job.status = 'sent'
                    email_job.updated_at = datetime.utcnow()
                    db.session.commit()
                    logger.info(f"Email job {email_job.id} marked as sent")
    except Exception as e:
        logger.error(f"Failed to process {email_type} email: {str(e)}")
        success = False
        
    # If not successful, increment attempt count and re-queue if under max attempts
    if not success:
        job['attempts'] += 1
        if job['attempts'] < MAX_ATTEMPTS:
            email_queue.put(job)
            logger.info(f"Requeued {email_type} email for retry, attempt {job['attempts']}")

def send_customer_email(data):
    """Send customer order confirmation email"""
    from flask import render_template
    from app import app, Order
    
    order_id = data.get('order_id')
    order = Order.query.get(order_id)
    
    if not order:
        logger.error(f"Cannot send customer email: Order {order_id} not found")
        return False
    
    customer_email = SGMail(
        from_email=('info@appareldecorating.net', 'DTF Printing'),
        to_emails=order.email,
        subject=f'DTF Printing Order Confirmation - {order.order_number}',
        html_content=render_template('emails/customer_order_confirmation.html', order=order)
    )
    
    return send_via_sendgrid(customer_email, f"customer email for order {order.order_number}")

def send_production_email(data):
    """Send production team notification email"""
    from flask import render_template
    from app import app, Order
    
    order_id = data.get('order_id')
    order = Order.query.get(order_id)
    
    if not order:
        logger.error(f"Cannot send production email: Order {order_id} not found")
        return False
    
    production_email = SGMail(
        from_email=('info@appareldecorating.net', 'DTF Printing'),
        to_emails=app.config['PRODUCTION_TEAM_EMAIL'],
        subject=f'New DTF Printing Order - {order.order_number}',
        html_content=render_template('emails/production_order_notification.html', order=order)
    )
    
    return send_via_sendgrid(production_email, f"production team email for order {order.order_number}")

def send_via_sendgrid(email, description):
    """Send an email via SendGrid API with proper error handling"""
    from app import app
    
    api_key = app.config['SENDGRID_API_KEY']
    if not api_key:
        logger.error(f"Cannot send {description}: SendGrid API key not configured")
        return False
    
    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(email)
        
        if response.status_code not in [200, 201, 202]:
            logger.error(f"Failed to send {description}. Status code: {response.status_code}")
            logger.error(f"Response body: {response.body.decode('utf-8') if hasattr(response, 'body') else 'No body'}")
            return False
        
        logger.info(f"Successfully sent {description}")
        return True
        
    except Exception as e:
        logger.error(f"SendGrid API error for {description}: {str(e)}")
        if hasattr(e, 'body'):
            try:
                error_body = e.body.decode('utf-8')
                logger.error(f"SendGrid API error details: {error_body}")
            except:
                logger.error("Could not decode error body")
        return False

def check_for_stuck_emails():
    """Check for emails that have been stuck in the queue for too long"""
    from app import app, db, EmailJob
    
    with app.app_context():
        # Find jobs that are still pending or processing and were created more than 15 minutes ago
        cutoff_time = datetime.utcnow() - timedelta(minutes=15)
        stuck_jobs = EmailJob.query.filter(
            EmailJob.status.in_(['pending', 'processing']),
            EmailJob.created_at < cutoff_time
        ).all()
        
        if stuck_jobs:
            logger.warning(f"Found {len(stuck_jobs)} stuck email jobs.")
            
            # Try to re-process them
            for job in stuck_jobs:
                logger.info(f"Re-enqueueing stuck job {job.id} of type {job.email_type}")
                enqueue_email(job.email_type, {
                    'order_id': job.order_id,
                    'email_job_id': job.id
                })