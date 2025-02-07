import os
import logging
import json
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from sqlalchemy.orm import DeclarativeBase
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail as SGMail

logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
mail = Mail()

app = Flask(__name__)
app.config.from_object('config.Config')

db.init_app(app)
mail.init_app(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

from models import Order, OrderItem
from utils import allowed_file, generate_order_number, calculate_cost, get_image_dimensions, validate_image

with app.app_context():
    db.create_all()
    logging.info("Database tables created successfully")

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
        return True
    except Exception as e:
        logging.error(f"Error sending emails: {str(e)}")
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
        return jsonify({'error': 'No file provided'}), 400

    files = request.files.getlist('file')
    email = request.form.get('email')
    order_details = json.loads(request.form.get('orderDetails', '[]'))
    total_cost = float(request.form.get('totalCost', 0))

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    if not files:
        return jsonify({'error': 'No files selected'}), 400

    try:
        # Create order
        order = Order(
            order_number=generate_order_number(),
            email=email,
            total_cost=total_cost,
            status='pending'
        )
        db.session.add(order)

        # Process each file
        for file, details in zip(files, order_details):
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                # Validate image
                is_valid, error_message = validate_image(filepath)
                if not is_valid:
                    return jsonify({'error': error_message}), 400

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

        try:
            db.session.commit()
        except Exception as db_error:
            db.session.rollback()
            logging.error(f"Database error: {str(db_error)}")
            return jsonify({
                'error': 'Database error occurred. Please try again.'
            }), 500

        # Send emails
        if not send_order_emails(order):
            # Log email failure but don't return error to user since order was saved
            logging.warning(f"Failed to send emails for order {order.order_number}")

        return jsonify({
            'message': 'Order submitted successfully',
            'order': order.to_dict(),
            'redirect': url_for('success')
        }), 200

    except Exception as e:
        logging.error(f"Error processing upload: {str(e)}")
        return jsonify({
            'error': 'Error processing your order. Please try again.'
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
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(filepath)

@app.route('/admin/order/<int:order_id>/download/<path:filename>')
def download_order_image(order_id, filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(filepath, as_attachment=True)