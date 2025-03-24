"""
Database access layer for the worker process.
This module avoids circular import issues by providing a clean interface
to database models for the worker process.
"""

import os
import sys
import logging
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_recent_orders(hours=24):
    """
    Get recent orders from the database.
    This function is called by the worker to find images that need thumbnails.
    """
    try:
        # Import here to avoid circular imports
        from app import app, db
        from models import Order
        
        with app.app_context():
            recent_orders = Order.query.filter(
                Order.created_at >= datetime.now() - timedelta(hours=hours)
            ).order_by(Order.created_at.desc()).all()
            
            # Convert to simple dictionaries to avoid SQLAlchemy session issues
            result = []
            for order in recent_orders:
                order_dict = {
                    'id': order.id,
                    'order_number': order.order_number,
                    'created_at': order.created_at.isoformat() if order.created_at else None,
                    'items': []
                }
                
                for item in order.items:
                    item_dict = {
                        'id': item.id,
                        'file_key': item.file_key,
                        'width_inches': item.width_inches,
                        'height_inches': item.height_inches,
                        'quantity': item.quantity
                    }
                    order_dict['items'].append(item_dict)
                
                result.append(order_dict)
            
            return result
    except Exception as e:
        logger.error(f"Error getting recent orders: {str(e)}")
        return []