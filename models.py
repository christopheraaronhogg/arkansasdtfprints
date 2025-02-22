from datetime import datetime
from database import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    invoice_number = db.Column(db.String(50), nullable=True)
    po_number = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=False)
    total_cost = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'order_number': self.order_number,
            'invoice_number': self.invoice_number,
            'po_number': self.po_number,
            'email': self.email,
            'total_cost': f"${self.total_cost:.2f}",
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    file_key = db.Column(db.String(255), nullable=False)
    width_inches = db.Column(db.Float, nullable=False)
    height_inches = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    cost = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    def format_dimensions(self):
        return f"{self.width_inches:.2f}\" × {self.height_inches:.2f}\""

    def to_dict(self):
        return {
            'id': self.id,
            'file_key': self.file_key,
            'dimensions': self.format_dimensions(),
            'quantity': self.quantity,
            'cost': f"${self.cost:.2f}",
            'notes': self.notes or ''
        }