import os
import logging
import json
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail as SGMail
from flask import current_app, render_template
from task_queue import enqueue_email_task

logger = logging.getLogger(__name__)

# Detailed logging for email sending process
def log_email_details(recipient, subject, is_production=False):
    """Log detailed information about an email being sent"""
    env_type = "production" if is_production else "development"
    logger.info(f"[{env_type}] Preparing to send email to: {recipient}")
    logger.info(f"[{env_type}] Email subject: {subject}")
    
    # Log if SendGrid API key is configured (without exposing the key)
    api_key = os.environ.get('SENDGRID_API_KEY') or current_app.config.get('SENDGRID_API_KEY')
    if api_key:
        logger.info(f"[{env_type}] SendGrid API key is configured")
    else:
        logger.error(f"[{env_type}] SendGrid API key is NOT configured")
    
    # Log SendGrid sender email
    sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'info@appareldecorating.net')
    logger.info(f"[{env_type}] Sending from: {sender}")

def _send_email_via_sendgrid(from_email, to_emails, subject, html_content, is_production=False):
    """Internal function to send an email via SendGrid"""
    try:
        # Create email
        message = SGMail(
            from_email=from_email,
            to_emails=to_emails,
            subject=subject,
            html_content=html_content
        )
        
        # Get API key from environment or app config
        api_key = os.environ.get('SENDGRID_API_KEY') or current_app.config.get('SENDGRID_API_KEY')
        if not api_key:
            logger.error("SendGrid API key not found in environment or app config")
            return False, "API key not configured"
        
        # Initialize SendGrid client with detailed error handling
        sg = SendGridAPIClient(api_key)
        
        # Send email with detailed logging
        env_type = "production" if is_production else "development"
        logger.info(f"[{env_type}] Sending email via SendGrid to: {to_emails}")
        response = sg.send(message)
        
        # Log success or failure based on response code
        if response.status_code not in [200, 201, 202]:
            error_body = response.body.decode('utf-8') if hasattr(response, 'body') else 'No response body'
            logger.error(f"[{env_type}] Failed to send email. Status code: {response.status_code}")
            logger.error(f"[{env_type}] Response body: {error_body}")
            return False, f"SendGrid API error: {response.status_code}"
        
        logger.info(f"[{env_type}] Successfully sent email via SendGrid. Status code: {response.status_code}")
        return True, f"Email sent successfully"
    
    except Exception as e:
        logger.error(f"SendGrid email error: {str(e)}")
        # Log detailed error information
        if hasattr(e, 'body'):
            try:
                error_body = e.body.decode('utf-8')
                error_json = json.loads(error_body)
                logger.error(f"SendGrid API error details: {json.dumps(error_json, indent=2)}")
            except:
                logger.error(f"Raw SendGrid error body: {e.body}")
        return False, str(e)

def send_order_confirmation_email(order):
    """Send order confirmation email to customer"""
    try:
        # Determine if we're in production
        is_production = os.environ.get('FLASK_ENV') == 'production'
        
        # Set sender info
        sender_name = 'DTF Printing'
        sender_email = current_app.config.get('MAIL_DEFAULT_SENDER', 'info@appareldecorating.net')
        from_email = (sender_email, sender_name)
        
        # Create email content
        subject = f'DTF Printing Order Confirmation - {order.order_number}'
        html_content = render_template('emails/customer_order_confirmation.html', order=order)
        
        # Log email details
        log_email_details(order.email, subject, is_production)
        
        # Use task queue to send email with retries
        return enqueue_email_task(
            _send_email_via_sendgrid,
            from_email,
            order.email,
            subject,
            html_content,
            is_production
        )
    
    except Exception as e:
        logger.error(f"Error preparing customer confirmation email: {str(e)}")
        return False

def send_production_notification_email(order):
    """Send order notification email to production team"""
    try:
        # Determine if we're in production
        is_production = os.environ.get('FLASK_ENV') == 'production'
        
        # Set sender info
        sender_name = 'DTF Printing'
        sender_email = current_app.config.get('MAIL_DEFAULT_SENDER', 'info@appareldecorating.net')
        from_email = (sender_email, sender_name)
        
        # Get production team emails
        to_emails = current_app.config.get('PRODUCTION_TEAM_EMAIL', ['rickey.stitchscreen@gmail.com'])
        
        # Create email content
        subject = f'New DTF Printing Order - {order.order_number}'
        html_content = render_template('emails/production_order_notification.html', order=order)
        
        # Log email details
        to_emails_str = ', '.join(to_emails) if isinstance(to_emails, list) else to_emails
        log_email_details(to_emails_str, subject, is_production)
        
        # Use task queue to send email with retries
        return enqueue_email_task(
            _send_email_via_sendgrid,
            from_email,
            to_emails,
            subject,
            html_content,
            is_production
        )
    
    except Exception as e:
        logger.error(f"Error preparing production notification email: {str(e)}")
        return False