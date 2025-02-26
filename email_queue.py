import os
import logging
from rq import Queue
from redis import Redis
from datetime import datetime
from flask import current_app
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail as SGMail

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Redis connection using TCP
redis_conn = Redis(host='localhost', port=6379, db=0)
email_queue = Queue('emails', connection=redis_conn)

def queue_order_emails(order, retry=True):
    """
    Queue emails for sending via background worker.
    Falls back to direct sending if queue is unavailable.
    """
    try:
        # Queue customer email
        email_queue.enqueue(
            send_customer_email,
            order.id,
            order.email,
            order.order_number,
            retry_attempts=3 if retry else 0
        )

        # Queue production team email
        email_queue.enqueue(
            send_production_email,
            order.id,
            order.order_number,
            retry_attempts=3 if retry else 0
        )

        logger.info(f"Successfully queued emails for order {order.order_number}")
        return True

    except Exception as e:
        logger.error(f"Failed to queue emails for order {order.order_number}: {str(e)}")
        # Fall back to direct sending if queue fails
        from app import send_order_emails
        return send_order_emails(order)

def send_customer_email(order_id, customer_email, order_number):
    """Background task to send customer confirmation email"""
    try:
        from app import app, Order
        with app.app_context():
            order = Order.query.get(order_id)
            if not order:
                logger.error(f"Order {order_id} not found")
                return False

            sg = SendGridAPIClient(app.config['SENDGRID_API_KEY'])
            message = SGMail(
                from_email=('info@appareldecorating.net', 'DTF Printing'),
                to_emails=customer_email,
                subject=f'DTF Printing Order Confirmation - {order_number}',
                html_content=render_template('emails/customer_order_confirmation.html', order=order)
            )

            response = sg.send(message)
            if response.status_code in [200, 201, 202]:
                logger.info(f"Successfully sent customer email for order {order_number}")
                return True
            else:
                logger.error(f"Failed to send customer email. Status: {response.status_code}")
                return False

    except Exception as e:
        logger.error(f"Error sending customer email: {str(e)}")
        return False

def send_production_email(order_id, order_number):
    """Background task to send production team notification"""
    try:
        from app import app, Order
        with app.app_context():
            order = Order.query.get(order_id)
            if not order:
                logger.error(f"Order {order_id} not found")
                return False

            sg = SendGridAPIClient(app.config['SENDGRID_API_KEY'])
            message = SGMail(
                from_email=('info@appareldecorating.net', 'DTF Printing'),
                to_emails=app.config['PRODUCTION_TEAM_EMAIL'],
                subject=f'New DTF Printing Order - {order_number}',
                html_content=render_template('emails/production_order_notification.html', order=order)
            )

            response = sg.send(message)
            if response.status_code in [200, 201, 202]:
                logger.info(f"Successfully sent production team email for order {order_number}")
                return True
            else:
                logger.error(f"Failed to send production team email. Status: {response.status_code}")
                return False

    except Exception as e:
        logger.error(f"Error sending production team email: {str(e)}")
        return False

from jinja2 import Environment, FileSystemLoader

# Assuming templates are in a 'templates' subdirectory
env = Environment(loader=FileSystemLoader('templates'))

def render_template(template_name, **context):
    template = env.get_template(template_name)
    return template.render(**context)