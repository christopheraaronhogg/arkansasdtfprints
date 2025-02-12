from app import app, db
from models import Order, OrderItem
from config import Config
import math

def round_dimension(dimension):
    # Round up if decimal is .495 or higher (accounts for floating point precision)
    return max(1, int((dimension * 2 + 1.01) // 2))  # Changed from +1 to +1.01

def update_order_costs():
    with app.app_context():
        # Get all orders
        orders = Order.query.all()
        print(f"Found {len(orders)} orders to update")

        for order in orders:
            # Recalculate total cost from items
            new_total = 0
            for item in order.items:
                # Round dimensions using fixed rounding
                width = round_dimension(item.width_inches)
                height = round_dimension(item.height_inches)
                
                # Add debug logging
                print(f"Original dimensions: {item.width_inches} x {item.height_inches}")
                print(f"Rounded dimensions: {width} x {height}")
                print(f"Rounding steps: {item.width_inches} -> {width}, {item.height_inches} -> {height}")
                
                # Calculate area and cost
                area = width * height
                item_cost = area * Config.COST_PER_SQINCH * item.quantity
                item.cost = item_cost
                new_total += item_cost
                
                print(f"Item cost: ${item_cost:.2f} (area: {area} sq in, qty: {item.quantity})")
            
            # Update order total
            old_total = order.total_cost
            order.total_cost = new_total
            print(f"Order {order.order_number}: ${old_total:.2f} -> ${new_total:.2f}\n")

        # Commit all changes
        db.session.commit()
        print("All orders updated successfully")

if __name__ == "__main__":
    update_order_costs() 