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
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

# Set longer timeout for the server
WSGIRequestHandler.protocol_version = "HTTP/1.1"

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
mail = Mail()
login_manager = LoginManager()

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
    utc_dt = datetime.utcnow().replace(tzinfo=pytz.UTC)
    return utc_dt.astimezone(central)

# Move the task definition before scheduler initialization
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

# Now initialize the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(generate_thumbnails_task, 'interval', hours=1)
scheduler.start()

app = Flask(__name__)
app.config.from_object('config.Config')

# Initialize Flask-Login
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

from models import Order, OrderItem, User
from utils import allowed_file, generate_order_number, calculate_cost, get_image_dimensions, generate_thumbnail, get_thumbnail_key

with app.app_context():
    db.create_all()
    # Create default admin user if it doesn't exist
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(
            username='admin',
            email='admin@appareldecorating.net',
            is_admin=True
        )
        admin_user.set_password('Stitches1')  # Changed password to Stitches1
        db.session.add(admin_user)
        db.session.commit()
    logger.info("Database tables created successfully")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password) and user.is_admin:
            login_user(user)
            return redirect(url_for('admin'))

        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# Protect admin routes with login_required
@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin.html', orders=orders)

@app.route('/admin/order/<int:order_id>')
@login_required
def view_order(order_id):
    if not current_user.is_admin:
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
    order = Order.query.get_or_404(order_id)
    return render_template('order_detail.html', order=order)

@app.route('/admin/order/<int:order_id>/status', methods=['POST'])
@login_required
def update_order_status(order_id):
    if not current_user.is_admin:
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
    order = Order.query.get_or_404(order_id)
    order.status = request.form.get('status', 'pending')
    db.session.commit()
    return redirect(url_for('view_order', order_id=order.id))

@app.route('/admin/order/<int:order_id>/image/<path:filename>')
@login_required
def get_order_image(order_id, filename):
    if not current_user.is_admin:
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
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
@login_required
def download_order_image(order_id, filename):
    if not current_user.is_admin:
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
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
@login_required
def download_all_images(order_id):
    if not current_user.is_admin:
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
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
@login_required
def bulk_status_update():
    if not current_user.is_admin:
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
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
@login_required
def export_orders():
    if not current_user.is_admin:
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
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
@login_required
def get_order_thumbnail(order_id, filename):
    if not current_user.is_admin:
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
    """Get thumbnail for order image, using pre-generated thumbnail if available"""
    try:
        thumbnail_key = get_thumbnail_key(filename)

        # Try to get pre-generated thumbnail
        try:
            thumb_data = storage.get_file(thumbnail_key)
            if thumb_data:
                return Response(
                    thumb_data,
                    mimetype='image/png',
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
            # Save the generated thumbnail for future use
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
                mimetype='image/png',
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
@login_required
def update_invoice_number():
    if not current_user.is_admin:
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
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
@login_required
def bulk_invoice_update():
    if not current_user.is_admin:
        flash('You do not have permission to access this page.')
        return redirect(url_for('index'))
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

#Start scheduler after app initialization.  The scheduler is already started above.

@app.template_filter('to_central')
def to_central_filter(dt):
    """Convert UTC datetime to Central time"""
    if dt is None:
        logger.debug("DateTime is None")
        return ""

    logger.debug(f"Original datetime: {dt}, tzinfo: {dt.tzinfo}")

    # Make the datetime timezone-aware (UTC)
    utc_dt = dt.replace(tzinfo=pytz.UTC)
    logger.debug(f"After UTC assignment: {utc_dt}, tzinfo: {utc_dt.tzinfo}")

    # Convert to Central time
    central_dt = utc_dt.astimezone(central)
    logger.debug(f"After conversion to Central: {central_dt}, tzinfo: {central_dt.tzinfo}")

    formatted = central_dt.strftime('%B %d, %Y %I:%M %p') + ' CST'
    logger.debug(f"Final formatted string: {formatted}")

    return formatted

# Add new helper function after the existing helper functions but before routes
def get_smart_image_url(order_id, filename, external=True, scheme='https'):
    """
    Get the most appropriate image URL based on thumbnail availability.
    Returns thumbnail URL if available, otherwise returns full image URL.
    """
    thumbnail_key = get_thumbnail_key(filename)
    try:
        if storage.get_file(thumbnail_key):
            return url_for('get_order_thumbnail', 
                         order_id=order_id, 
                         filename=filename, 
                         _external=external, 
                         _scheme=scheme)
    except Exception as e:
        logger.debug(f"Error checking thumbnail {thumbnail_key}: {str(e)}")

    # Fallback to full image if thumbnail not available
    return url_for('get_order_image', 
                  order_id=order_id, 
                  filename=filename, 
                  _external=external, 
                  _scheme=scheme)

@app.context_processor
def utility_processor():
    """Make utility functions available in templates"""
    return {
        'central': central,
        'utc': utc,
        'get_smart_image_url': get_smart_image_url
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

@app.route('/send_order_emails', methods=['POST'])
def send_order_emails_api():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        order_id = request.json.get('order_id')
        if not order_id:
            return jsonify({'error': 'Missing order ID'}), 400

        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        success = send_order_emails(order)
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Error sending emails: {str(e)}")
        return jsonify({'error': 'Failed to send emails'}), 500

@app.route('/admin/delete-orders', methods=['POST'])
@login_required
def delete_orders():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized access'}), 401

    try:
        data = request.get_json()
        if not data or 'order_ids' not in data:
            return jsonify({'error': 'Missing order IDs'}), 400

        order_ids = data['order_ids']

        # Get all orders with their items
        orders = Order.query.filter(Order.id.in_(order_ids)).all()

        # Collect all file keys to delete
        file_keys = []
        for order in orders:
            for item in order.items:
                # Add both the original file and its thumbnail
                file_keys.append(item.file_key)
                thumbnail_key = get_thumbnail_key(item.file_key)
                file_keys.append(thumbnail_key)

        # Delete files from storage
        for file_key in file_keys:
            try:
                storage.delete_file(file_key)
                logger.info(f"Deleted file: {file_key}")
            except Exception as e:
                logger.warning(f"Failed to delete file {file_key}: {str(e)}")

        # First delete all order items
        for order in orders:
            OrderItem.query.filter_by(order_id=order.id).delete()

        # Then delete the orders
        deleted = Order.query.filter(Order.id.in_(order_ids)).delete(
            synchronize_session=False
        )

        db.session.commit()
        logger.info(f"Successfully deleted {deleted} orders and their associated files")

        return jsonify({
            'success': True,
            'message': f'Successfully deleted {deleted} orders',
            'deleted_count': deleted
        })

    except Exception as e:
        logger.error(f"Error deleting orders: {str(e)}")
        db.session.rollback()
        return jsonify({'error': f'Failed to delete orders: {str(e)}'}), 500