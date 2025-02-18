import os
import logging
import json
import pytz
from datetime import datetime, timedelta
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
from werkzeug.serving import WSGIRequestHandler
from config import Config
from PIL import Image
import io
import uuid
import shutil
from apscheduler.schedulers.background import BackgroundScheduler
import threading

# Set longer timeout for the server
WSGIRequestHandler.protocol_version = "HTTP/1.1"

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

# Initialize timezone
import pytz
central = pytz.timezone('US/Central')
utc = pytz.UTC

# Add after storage initialization but before app initialization
def get_central_time():
    """Get current time in Central timezone"""
    # Get current UTC time and make it timezone-aware
    utc_dt = datetime.utcnow().replace(tzinfo=pytz.UTC)
    # Convert to Central time
    return utc_dt.astimezone(central)

scheduler = BackgroundScheduler()

def generate_thumbnails_task():
    """Background task to pre-generate thumbnails for recent orders"""
    with app.app_context():
        try:
            # Get orders from last 7 days that might need thumbnails
            recent_orders = Order.query.filter(
                Order.created_at >= datetime.now() - timedelta(days=7)
            ).all()

            logger.info(f"Starting thumbnail generation for {len(recent_orders)} recent orders")

            for order in recent_orders:
                for item in order.items:
                    thumbnail_key = get_thumbnail_key(item.file_key)

                    # Try to get the thumbnail first
                    try:
                        if not storage.get_file(thumbnail_key):
                            # Only generate if thumbnail doesn't exist
                            file_data = storage.get_file(item.file_key)
                            if file_data:
                                thumb_data = generate_thumbnail(file_data)
                                if thumb_data:
                                    # Upload without content_type parameter
                                    storage.upload_file(
                                        BytesIO(thumb_data),
                                        thumbnail_key
                                    )
                                    logger.info(f"Generated thumbnail for {item.file_key}")
                    except Exception as e:
                        logger.error(f"Error processing thumbnail for {item.file_key}: {str(e)}")
                        continue

        except Exception as e:
            logger.error(f"Error in thumbnail generation task: {str(e)}")

def generate_thumbnail_for_file(file_key):
    """Generate and store thumbnail for a single file"""
    try:
        thumbnail_key = get_thumbnail_key(file_key)
        if not storage.get_file(thumbnail_key):
            file_data = storage.get_file(file_key)
            if file_data:
                thumb_data = generate_thumbnail(file_data)
                if thumb_data:
                    storage.upload_file(BytesIO(thumb_data), thumbnail_key)
    except Exception as e:
        logger.error(f"Error generating thumbnail for {file_key}: {str(e)}")

app = Flask(__name__)
app.config.from_object('config.Config')

# Configure server timeouts and limits
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB limit
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_timeout": 30,
    "pool_size": 5,
    "max_overflow": 10
}

db.init_app(app)
mail.init_app(app)

from models import Order, OrderItem
from utils import allowed_file, generate_order_number, calculate_cost, get_image_dimensions, generate_thumbnail, get_thumbnail_key

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
            logger.debug(f"To: {', '.join(app.config['PRODUCTION_TEAM_EMAIL'])}")
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

# Add this after initializing app but before routes
@app.context_processor
def utility_processor():
    """Make timezone objects available in templates"""
    return {
        'central': central,
        'utc': utc
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/success')
def success():
    return render_template('success.html')

# Remove created_at from order creation to use UTC default
@app.route('/create-order', methods=['POST'])
def create_order():
    """Create an order and return its ID for subsequent file uploads"""
    try:
        email = request.form.get('email')
        po_number = request.form.get('po_number')
        try:
            order_details = json.loads(request.form.get('orderDetails', '[]'))
            total_cost = float(request.form.get('totalCost', 0))
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid order details format: {str(e)}")
            return jsonify({'error': 'Invalid order details'}), 400

        if not email:
            return jsonify({'error': 'Missing email'}), 400

        # Create order with default UTC time
        order = Order(
            order_number=generate_order_number(),
            email=email,
            po_number=po_number,
            total_cost=total_cost,
            status='pending'
        )
        db.session.add(order)
        db.session.commit()
        logger.info(f"Created new order: {order.order_number} with ID: {order.id}")

        return jsonify({
            'success': True,
            'order_id': order.id,
            'order_number': order.order_number
        })

    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to create order'}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        logger.info("Starting upload process")

        if 'file' not in request.files:
            logger.error("No file provided in request")
            return jsonify({'error': 'No file provided'}), 400

        order_id = request.form.get('order_id')
        if not order_id:
            return jsonify({'error': 'Missing order ID'}), 400

        # Get existing order
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Invalid order ID'}), 404

        file = request.files['file']
        try:
            file_details = json.loads(request.form.get('fileDetails', '{}'))
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid file details'}), 400

        # Check file size
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)

        if file_size > 32 * 1024 * 1024:  # 32MB limit
            return jsonify({
                'error': 'File too large',
                'details': f'File {file.filename} is too large. Maximum allowed size is 32MB'
            }), 413

        if file and allowed_file(file.filename):
            # Get number of existing items for this order to create sequence number
            sequence_number = len(order.items) + 1

            # Get the original filename and extension
            original_filename = secure_filename(file.filename)
            name, ext = os.path.splitext(original_filename)

            # Create new filename with order number, sequence, and quantity
            quantity = file_details.get('quantity', 1)
            new_filename = f"{order.order_number}-{sequence_number}_{name}_qty-{quantity}{ext}"

            logger.info(f"Processing file: {new_filename}")

            try:
                if not storage.upload_file(file, new_filename):
                    error_msg = f"Failed to upload file {new_filename} to storage"
                    logger.error(error_msg)
                    raise Exception(error_msg)

                logger.info(f"Successfully uploaded {new_filename} to storage")

                # Create order item with new filename
                order_item = OrderItem(
                    order_id=order.id,
                    file_key=new_filename,
                    width_inches=file_details.get('width', 0),
                    height_inches=file_details.get('height', 0),
                    quantity=file_details.get('quantity', 1),
                    cost=file_details.get('cost', 0),
                    notes=file_details.get('notes', '')
                )
                db.session.add(order_item)
                db.session.commit()
                logger.info(f"Added order item for file: {new_filename}")

                # Generate thumbnail in background
                thread = threading.Thread(target=generate_thumbnail_for_file, args=(new_filename,))
                thread.start()

                # Only send emails after the last file
                if request.form.get('is_last_file') == 'true':
                    if not send_order_emails(order):
                        logger.warning(f"Failed to send emails for order {order.order_number}")

                return jsonify({
                    'success': True,
                    'message': 'File uploaded successfully',
                    'order': order.to_dict()
                }), 200

            except Exception as e:
                db.session.rollback()
                error_msg = str(e)
                logger.error(f"Error processing file: {error_msg}")
                return jsonify({
                    'error': 'Operation failed',
                    'details': f'Failed to process your file: {error_msg}'
                }), 500

    except Exception as e:
        logger.error(f"Unexpected error in upload_file: {str(e)}")
        return jsonify({
            'error': 'Server error',
            'details': f'An unexpected error occurred: {str(e)}'
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
    order = Order.query.get_or_404(order_id)
    # Find the order item for this file to get its quantity
    order_item = OrderItem.query.filter_by(order_id=order_id, file_key=filename).first()
    if not order_item:
        logger.error(f"Order item not found for file: {filename}")
        return "Image not found", 404

    file_data = storage.get_file(filename)
    if file_data is None:
        logger.error(f"Image file not found in storage: {filename}")
        return "Image not found", 404

    # The filename already includes the quantity, so we can use it directly
    download_filename = filename

    # Prepend invoice number if it exists
    if order.invoice_number and order.invoice_number.strip():
        name, ext = os.path.splitext(download_filename)
        download_filename = f"{order.invoice_number}_{name}{ext}"

    return Response(
        file_data,
        mimetype='image/png',
        headers={'Content-Disposition': f'attachment; filename={download_filename}'}
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
                    # Use the file_key directly as it already contains the sequence number and quantity
                    zip_filename = item.file_key

                    # Add invoice number to filename if it exists
                    if order.invoice_number and order.invoice_number.strip():
                        name, ext = os.path.splitext(zip_filename)
                        zip_filename = f"{order.invoice_number}_{name}{ext}"

                    # Add file to zip
                    zf.writestr(zip_filename, file_data)
            except Exception as e:
                logger.error(f"Error adding {item.file_key} to zip: {str(e)}")
                continue

    # Prepare zip file for download
    memory_file.seek(0)
    zip_filename = f"order_{order.order_number}_files.zip"
    if order.invoice_number and order.invoice_number.strip():
        zip_filename = f"{order.invoice_number}_order_{order.order_number}_files.zip"

    return Response(
        memory_file.getvalue(),
        mimetype='application/zip',
        headers={
            'Content-Disposition': f'attachment; filename={zip_filename}'
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

@app.route('/admin/bulk-delete', methods=['POST'])
def bulk_delete():
    try:
        data = request.get_json()
        if not data or 'order_ids' not in data:
            return jsonify({'error': 'Invalid request data'}), 400

        order_ids = data['order_ids']
        logger.info(f"Starting bulk delete of {len(order_ids)} orders")

        # Get all orders and their items before deletion
        orders = Order.query.filter(Order.id.in_(order_ids)).all()
        deleted_count = len(orders)

        for order in orders:
            try:
                logger.info(f"Processing order {order.order_number}")

                # Delete order items from database first
                for item in order.items:
                    # Try to delete files but don't wait for retries if they fail
                    try:
                        storage.delete_file_no_retry(item.file_key)
                        storage.delete_file_no_retry(get_thumbnail_key(item.file_key))
                    except Exception as e:
                        logger.warning(f"Could not delete files for {item.file_key}: {str(e)}")

                    # Delete the item from database
                    db.session.delete(item)

                # Delete the order
                db.session.delete(order)
                logger.info(f"Deleted order {order.order_number} from database")

            except Exception as e:
                logger.error(f"Error deleting order {order.order_number}: {str(e)}")
                continue

        # Commit all changes to database
        logger.info("Committing changes to database...")
        db.session.commit()
        logger.info(f"Successfully deleted {deleted_count} orders")

        return jsonify({
            'success': True,
            'deleted': deleted_count,
            'message': f"Successfully deleted {deleted_count} orders"
        }), 200

    except Exception as e:
        logger.error(f"Error in bulk delete: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete orders', 'details': str(e)}), 500

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

@app.route('/admin/order/<int:order_id>/thumbnail/<path:filename>')
def get_order_thumbnail(order_id, filename):
    """Get thumbnail for order image, using pre-generated thumbnail if available"""
    try:
        thumbnail_key = get_thumbnail_key(filename)

        # Try to get pre-generated thumbnail
        try:
            thumb_data = storage.get_file(thumbnail_key)
            if thumb_data:
                return Response(
                    thumb_data,
                    mimetype='image/jpeg',
                    headers={'Content-Disposition': f'inline; filename={thumbnail_key}'}
                )
        except Exception as e:
            logger.debug(f"No pre-generated thumbnail found for {filename}: {str(e)}")

        # If no thumbnail exists or failed to retrieve, generate one on the fly
        file_data = storage.get_file(filename)
        if file_data is None:
            logger.error(f"Image file not found in storage: {filename}")
            return "Image not found", 404

        thumb_data = generate_thumbnail(file_data)
        if thumb_data:
            # Save the generated thumbnail for future use - without content_type
            try:
                storage.upload_file(
                    BytesIO(thumb_data),
                    thumbnail_key
                )
                logger.info(f"Generated and saved thumbnail for {filename}")
            except Exception as e:
                logger.warning(f"Could not save thumbnail for {filename}: {str(e)}")

            return Response(
                thumb_data,
                mimetype='image/jpeg',
                headers={'Content-Disposition': f'inline; filename={thumbnail_key}'}
            )

        return "Error generating thumbnail", 500

    except Exception as e:
        logger.error(f"Error in get_order_thumbnail: {str(e)}")
        return str(e), 500

@app.route('/get-dimensions', methods=['POST'])
def get_dimensions():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file'}), 400

    try:
        width_inches, height_inches = get_image_dimensions(file)
        return jsonify({
            'width': width_inches,
            'height': height_inches
        })
    except Exception as e:
        logger.error(f"Error getting dimensions: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/update-invoice-number', methods=['POST'])
def update_invoice_number():
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        invoice_number = data.get('invoice_number')

        if not order_id or invoice_number is None:
            return jsonify({'error': 'Missing required fields'}), 400

        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Order not found'}), 404

        order.invoice_number = invoice_number if invoice_number.strip() else None
        db.session.commit()

        return jsonify({'success': True, 'invoice_number': order.invoice_number})
    except Exception as e:
        logger.error(f"Error updating invoice number: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update invoice number'}), 500

@app.route('/admin/bulk-invoice-update', methods=['POST'])
def bulk_invoice_update():
    try:
        data = request.get_json()
        if not data or 'order_ids' not in data or 'invoice_number' not in data:
            return jsonify({'error': 'Invalid request data'}), 400

        order_ids = data['order_ids']
        invoice_number = data['invoice_number'].strip()

        # Update all specified orders
        updated = Order.query.filter(Order.id.in_(order_ids)).update(
            {Order.invoice_number: invoice_number if invoice_number else None},
            synchronize_session=False
        )

        db.session.commit()
        logger.info(f"Bulk updated {updated} orders with invoice number: {invoice_number}")

        return jsonify({'success': True, 'updated': updated}), 200
    except Exception as e:
        logger.error(f"Error in bulk invoice update: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update orders'}), 500

@app.route('/order-history')
def order_history():
    email = request.args.get('email')
    orders = []
    if email:
        orders = Order.query.filter_by(email=email).order_by(Order.created_at.desc()).all()
    return render_template('order_history.html', orders=orders, email=email)

# Start scheduler after app initialization
scheduler.add_job(generate_thumbnails_task, 'interval', hours=1)
scheduler.start()