import os
import json
import time
import uuid
import logging
import threading
from datetime import datetime, timedelta
from replit import db
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail as SGMail

# Configure logging
logger = logging.getLogger(__name__)

# Prefix for all email-related keys in Replit DB
EMAIL_KEY_PREFIX = "email_task:"
EMAIL_QUEUE_KEY = "email_queue_list"

# Store of functions that can be called by name
registered_functions = {}

# Background worker thread
worker_thread = None
worker_running = False

class EmailTask:
    """Represents an email task to be queued and processed"""
    
    def __init__(self, to_email, subject, html_content, from_email=None, 
                 template_id=None, dynamic_template_data=None, task_type="customer"):
        """
        Initialize an email task
        
        Args:
            to_email: Recipient email (string or list)
            subject: Email subject
            html_content: HTML content of the email
            from_email: Sender email tuple (email, name) or default if None
            template_id: SendGrid template ID if using templates
            dynamic_template_data: Data for SendGrid templates
            task_type: Type of email (customer, production, etc.)
        """
        self.id = str(uuid.uuid4())
        self.to_email = to_email
        self.subject = subject
        self.html_content = html_content
        self.from_email = from_email or ('info@appareldecorating.net', 'DTF Printing')
        self.template_id = template_id
        self.dynamic_template_data = dynamic_template_data
        self.task_type = task_type
        self.created_at = datetime.utcnow().isoformat()
        self.retry_count = 0
        self.max_retries = 3
        self.last_attempt = None
        self.next_attempt = datetime.utcnow().isoformat()
        self.status = "pending"
        self.error = None
        
    def to_dict(self):
        """Convert task to dictionary for storage"""
        return {
            "id": self.id,
            "to_email": self.to_email,
            "subject": self.subject,
            "html_content": self.html_content,
            "from_email": self.from_email,
            "template_id": self.template_id,
            "dynamic_template_data": self.dynamic_template_data,
            "task_type": self.task_type,
            "created_at": self.created_at,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "last_attempt": self.last_attempt,
            "next_attempt": self.next_attempt,
            "status": self.status,
            "error": self.error
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create task from dictionary storage"""
        task = cls(
            to_email=data["to_email"],
            subject=data["subject"],
            html_content=data["html_content"],
            from_email=data["from_email"],
            template_id=data.get("template_id"),
            dynamic_template_data=data.get("dynamic_template_data"),
            task_type=data["task_type"]
        )
        task.id = data["id"]
        task.created_at = data["created_at"]
        task.retry_count = data["retry_count"]
        task.max_retries = data["max_retries"]
        task.last_attempt = data["last_attempt"]
        task.next_attempt = data["next_attempt"]
        task.status = data["status"]
        task.error = data["error"]
        return task


def enqueue_email(to_email, subject, html_content, from_email=None, 
                template_id=None, dynamic_template_data=None, task_type="customer"):
    """
    Add an email to the queue for sending
    
    Args:
        to_email: Recipient email (string or list)
        subject: Email subject
        html_content: HTML content of the email
        from_email: Sender email tuple (email, name) or default if None
        template_id: SendGrid template ID if using templates
        dynamic_template_data: Data for SendGrid templates
        task_type: Type of email (customer, production, etc.)
        
    Returns:
        task_id: ID of the queued task
    """
    try:
        # Create new task
        task = EmailTask(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            from_email=from_email,
            template_id=template_id,
            dynamic_template_data=dynamic_template_data,
            task_type=task_type
        )
        
        # Store task in DB
        task_key = f"{EMAIL_KEY_PREFIX}{task.id}"
        db[task_key] = json.dumps(task.to_dict())
        
        # Add task ID to queue list
        queue_list = json.loads(db.get(EMAIL_QUEUE_KEY, "[]"))
        queue_list.append(task.id)
        db[EMAIL_QUEUE_KEY] = json.dumps(queue_list)
        
        logger.info(f"Enqueued email task {task.id} to {to_email}, subject: {subject}")
        
        # Ensure worker is running
        ensure_worker_running()
        
        return task.id
        
    except Exception as e:
        logger.error(f"Failed to enqueue email: {str(e)}")
        # Try to send immediately as fallback
        try:
            logger.warning("Attempting to send email immediately as fallback")
            send_email_with_sendgrid(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                from_email=from_email,
                template_id=template_id,
                dynamic_template_data=dynamic_template_data
            )
            return "direct_send"
        except Exception as direct_e:
            logger.error(f"Direct email send failed: {str(direct_e)}")
            return None


def send_email_with_sendgrid(to_email, subject, html_content, from_email=None, 
                           template_id=None, dynamic_template_data=None):
    """
    Send an email using SendGrid API
    
    Args:
        to_email: Recipient email (string or list)
        subject: Email subject
        html_content: HTML content of the email
        from_email: Sender email tuple (email, name) or default if None
        template_id: SendGrid template ID if using templates
        dynamic_template_data: Data for SendGrid templates
        
    Returns:
        success: Boolean indicating if send was successful
    """
    try:
        # Create SendGrid mail object
        message = SGMail(
            from_email=from_email or ('info@appareldecorating.net', 'DTF Printing'),
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        
        # Add template if provided
        if template_id:
            message.template_id = template_id
            message.dynamic_template_data = dynamic_template_data or {}
        
        # Get API key from environment
        api_key = os.environ.get('SENDGRID_API_KEY')
        if not api_key:
            raise ValueError("SENDGRID_API_KEY environment variable is not set")
            
        # Initialize client and send
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        
        # Check response
        if response.status_code not in [200, 201, 202]:
            logger.error(f"SendGrid API error - Status code: {response.status_code}")
            logger.error(f"Response body: {response.body.decode('utf-8') if hasattr(response, 'body') else 'No body'}")
            return False
            
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"SendGrid API error: {str(e)}")
        if hasattr(e, 'body'):
            try:
                error_body = e.body.decode('utf-8')
                logger.error(f"SendGrid API error details: {error_body}")
            except:
                logger.error("Could not decode error body")
        return False


def process_email_queue():
    """
    Process emails in the queue
    
    This function will:
    1. Get all emails in the queue
    2. Process emails that are due for sending
    3. Handle retries and failures
    """
    try:
        # Get queue list
        queue_list = json.loads(db.get(EMAIL_QUEUE_KEY, "[]"))
        
        if not queue_list:
            logger.debug("Email queue is empty")
            return
            
        now = datetime.utcnow()
        processed_ids = []
        
        # Process each task
        for task_id in queue_list:
            try:
                # Get task data
                task_key = f"{EMAIL_KEY_PREFIX}{task_id}"
                task_data = db.get(task_key)
                
                if not task_data:
                    # Task no longer exists, remove from queue
                    processed_ids.append(task_id)
                    continue
                    
                # Parse task
                task_dict = json.loads(task_data)
                task = EmailTask.from_dict(task_dict)
                
                # Check if task is due for processing
                next_attempt = datetime.fromisoformat(task.next_attempt)
                
                if next_attempt <= now and task.status in ["pending", "retry"]:
                    # Task is due for processing
                    logger.info(f"Processing email task {task.id} (attempt {task.retry_count + 1}/{task.max_retries})")
                    
                    # Update task status
                    task.status = "processing"
                    task.last_attempt = now.isoformat()
                    db[task_key] = json.dumps(task.to_dict())
                    
                    # Send email
                    success = send_email_with_sendgrid(
                        to_email=task.to_email,
                        subject=task.subject,
                        html_content=task.html_content,
                        from_email=task.from_email,
                        template_id=task.template_id,
                        dynamic_template_data=task.dynamic_template_data
                    )
                    
                    # Update task based on result
                    if success:
                        # Email sent successfully
                        task.status = "completed"
                        processed_ids.append(task_id)
                        logger.info(f"Email task {task.id} completed successfully")
                    else:
                        # Email failed, schedule retry if attempts remain
                        task.retry_count += 1
                        
                        if task.retry_count >= task.max_retries:
                            # Max retries reached
                            task.status = "failed"
                            task.error = "Max retry attempts reached"
                            processed_ids.append(task_id)
                            logger.error(f"Email task {task.id} failed after {task.max_retries} attempts")
                        else:
                            # Schedule retry with exponential backoff
                            backoff_seconds = 60 * (2 ** task.retry_count)  # 2, 4, 8 minutes
                            retry_time = now + timedelta(seconds=backoff_seconds)
                            task.next_attempt = retry_time.isoformat()
                            task.status = "retry"
                            logger.info(f"Email task {task.id} scheduled for retry in {backoff_seconds} seconds")
                    
                    # Save updated task
                    db[task_key] = json.dumps(task.to_dict())
                
                elif task.status in ["completed", "failed"]:
                    # Task is completed or failed, remove from queue
                    processed_ids.append(task_id)
                    
            except Exception as e:
                logger.error(f"Error processing email task {task_id}: {str(e)}")
                # Remove task from queue to prevent blocking the queue
                processed_ids.append(task_id)
                
                # Try to update task status if possible
                try:
                    task_key = f"{EMAIL_KEY_PREFIX}{task_id}"
                    task_data = db.get(task_key)
                    if task_data:
                        task_dict = json.loads(task_data)
                        task_dict["status"] = "error"
                        task_dict["error"] = str(e)
                        db[task_key] = json.dumps(task_dict)
                except:
                    pass
        
        # Remove processed tasks from queue
        if processed_ids:
            new_queue = [task_id for task_id in queue_list if task_id not in processed_ids]
            db[EMAIL_QUEUE_KEY] = json.dumps(new_queue)
            
    except Exception as e:
        logger.error(f"Error in process_email_queue: {str(e)}")


def worker_loop():
    """Background worker loop that processes the email queue"""
    global worker_running
    
    try:
        while worker_running:
            try:
                # Process queue
                process_email_queue()
            except Exception as e:
                logger.error(f"Error in worker loop: {str(e)}")
                
            # Sleep for a bit before checking again
            time.sleep(30)  # Check every 30 seconds
    except:
        pass
    
    logger.info("Email queue worker stopped")


def ensure_worker_running():
    """Ensure the background worker is running"""
    global worker_thread, worker_running
    
    if worker_thread is None or not worker_thread.is_alive():
        logger.info("Starting email queue worker thread")
        worker_running = True
        worker_thread = threading.Thread(target=worker_loop, daemon=True)
        worker_thread.start()


def stop_worker():
    """Stop the background worker"""
    global worker_running
    worker_running = False
    

def get_queue_stats():
    """Get statistics about the email queue"""
    try:
        # Get queue list
        queue_list = json.loads(db.get(EMAIL_QUEUE_KEY, "[]"))
        
        # Count tasks by status
        status_counts = {
            "pending": 0,
            "processing": 0,
            "retry": 0,
            "completed": 0,
            "failed": 0,
            "error": 0
        }
        
        # Process each task
        for task_id in queue_list:
            try:
                # Get task data
                task_key = f"{EMAIL_KEY_PREFIX}{task_id}"
                task_data = db.get(task_key)
                
                if task_data:
                    task_dict = json.loads(task_data)
                    status = task_dict.get("status", "unknown")
                    if status in status_counts:
                        status_counts[status] += 1
                    else:
                        status_counts["unknown"] = status_counts.get("unknown", 0) + 1
            except:
                pass
                
        return {
            "queue_length": len(queue_list),
            "status_counts": status_counts
        }
        
    except Exception as e:
        logger.error(f"Error getting queue stats: {str(e)}")
        return {
            "queue_length": 0,
            "status_counts": {},
            "error": str(e)
        }


# Start the worker thread when the module is imported
ensure_worker_running()