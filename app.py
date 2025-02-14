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
from werkzeug.serving import WSGIRequestHandler
from config import Config
from PIL import Image
import io
import uuid
import shutil

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

app = Flask(__name__)
app.config.from_object('config.Config')

# Configure server timeouts and limits
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
app.config['PROXY_FIX'] = Config.PROXY_FIX
app.config['PREFERRED_URL_SCHEME'] = Config.PREFERRED_URL_SCHEME

# Configure SQLAlchemy engine with proper pooling
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,  # Enable connection testing
    "pool_recycle": 300,    # Recycle connections every 5 minutes
    "pool_timeout": 30,     # Wait up to 30 seconds for a connection
    "pool_size": 5,         # Maximum number of permanent connections
    "max_overflow": 10      # Maximum number of additional connections
}

if Config.PROXY_FIX:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
    )

db.init_app(app)
mail.init_app(app)

from models import Order, OrderItem
from utils import allowed_file, generate_order_number, calculate_cost, get_image_dimensions, validate_image, generate_thumbnail, get_thumbnail_key

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        # Log request details
        logger.info("Starting upload process")

        if 'file' not in request.files:
            logger.error("No file provided in request")
            return jsonify({'error': 'No file provided', 'details': 'Please select at least one file to upload'}), 400

        files = request.files.getlist('file')
        email = request.form.get('email')
        po_number = request.form.get('po_number')

        try:
            order_details = json.loads(request.form.get('orderDetails', '[]'))
            total_cost = float(request.form.get('totalCost', 0))
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid order details format: {str(e)}")
            return jsonify({'error': 'Invalid order details', 'details': 'Order details are not properly formatted'}), 400

        # Check individual file sizes
        for file in files:
            try:
                file_size = 0
                file.seek(0, 2)  # Seek to end of file
                file_size = file.tell()  # Get current position (file size)
                file.seek(0)  # Reset to beginning

                logger.info(f"Processing file: {file.filename}, Size: {file_size / (1024 * 1024):.1f}MB")

                if file_size > 32 * 1024 * 1024:  # 32MB limit
                    logger.error(f"File too large: {file.filename} ({file_size / (1024 * 1024):.1f}MB)")
                    return jsonify({
                        'error': 'File too large',
                        'details': f'File {file.filename} is {file_size / (1024 * 1024):.1f}MB. Maximum allowed size is 32MB'
                    }), 413
            except Exception as e:
                logger.error(f"Error checking file size for {file.filename}: {str(e)}")
                return jsonify({
                    'error': 'File processing error',
                    'details': f'Error processing file {file.filename}: {str(e)}'
                }), 400

        if not email:
            return jsonify({'error': 'Missing email', 'details': 'Email address is required'}), 400

        if not files:
            return jsonify({'error': 'No files', 'details': 'No files were selected'}), 400

        try:
            # Create order
            order = Order(
                order_number=generate_order_number(),
                email=email,
                po_number=po_number,
                total_cost=total_cost,
                status='pending'
            )
            db.session.add(order)
            logger.info(f"Created new order: {order.order_number}")

            # Process each file
            for file, details in zip(files, order_details):
                try:
                    if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        logger.info(f"Processing file: {filename}")

                        # Read file data into memory
                        file_data = file.read()
                        file.seek(0)  # Reset file pointer for later use

                        # Create BytesIO object for validation
                        img_data = BytesIO(file_data)

                        # Validate image format
                        try:
                            img = Image.open(img_data)
                            format_name = img.format
                            mode_name = img.mode
                            logger.info(f"Image format: {format_name}, Mode: {mode_name}")

                            if format_name != 'PNG':
                                logger.error(f"Invalid image format: {format_name}")
                                return jsonify({
                                    'error': 'Invalid image',
                                    'details': f"Only PNG files are supported. File '{filename}' appears to be {format_name}"
                                }), 400
                            if mode_name not in ('RGB', 'RGBA'):
                                logger.error(f"Invalid image mode: {mode_name}")
                                return jsonify({
                                    'error': 'Invalid image',
                                    'details': f"Image must be in RGB or RGBA format. File '{filename}' is in {mode_name} mode"
                                }), 400
                            img.close()
                        except Exception as e:
                            logger.error(f"Error validating image format: {str(e)}")
                            return jsonify({
                                'error': 'Invalid image',
                                'details': f"Error validating image format for '{filename}': {str(e)}"
                            }), 400

                        # Upload to object storage using the original file data
                        logger.info(f"Starting upload to storage: {filename}")
                        try:
                            if not storage.upload_file(BytesIO(file_data), filename):
                                error_msg = f"Failed to upload file {filename} to object storage"
                                logger.error(error_msg)
                                raise Exception(error_msg)

                            logger.info(f"Successfully uploaded {filename} to storage")

                        except Exception as e:
                            logger.error(f"Storage error for {filename}: {str(e)}")
                            raise Exception(f"Storage error: {str(e)}")

                        # Create order item
                        order_item = OrderItem(
                            order_id=order.id,
                            file_key=filename,
                            width_inches=details['width'],
                            height_inches=details['height'],
                            quantity=details['quantity'],
                            cost=details['cost'],
                            notes=details.get('notes', '')
                        )
                        db.session.add(order_item)
                        logger.info(f"Added order item for file: {filename}")
                except Exception as e:
                    logger.error(f"Error processing file: {str(e)}")
                    return jsonify({
                        'error': 'File processing error',
                        'details': str(e)
                    }), 400

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
            error_msg = str(e)
            logger.error(f"Error processing order: {error_msg}")
            return jsonify({
                'error': 'Operation failed',
                'details': f'Failed to process your order: {error_msg}'
            }), 500

    except Exception as e:
        logger.error(f"Unexpected error in upload_file: {str(e)}")
        return jsonify({
            'error': 'Server error',
            'details': f'An unexpected error occurred: {str(e)}'
        }), 500

@app.route('/upload-chunk', methods=['POST'])
def upload_chunk():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file chunk provided'}), 400

        chunk = request.files['file']
        chunk_index = int(request.form.get('chunkIndex', 0))
        total_chunks = int(request.form.get('totalChunks', 1))
        file_index = int(request.form.get('fileIndex', 0))
        total_files = int(request.form.get('totalFiles', 1))
        filename = secure_filename(chunk.filename)

        # Get or create session
        session_id = request.form.get('sessionId')
        if chunk_index == 0 and not session_id:
            try:
                # Create new session with first chunk
                email = request.form.get('email')
                po_number = request.form.get('po_number')
                order_details = json.loads(request.form.get('orderDetails', '[]'))
                total_cost = float(request.form.get('totalCost', 0))

                logger.info(f"Creating session with PO number: {po_number}")
                session_id = create_upload_session(email, order_details, total_cost, po_number)
                logger.info(f"Created new session {session_id} for file {filename}")
            except Exception as e:
                logger.error(f"Failed to create session: {str(e)}")
                return jsonify({'error': 'Failed to create upload session'}), 500
        elif not session_id:
            return jsonify({'error': 'No session ID provided'}), 400

        # Validate session exists and hasn't expired
        metadata = get_upload_session(session_id)
        if not metadata:
            return jsonify({'error': 'Invalid or expired session'}), 400

        # Save chunk
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp')
        session_dir = os.path.join(temp_dir, session_id)
        chunk_path = os.path.join(session_dir, f"{filename}.part{chunk_index}")

        try:
            chunk.save(chunk_path)
            logger.info(f"Saved chunk {chunk_index}/{total_chunks} for file {filename}")

            # Update progress
            is_complete = update_session_file_progress(session_id, filename, chunk_index, total_chunks)

            # If file is complete, combine chunks
            if is_complete:
                if not combine_file_chunks(session_id, filename):
                    return jsonify({'error': 'Failed to combine file chunks'}), 500

                logger.info(f"Successfully combined chunks for {filename}")

                # If this was the last file, process the order
                metadata = get_upload_session(session_id)
                all_files_complete = all(
                    f['is_complete']
                    for f in metadata['files'].values()
                )

                if file_index == total_files - 1 and all_files_complete:
                    try:
                        # Create order
                        logger.info(f"Creating order with metadata: {metadata}")
                        order = Order(
                            order_number=generate_order_number(),
                            email=metadata['email'],
                            total_cost=metadata['totalCost'],
                            po_number=metadata.get('po_number'),
                            status='pending'
                        )
                        logger.info(f"Created order with PO number: {order.po_number}")
                        db.session.add(order)
                        logger.info(f"Created order: {order.order_number}")

                        # Process all completed files
                        processed_files = []
                        for fname in os.listdir(session_dir):
                            if fname == 'metadata.json' or '.part' in fname:
                                continue

                            file_path = os.path.join(session_dir, fname)
                            with open(file_path, 'rb') as f:
                                file_data = f.read()

                            # Upload to storage
                            if storage.upload_file(BytesIO(file_data), fname):
                                processed_files.append(fname)
                                logger.info(f"Uploaded {fname} to storage")
                            else:
                                raise Exception(f"Failed to upload {fname} to storage")

                        logger.info(f"Successfully processed files: {processed_files}")
                        logger.info(f"Order details: {metadata['orderDetails']}")

                        # Create order items
                        items_created = 0
                        for details in metadata['orderDetails']:
                            filename = secure_filename(details['filename'])
                            if filename in processed_files:
                                item = OrderItem(
                                    order=order,
                                    file_key=filename,
                                    width_inches=float(details['width']),
                                    height_inches=float(details['height']),
                                    quantity=int(details['quantity']),
                                    cost=float(details['cost']),
                                    notes=details.get('notes', '')  # Add notes from details
                                )
                                db.session.add(item)
                                items_created += 1
                                logger.info(f"Added order item for {filename}")
                            else:
                                logger.error(f"File {filename} not found in processed files")
                                raise Exception(f"File {filename} was not properly processed")

                        if items_created == 0:
                            raise Exception("No order items were created")

                        try:
                            # Commit the transaction
                            db.session.commit()
                            logger.info(f"Order {order.order_number} committed successfully with {items_created} items")

                            # Send confirmation emails
                            if not send_order_emails(order):
                                logger.warning(f"Failed to send confirmation emails for order {order.order_number}")

                            # Only clean up after successful commit
                            cleanup_session(session_id)

                            # Return success response with redirect
                            response = {
                                'success': True,
                                'message': 'Order submitted successfully',
                                'order': order.to_dict(),
                                'redirect': url_for('success')
                            }
                            logger.info(f"Returning success response: {response}")
                            return jsonify(response)
                        except Exception as e:
                            logger.error(f"Error committing order: {str(e)}")
                            db.session.rollback()
                            raise Exception(f"Failed to commit order: {str(e)}")

                    except Exception as e:
                        logger.error(f"Error processing order: {str(e)}")
                        db.session.rollback()
                        return jsonify({'error': f'Error processing order: {str(e)}'}), 500

            # Return success for this chunk
            return jsonify({
                'success': True,
                'message': 'Chunk uploaded successfully',
                'sessionId': session_id
            })

        except Exception as e:
            logger.error(f"Error saving chunk: {str(e)}")
            return jsonify({'error': f'Error saving chunk: {str(e)}'}), 500

    except Exception as e:
        logger.error(f"Error in upload_chunk: {str(e)}")
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
    order = Order.query.get_or_404(order_id)
    file_data = storage.get_file(filename)
    if file_data is None:
        logger.error(f"Image file not found in storage: {filename}")
        return "Image not found", 404

    # Prepend invoice number if it exists
    download_filename = filename
    if order.invoice_number and order.invoice_number.strip():
        download_filename = f"{order.invoice_number}_{filename}"

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
                    # Add invoice number to filename if it exists
                    zip_filename = item.file_key
                    if order.invoice_number and order.invoice_number.strip():
                        zip_filename = f"{order.invoice_number}_{item.file_key}"
                    # Add file to zip with modified filename
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
    file_data = storage.get_file(filename)
    if file_data is None:
        logger.error(f"Image file not found in storage: {filename}")
        return "Image not found", 404

    # Create thumbnail
    image = Image.open(io.BytesIO(file_data))

    # Calculate thumbnail size while maintaining aspect ratio
    max_size = (100, 100)
    image.thumbnail(max_size, Image.Resampling.LANCZOS)

    # Save thumbnail to bytes
    thumb_io = io.BytesIO()
    image.save(thumb_io, 'PNG', quality=85)
    thumb_io.seek(0)

    return Response(
        thumb_io.getvalue(),
        mimetype='image/png',
        headers={'Content-Disposition': f'inline; filename=thumb_{filename}'}
    )

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

# Session management functions
def create_upload_session(email, order_details, total_cost, po_number):
    """Create a new upload session with metadata"""
    session_id = str(uuid.uuid4())
    temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp')
    session_dir = os.path.join(temp_dir, session_id)

    try:
        os.makedirs(session_dir, exist_ok=True)
        metadata = {
            'email': email,
            'orderDetails': order_details,
            'totalCost': total_cost,
            'po_number': po_number,
            'files': {},
            'created_at': datetime.utcnow().isoformat()
        }

        with open(os.path.join(session_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f)

        logger.info(f"Created upload session {session_id} with metadata: {json.dumps(metadata)}")
        return session_id
    except Exception as e:
        logger.error(f"Error creating upload session: {str(e)}")
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
        raise

def get_upload_session(session_id):
    """Get session metadata and validate it hasn't expired"""
    temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp')
    session_dir = os.path.join(temp_dir, session_id)
    metadata_path = os.path.join(session_dir, 'metadata.json')

    if not os.path.exists(metadata_path):
        return None

    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        # Check for session timeout (30 minutes)
        created_at = datetime.fromisoformat(metadata['created_at'])
        if datetime.utcnow() - created_at > timedelta(minutes=30):
            cleanup_session(session_id)
            return None

        return metadata
    except Exception as e:
        logger.error(f"Error reading session metadata: {str(e)}")
        return None

def update_session_file_progress(session_id, filename, chunk_index, total_chunks):
    """Update file progress in session metadata"""
    temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp')
    session_dir = os.path.join(temp_dir, session_id)
    metadata_path = os.join(session_dir, 'metadata.json')

    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        if filename not in metadata['files']:
            metadata['files'][filename] = {
                'chunks_received': [],
                'totalchunks': total_chunks,
                'is_complete': False
            }

        # Add chunk to received list if not already present
        if chunk_index not in metadata['files'][filename]['chunks_received']:
            metadata['files'][filename]['chunks_received'].append(chunk_index)

        # Check if file is complete
        is_complete = len(metadata['files'][filename]['chunks_received']) == total_chunks
        metadata['files'][filename]['is_complete'] = is_complete

        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)

        return is_complete
    except Exception as e:
        logger.error(f"Error updating session progress: {str(e)}")
        return False

def cleanup_session(session_id):
    """Clean up session directory and files"""
    temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp')
    session_dir = os.path.join(temp_dir, session_id)

    try:
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
            logger.info(f"Cleaned up session directory: {session_id}")
    except Exception as e:
        logger.error(f"Error cleaning up session: {str(e)}")

def combine_file_chunks(session_id, filename):
    """Combine chunks into complete file and validate"""
    temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp')
    session_dir = os.path.join(temp_dir, session_id)
    final_path = os.path.join(session_dir, filename)

    try:
        metadata = get_upload_session(session_id)
        if not metadata or filename not in metadata['files']:
            raise Exception("Invalid session or file")

        file_meta = metadata['files'][filename]
        if not file_meta['is_complete']:
            raise Exception("File is not complete")

        # Combine chunks
        with open(final_path, 'wb') as outfile:
            for i in range(file_meta['totalchunks']):
                chunk_path = os.path.join(session_dir, f"{filename}.part{i}")
                with open(chunk_path, 'rb') as infile:
                    outfile.write(infile.read())
                os.remove(chunk_path)

        # Validate combined file
        with Image.open(final_path) as img:
            if img.format != 'PNG' or img.mode not in ('RGB', 'RGBA'):
                raise Exception("Invalid image format")

        return True
    except Exception as e:
        logger.error(f"Error combining chunks for {filename}: {str(e)}")
        if os.path.exists(final_path):
            os.remove(final_path)
        return False

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