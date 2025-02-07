import os
import logging
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from sqlalchemy.orm import DeclarativeBase

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

from models import Order
from utils import allowed_file, generate_order_number, calculate_cost, get_image_dimensions, validate_image

with app.app_context():
    # Import models and create tables
    db.create_all()
    logging.info("Database tables created successfully")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    email = request.form.get('email')
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only PNG files are allowed'}), 400
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Validate image
        is_valid, message = validate_image(filepath)
        if not is_valid:
            os.remove(filepath)
            return jsonify({'error': message}), 400
        
        # Get dimensions and calculate cost
        width_inches, height_inches = get_image_dimensions(filepath)
        total_cost = calculate_cost(width_inches, height_inches)
        
        # Create order
        order = Order(
            order_number=generate_order_number(),
            email=email,
            file_key=filename,
            width_inches=width_inches,
            height_inches=height_inches,
            total_cost=total_cost
        )
        
        db.session.add(order)
        db.session.commit()
        
        # Send confirmation email
        msg = Message(
            'DTF Printing Order Confirmation',
            sender='noreply@dtfprinting.com',
            recipients=[email]
        )
        msg.body = f'''
        Thank you for your DTF printing order!
        Order Number: {order.order_number}
        Dimensions: {width_inches:.2f}" x {height_inches:.2f}"
        Total Cost: ${total_cost:.2f}
        
        We will process your order shortly.
        '''
        mail.send(msg)
        
        return jsonify(order.to_dict()), 200
        
    except Exception as e:
        logging.error(f"Error processing upload: {str(e)}")
        return jsonify({'error': 'Error processing upload'}), 500