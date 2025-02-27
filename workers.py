import os
import logging
import time
from datetime import datetime
from rq import Queue
from redis import Redis
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail as SGMail

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Redis connection
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
redis_conn = Redis.from_url(redis_url)
email_queue = Queue('emails', connection=redis_conn, default_timeout=300)

def send_email_task(email_data):
    """
    Background task for sending emails via SendGrid

    Args:
        email_data (dict): Contains email details:
            - from_email (tuple): (email, name)
            - to_emails: Email address or list of addresses
            - subject: Email subject
            - html_content: HTML content of the email
            - metadata: Additional metadata for logging (order_number, etc.)
    """
    logger.info(f"Processing email job: {email_data.get('metadata', {}).get('type', 'unknown')} for {email_data.get('metadata', {}).get('order_number', 'unknown')}")

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

        # Send with retry logic
        for attempt in range(5):  # 5 attempts
            try:
                logger.info(f"Sending email attempt {attempt+1}/5")
                response = sg.send(message)

                if response.status_code in [200, 201, 202]:
                    logger.info(f"Email sent successfully: {email_data.get('metadata', {}).get('type', 'unknown')} for {email_data.get('metadata', {}).get('order_number', 'unknown')}")
                    # Record success in email_logs table if implemented
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
                        return False

            except Exception as e:
                logger.error(f"Send attempt {attempt+1} failed: {str(e)}")

            # Exponential backoff with jitter
            if attempt < 4:  # Don't sleep after the last attempt
                sleep_time = min(60, (2 ** attempt) + (attempt * 0.1))
                logger.info(f"Retrying in {sleep_time:.1f} seconds")
                time.sleep(sleep_time)

        # If we get here, all attempts failed
        logger.error(f"Failed to send email after 5 attempts for {email_data.get('metadata', {}).get('order_number', 'unknown')}")
        return False

    except Exception as e:
        logger.error(f"Error in email_task: {str(e)}")
        return False

def queue_email(email_data):
    """
    Queue an email to be sent in the background

    Args:
        email_data (dict): Email data dictionary as required by send_email_task

    Returns:
        str: Job ID or None on failure
    """
    try:
        job = email_queue.enqueue(
            send_email_task, 
            email_data
        )
        logger.info(f"Queued email job {job.id} for {email_data.get('metadata', {}).get('order_number', 'unknown')}")
        return job.id
    except Exception as e:
        logger.error(f"Failed to queue email: {str(e)}")
        return None