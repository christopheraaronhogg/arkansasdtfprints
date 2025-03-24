"""
Database migration script to add indexes to existing tables
This script will add performance indexes to the Order and OrderItem tables
"""
import logging
from app import app, db
from models import Order, OrderItem
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_indexes():
    """Add indexes to database tables"""
    with app.app_context():
        try:
            # Check if the migration is needed
            conn = db.engine.connect()
            
            # Check for existing indexes on Order table
            result = conn.execute(text(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'order'"))
            existing_indexes = {row[0] for row in result}
            
            logger.info("Existing indexes on Order table: %s", existing_indexes)
            
            # Order table indexes (if they don't already exist)
            indexes_to_create = [
                ("ix_order_order_number", "CREATE INDEX IF NOT EXISTS ix_order_order_number ON \"order\" (order_number)"),
                ("ix_order_invoice_number", "CREATE INDEX IF NOT EXISTS ix_order_invoice_number ON \"order\" (invoice_number)"),
                ("ix_order_email", "CREATE INDEX IF NOT EXISTS ix_order_email ON \"order\" (email)"),
                ("ix_order_status", "CREATE INDEX IF NOT EXISTS ix_order_status ON \"order\" (status)"),
                ("ix_order_created_at", "CREATE INDEX IF NOT EXISTS ix_order_created_at ON \"order\" (created_at)"),
                ("idx_order_status_created", "CREATE INDEX IF NOT EXISTS idx_order_status_created ON \"order\" (status, created_at)")
            ]
            
            for idx_name, idx_sql in indexes_to_create:
                if idx_name.lower() not in [idx.lower() for idx in existing_indexes]:
                    logger.info("Creating index: %s", idx_name)
                    conn.execute(text(idx_sql))
                else:
                    logger.info("Index already exists: %s", idx_name)
                    
            # Check for existing indexes on OrderItem table
            result = conn.execute(text(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'order_item'"))
            existing_indexes = {row[0] for row in result}
            
            logger.info("Existing indexes on OrderItem table: %s", existing_indexes)
            
            # OrderItem table indexes (if they don't already exist)
            indexes_to_create = [
                ("ix_order_item_order_id", "CREATE INDEX IF NOT EXISTS ix_order_item_order_id ON order_item (order_id)"),
                ("ix_order_item_file_key", "CREATE INDEX IF NOT EXISTS ix_order_item_file_key ON order_item (file_key)"),
                ("idx_orderitem_order_file", "CREATE INDEX IF NOT EXISTS idx_orderitem_order_file ON order_item (order_id, file_key)")
            ]
            
            for idx_name, idx_sql in indexes_to_create:
                if idx_name.lower() not in [idx.lower() for idx in existing_indexes]:
                    logger.info("Creating index: %s", idx_name)
                    conn.execute(text(idx_sql))
                else:
                    logger.info("Index already exists: %s", idx_name)
                    
            # Commit the transaction
            conn.commit()
            conn.close()
            
            logger.info("Successfully added all indexes")
            
        except Exception as e:
            logger.error("Error adding indexes: %s", str(e))
            raise

if __name__ == "__main__":
    create_indexes()