from datetime import datetime
from app import db

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    file_key = db.Column(db.String(255), nullable=False)
    width_inches = db.Column(db.Float, nullable=False)
    height_inches = db.Column(db.Float, nullable=False)
    total_cost = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'order_number': self.order_number,
            'email': self.email,
            'dimensions': f"{self.width_inches}\" x {self.height_inches}\"",
            'total_cost': f"${self.total_cost:.2f}",
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
