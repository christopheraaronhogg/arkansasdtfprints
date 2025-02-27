"""
Email Worker - A simple background worker for sending emails without Redis.
Provides a lightweight queue system for email delivery with persistence and retry logic.
"""

import os
import time
import json
import logging
import threading
import queue
import pickle
from datetime import datetime, timedelta
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail as SGMail

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Email queue
email_queue = queue.Queue()
QUEUE_PERSISTENCE_FILE = '/tmp/email_queue.pickle'
FAILED_EMAILS_FILE = '/tmp/failed_emails.pickle'

# Track if worker is running
worker_running = False
worker_thread = None

def save_queue_to_disk():
    """Save current queue to disk for persistence"""
    try:
        # Get all items from queue without removing them
        items = list(email_queue.queue)
        if items:
            with open(QUEUE_PERSISTENCE_FILE, 'wb') as f:
                pickle.dump(items, f)
            logger.info(f"Saved {len(items)} emails to persistent storage")
    except Exception as e:
        logger.error(f"Error saving queue to disk: {e}")

def load_queue_from_disk():
    """Load queued emails from disk on startup"""
    if os.path.exists(QUEUE_PERSISTENCE_FILE):
        try:
            with open(QUEUE_PERSISTENCE_FILE, 'rb') as f:
                items = pickle.load(f)
                for item in items:
                    email_queue.put(item)
            logger.info(f"Loaded {len(items)} emails from persistent storage")
            # Remove the file after successful loading
            os.remove(QUEUE_PERSISTENCE_FILE)
        except Exception as e:
            logger.error(f"Error loading queue from disk: {e}")

def save_failed_email(email_data, error):
    """Save failed email for later analysis"""
    try:
        failed = {}
        if os.path.exists(FAILED_EMAILS_FILE):
            with open(FAILED_EMAILS_FILE, 'rb') as f:
                failed = pickle.load(f)
        
        # Add timestamp and error info
        email_record = {
            'data': email_data,
            'error': str(error),
            'timestamp': datetime.utcnow().isoformat(),
            'attempts': email_data.get('_attempts', 0)
        }
        
        # Use order number or unique id as key
        key = email_data.get('metadata', {}).get('order_number', str(time.time()))
        failed[key] = email_record
        
        with open(FAILED_EMAILS_FILE, 'wb') as f:
            pickle.dump(failed, f)
            
        logger.warning(f"Saved failed email for order {key} to disk")
    except Exception as e:
        logger.error(f"Error saving failed email: {e}")

def send_email(email_data):
    """
    Send an email via SendGrid with retry logic
    
    Args:
        email_data (dict): Contains email details:
            - from_email (tuple): (email, name)
            - to_emails: Email address or list of addresses
            - subject: Email subject
            - html_content: HTML content of the email
            - metadata: Additional metadata for logging
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    # Track attempts for this send operation
    attempt = email_data.get('_attempts', 0) + 1
    email_data['_attempts'] = attempt
    
    if attempt > 5:  # Maximum retry limit
        logger.error(f"Exceeded maximum retries for email: {email_data.get('metadata', {}).get('order_number', 'unknown')}")
        save_failed_email(email_data, "Exceeded maximum retries")
        return False
    
    logger.info(f"Processing email: {email_data.get('metadata', {}).get('type', 'unknown')} for "
                f"{email_data.get('metadata', {}).get('order_number', 'unknown')} (attempt {attempt}/5)")
    
    try:
        # Create SendGrid message
        message = SGMail(
            from_email=email_data['from_email'],
            to_emails=email_data['to_emails'],
            subject=email_data['subject'],
            html_content=email_data['html_content']
        )
        
        # Get SendGrid API key
        sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
        if not sendgrid_api_key:
            logger.error("SENDGRID_API_KEY not set in environment")
            raise ValueError("SendGrid API key not configured")
        
        sg = SendGridAPIClient(sendgrid_api_key)
        
        try:
            response = sg.send(message)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent successfully: {email_data.get('metadata', {}).get('type', 'unknown')} for "
                           f"{email_data.get('metadata', {}).get('order_number', 'unknown')}")
                return True
            else:
                logger.error(f"SendGrid error: HTTP {response.status_code}")
                if hasattr(response, 'body'):
                    try:
                        logger.error(f"Error details: {response.body.decode('utf-8')}")
                    except:
                        logger.error("Could not decode error response body")
                
                # Don't retry on client errors (4xx) except rate limiting
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    save_failed_email(email_data, f"HTTP error {response.status_code}")
                    return False
                
                # Re-queue for retry if we have a server error or rate limit
                # Add exponential backoff by using attempt number
                email_queue.put(email_data)
                logger.info(f"Requeued email for retry (attempt {attempt}/5)")
                return False
                
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            # Re-queue for retry
            email_queue.put(email_data)
            logger.info(f"Requeued email for retry (attempt {attempt}/5)")
            return False
            
    except Exception as e:
        logger.error(f"Error preparing email: {str(e)}")
        save_failed_email(email_data, str(e))
        return False

def email_worker():
    """Background thread function to process emails"""
    logger.info("Starting email worker thread")
    
    while True:
        try:
            # Process one email from the queue (blocking with timeout)
            try:
                email_data = email_queue.get(timeout=5)  # 5 second timeout
                send_email(email_data)
                email_queue.task_done()
                
                # Save the queue periodically
                if not email_queue.empty() and email_queue.qsize() % 5 == 0:
                    save_queue_to_disk()
                    
            except queue.Empty:
                # Queue is empty, nothing to process
                pass
                
            # Check for new items
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Error in email worker: {str(e)}")
            # Sleep longer after an error to prevent rapid retries
            time.sleep(5)
            
        # Save pending emails before exit
        if threading.current_thread().daemon and not email_queue.empty():
            save_queue_to_disk()

def queue_email(email_data):
    """
    Queue an email to be sent in the background
    
    Args:
        email_data (dict): Email data dictionary
        
    Returns:
        bool: True if queued successfully, False otherwise
    """
    try:
        # Add timestamp and initial attempt count
        if '_attempts' not in email_data:
            email_data['_attempts'] = 0
        email_data['_queued_at'] = datetime.utcnow().isoformat()
        
        # Add to queue
        email_queue.put(email_data)
        logger.info(f"Queued email for {email_data.get('metadata', {}).get('order_number', 'unknown')}")
        
        # Ensure worker is running
        ensure_worker_running()
        
        return True
    except Exception as e:
        logger.error(f"Failed to queue email: {str(e)}")
        return False

def ensure_worker_running():
    """Check if worker is running and start if needed"""
    global worker_running, worker_thread
    
    if not worker_running or (worker_thread and not worker_thread.is_alive()):
        worker_thread = threading.Thread(target=email_worker, daemon=True)
        worker_thread.start()
        worker_running = True
        logger.info("Started new email worker thread")

def start_worker():
    """Initialize and start the email worker"""
    # Load any persisted emails first
    load_queue_from_disk()
    
    # Start the worker thread
    ensure_worker_running()
    
    # Start a second thread to periodically save the queue
    def periodic_save():
        while True:
            time.sleep(60)  # Save every minute
            if not email_queue.empty():
                save_queue_to_disk()
    
    save_thread = threading.Thread(target=periodic_save, daemon=True)
    save_thread.start()
    
    logger.info("Email worker system initialized")
