import os
import logging
import json
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, send_file, Response
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from sqlalchemy.orm import DeclarativeBase
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail as SGMail
from io import BytesIO
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from storage import ObjectStorage

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
mail = Mail()

try:
    storage = ObjectStorage()
    logger.info("Successfully initialized ObjectStorage")
except Exception as e:
    logger.error(f"Failed to initialize ObjectStorage: {str(e)}")
    raise

app = Flask(__name__)
app.config.from_object('config.Config')

# Configure SQLAlchemy engine with proper pooling
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,  # Enable connection testing
    "pool_recycle": 300,    # Recycle connections every 5 minutes
    "pool_timeout": 30,     # Wait up to 30 seconds for a connection
    "pool_size": 5,         # Maximum number of permanent connections
    "max_overflow": 10      # Maximum number of additional connections
}

db.init_app(app)
mail.init_app(app)

from models import Order, OrderItem
from utils import allowed_file, generate_order_number, calculate_cost, get_image_dimensions, validate_image

with app.app_context():
    db.create_all()
    logger.info("Database tables created successfully")

def send_order_emails(order):
    # Customer email
    customer_email = SGMail(
        from_email=app.config['MAIL_DEFAULT_SENDER'],
        to_emails=order.email,
        subject=f'DTF Printing Order Confirmation - {order.order_number}',
        html_content=render_template('emails/customer_order_confirmation.html', order=order)
    )

    # Production team email
    production_email = SGMail(
        from_email=app.config['MAIL_DEFAULT_SENDER'],
        to_emails=app.config['PRODUCTION_TEAM_EMAIL'],
        subject=f'New DTF Printing Order - {order.order_number}',
        html_content=render_template('emails/production_order_notification.html', order=order)
    )

    try:
        sg = SendGridAPIClient(app.config['SENDGRID_API_KEY'])
        sg.send(customer_email)
        sg.send(production_email)
        logger.info(f"Order confirmation emails sent successfully for order: {order.order_number}")
        return True
    except Exception as e:
        logger.error(f"Error sending emails: {str(e)}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        logger.error("No file provided in request")
        return jsonify({'error': 'No file provided'}), 400

    files = request.files.getlist('file')
    email = request.form.get('email')

    try:
        order_details = json.loads(request.form.get('orderDetails', '[]'))
        total_cost = float(request.form.get('totalCost', 0))
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Invalid order details format: {str(e)}")
        return jsonify({'error': 'Invalid order details format'}), 400

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    if not files:
        return jsonify({'error': 'No files selected'}), 400

    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            # Create order
            order = Order(
                order_number=generate_order_number(),
                email=email,
                total_cost=total_cost,
                status='pending'
            )
            db.session.add(order)
            logger.info(f"Created new order: {order.order_number}")

            # Process each file
            for file, details in zip(files, order_details):
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)

                    # Store file in memory for validation
                    file_data = BytesIO(file.read())
                    file_data.seek(0)  # Reset pointer for validation

                    # Validate image
                    is_valid, error_message = validate_image(file_data)
                    if not is_valid:
                        logger.error(f"Image validation failed for {filename}: {error_message}")
                        return jsonify({'error': error_message}), 400

                    # Reset pointer for storage
                    file_data.seek(0)

                    # Upload to object storage with explicit error handling
                    logger.info(f"Uploading file {filename} to object storage")
                    if not storage.upload_file(file_data, filename):
                        raise Exception(f"Failed to upload file {filename} to object storage")

                    # Create order item
                    item = OrderItem(
                        order=order,
                        file_key=filename,
                        width_inches=float(details['width']),
                        height_inches=float(details['height']),
                        quantity=int(details['quantity']),
                        cost=float(details['cost'])
                    )
                    db.session.add(item)
                    logger.info(f"Added order item for file {filename}")

            try:
                db.session.commit()
                logger.info(f"Order {order.order_number} committed to database successfully")
                break  # Exit retry loop on success
            except Exception as db_error:
                db.session.rollback()
                retry_count += 1
                if retry_count == max_retries:
                    logger.error(f"Database error after {max_retries} retries: {str(db_error)}")
                    return jsonify({'error': 'Database error occurred. Please try again.'}), 500
                logger.warning(f"Database error (attempt {retry_count}): {str(db_error)}")
                continue

            # Send emails
            if not send_order_emails(order):
                logger.warning(f"Failed to send emails for order {order.order_number}")

            return jsonify({
                'message': 'Order submitted successfully',
                'order': order.to_dict(),
                'redirect': url_for('success')
            }), 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error processing upload: {str(e)}")
            return jsonify({'error': str(e)}), 500

@app.route('/admin')
def admin():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin.html', orders=orders)

@app.route('/admin/order/<int:order_id>')
def view_order(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('order_detail.html', order=order)

@app.route('/admin/order/<int:order_id>/status', methods=['POST'])
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = request.form.get('status', 'pending')
    db.session.commit()
    return redirect(url_for('view_order', order_id=order.id))

@app.route('/admin/order/<int:order_id>/image/<path:filename>')
def get_order_image(order_id, filename):
    file_data = storage.get_file(filename)
    if file_data is None:
        logger.error(f"Image file not found in storage: {filename}")
        return "Image not found", 404

    return Response(
        file_data,
        mimetype='image/png',
        headers={'Content-Disposition': f'inline; filename={filename}'}
    )

@app.route('/admin/order/<int:order_id>/download/<path:filename>')
def download_order_image(order_id, filename):
    file_data = storage.get_file(filename)
    if file_data is None:
        logger.error(f"Image file not found in storage: {filename}")
        return "Image not found", 404

    return Response(
        file_data,
        mimetype='image/png',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )