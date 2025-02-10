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
import zipfile
from io import BytesIO
from datetime import datetime, timedelta

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
mail = Mail()

# Initialize storage with proper error handling
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
    """Send order confirmation emails to customer and production team"""
    try:
        # Customer email
        customer_email = SGMail(
            from_email=('info@appareldecorating.net', 'DTF Printing'),
            to_emails=order.email,
            subject=f'DTF Printing Order Confirmation - {order.order_number}',
            html_content=render_template('emails/customer_order_confirmation.html', order=order)
        )

        # Production team email
        production_email = SGMail(
            from_email=('info@appareldecorating.net', 'DTF Printing'),
            to_emails=app.config['PRODUCTION_TEAM_EMAIL'],
            subject=f'New DTF Printing Order - {order.order_number}',
            html_content=render_template('emails/production_order_notification.html', order=order)
        )

        try:
            sg = SendGridAPIClient(app.config['SENDGRID_API_KEY'])

            # Send customer email with detailed logging
            logger.info(f"Attempting to send customer email for order {order.order_number}")
            logger.debug(f"From: info@appareldecorating.net")
            logger.debug(f"To: {order.email}")
            logger.debug(f"Subject: DTF Printing Order Confirmation - {order.order_number}")

            response = sg.send(customer_email)
            if response.status_code not in [200, 201, 202]:
                logger.error(f"Failed to send customer email. Status code: {response.status_code}")
                logger.error(f"Response body: {response.body.decode('utf-8') if hasattr(response, 'body') else 'No body'}")
                return False
            logger.info(f"Successfully sent customer email for order {order.order_number}")

            # Send production team email
            logger.info(f"Attempting to send production team email for order {order.order_number}")
            response = sg.send(production_email)
            if response.status_code not in [200, 201, 202]:
                logger.error(f"Failed to send production team email. Status code: {response.status_code}")
                logger.error(f"Response body: {response.body.decode('utf-8') if hasattr(response, 'body') else 'No body'}")
                return False
            logger.info(f"Successfully sent production team email for order {order.order_number}")

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

    except Exception as e:
        logger.error(f"Error preparing emails: {str(e)}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            logger.error("No file provided in request")
            return jsonify({'error': 'No file provided', 'details': 'Please select at least one file to upload'}), 400

        files = request.files.getlist('file')
        email = request.form.get('email')

        try:
            order_details = json.loads(request.form.get('orderDetails', '[]'))
            total_cost = float(request.form.get('totalCost', 0))
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid order details format: {str(e)}")
            return jsonify({'error': 'Invalid order details', 'details': 'Order details are not properly formatted'}), 400

        if not email:
            return jsonify({'error': 'Missing email', 'details': 'Email address is required'}), 400

        if not files:
            return jsonify({'error': 'No files', 'details': 'No files were selected'}), 400

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
                            return jsonify({
                                'error': 'Invalid image',
                                'details': error_message
                            }), 400

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

                db.session.commit()
                logger.info(f"Order {order.order_number} committed to database successfully")

                # Send emails
                if not send_order_emails(order):
                    logger.warning(f"Failed to send emails for order {order.order_number}")
                    # Continue anyway as this is not critical

                return jsonify({
                    'success': True,
                    'message': 'Order submitted successfully',
                    'order': order.to_dict(),
                    'redirect': url_for('success')
                }), 200

            except Exception as e:
                db.session.rollback()
                retry_count += 1
                error_msg = str(e)
                logger.error(f"Error (attempt {retry_count}): {error_msg}")

                if retry_count >= max_retries:
                    return jsonify({
                        'error': 'Operation failed',
                        'details': 'Failed to process your order after multiple attempts. Please try again.'
                    }), 500

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({
            'error': 'Server error',
            'details': 'An unexpected error occurred. Please try again.'
        }), 500

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

@app.route('/admin/order/<int:order_id>/download-all')
def download_all_images(order_id):
    order = Order.query.get_or_404(order_id)

    # Create a zip file in memory
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for item in order.items:
            try:
                file_data = storage.get_file(item.file_key)
                if file_data:
                    # Add file to zip with its original filename
                    zf.writestr(item.file_key, file_data)
            except Exception as e:
                logger.error(f"Error adding {item.file_key} to zip: {str(e)}")
                continue

    # Prepare zip file for download
    memory_file.seek(0)
    return Response(
        memory_file.getvalue(),
        mimetype='application/zip',
        headers={
            'Content-Disposition': f'attachment; filename=order_{order.order_number}_files.zip'
        }
    )

@app.route('/admin/bulk-status-update', methods=['POST'])
def bulk_status_update():
    try:
        data = request.get_json()
        if not data or 'order_ids' not in data or 'status' not in data:
            return jsonify({'error': 'Invalid request data'}), 400

        order_ids = data['order_ids']
        new_status = data['status']

        # Update all specified orders
        updated = Order.query.filter(Order.id.in_(order_ids)).update(
            {Order.status: new_status},
            synchronize_session=False
        )

        db.session.commit()
        logger.info(f"Bulk updated {updated} orders to status: {new_status}")

        return jsonify({'success': True, 'updated': updated}), 200
    except Exception as e:
        logger.error(f"Error in bulk status update: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update orders'}), 500


@app.route('/admin/export')
def export_orders():
    try:
        import csv
        from io import StringIO

        # Get filter parameters
        status = request.args.get('status')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # Base query
        query = Order.query

        # Apply filters
        if status:
            query = query.filter(Order.status == status)
        if start_date:
            query = query.filter(Order.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date:
            # Add one day to include the entire end date
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Order.created_at < end)

        # Get filtered orders
        orders = query.order_by(Order.created_at.desc()).all()

        # Create CSV
        si = StringIO()
        writer = csv.writer(si)

        # Write headers
        writer.writerow(['Order Number', 'Date', 'Email', 'Status', 'Total Cost', 'Number of Items'])

        # Write order data
        for order in orders:
            writer.writerow([
                order.order_number,
                order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                order.email,
                order.status,
                f"${order.total_cost:.2f}",
                len(order.items)
            ])

        output = si.getvalue()
        si.close()

        return Response(
            output,
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=dtf_orders.csv',
                'Content-Type': 'text/csv'
            }
        )
    except Exception as e:
        logger.error(f"Error exporting orders: {str(e)}")
        return jsonify({'error': 'Failed to export orders'}), 500