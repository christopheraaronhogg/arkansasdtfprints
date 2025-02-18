from datetime import datetime
from app import db

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    invoice_number = db.Column(db.String(50), nullable=True)
    po_number = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=False)
    total_cost = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
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