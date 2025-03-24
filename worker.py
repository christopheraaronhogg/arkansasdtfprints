"""
Image processing worker for Apparel Decorating Network
This process runs independently of the main Flask app and handles:
- Thumbnail generation
- Image validation and processing
- Background image tasks

Communication happens via Redis for production or filesystem-based queues for development.
"""

import os
import sys
import time
import json
import logging
import signal
import threading
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta
import traceback

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
exit_flag = False
task_path = Path("worker_tasks")
task_path.mkdir(exist_ok=True)

# Import shared modules that don't have circular dependencies
from storage import ObjectStorage
from utils import generate_thumbnail, get_thumbnail_key

# Initialize storage
try:
    storage = ObjectStorage()
    logger.info("Successfully initialized ObjectStorage")
except Exception as e:
    logger.error(f"Failed to initialize ObjectStorage: {str(e)}")
    raise

# Import database accessor that avoids circular imports
# We'll import the function at runtime to avoid circular imports
worker_db = None

class Task:
    """Represents a processing task with metadata"""
    def __init__(self, task_type, data, priority=0):
        self.task_type = task_type
        self.data = data
        self.priority = priority
        self.timestamp = time.time()
    
    def to_dict(self):
        """Convert task to dictionary for serialization"""
        return {
            'type': self.task_type,
            'data': self.data,
            'priority': self.priority,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create task from dictionary"""
        return cls(
            data.get('type', 'unknown'),
            data.get('data', {}),
            data.get('priority', 0)
        )

def process_thumbnail_task(file_key, storage_client):
    """Process a single thumbnail generation task"""
    try:
        logger.info(f"Processing thumbnail task for {file_key}")
        
        # Generate thumbnail key
        thumbnail_key = get_thumbnail_key(file_key)
        
        # Check if thumbnail exists already
        if storage_client.get_file(thumbnail_key):
            logger.info(f"Thumbnail already exists for {file_key}")
            return True
            
        # Get the original file
        file_data = storage_client.get_file(file_key)
        if not file_data:
            logger.error(f"Original file not found: {file_key}")
            return False
            
        # Generate the thumbnail
        thumb_data = generate_thumbnail(file_data)
        if not thumb_data:
            logger.error(f"Failed to generate thumbnail for {file_key}")
            return False
            
        # Save the thumbnail
        storage_client.upload_file(BytesIO(thumb_data), thumbnail_key)
        logger.info(f"Successfully generated thumbnail for {file_key}")
        
        return True
    except Exception as e:
        logger.error(f"Error processing thumbnail for {file_key}: {e}")
        return False

def process_batch_thumbnails_task(batch_file_keys, storage_client):
    """Process a batch of thumbnails"""
    successful = 0
    failed = 0
    
    for file_key in batch_file_keys:
        try:
            success = process_thumbnail_task(file_key, storage_client)
            if success:
                successful += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"Error processing batch thumbnail {file_key}: {e}")
            failed += 1
    
    logger.info(f"Batch processing complete: {successful} successful, {failed} failed")
    return successful > 0

def process_recent_orders_task(hours=24, max_thumbnails=20, storage_client=None):
    """Process thumbnails for recent orders"""
    if storage_client is None:
        storage_client = storage
    
    try:
        # Import here to avoid circular imports
        from worker_db import get_recent_orders
        
        # Get recent orders from database
        recent_orders = get_recent_orders(hours)
        
        if not recent_orders:
            logger.info("No recent orders found")
            return True
            
        logger.info(f"Processing thumbnails for {len(recent_orders)} recent orders")
        
        processed = 0
        for order in recent_orders:
            if processed >= max_thumbnails:
                break
                
            for item in order.get('items', []):
                if processed >= max_thumbnails:
                    break
                
                file_key = item.get('file_key')
                if not file_key:
                    continue
                    
                try:
                    success = process_thumbnail_task(file_key, storage_client)
                    if success:
                        processed += 1
                except Exception as e:
                    logger.error(f"Error processing thumbnail in recent orders: {e}")
        
        logger.info(f"Processed {processed} thumbnails from recent orders")
        return True
    except Exception as e:
        logger.error(f"Error processing recent orders: {e}")
        traceback.print_exc()
        return False

def process_task(task, storage_client):
    """Process a single task based on its type"""
    task_type = task.task_type
    task_data = task.data
    
    if task_type == 'thumbnail':
        file_key = task_data.get('file_key')
        if file_key:
            return process_thumbnail_task(file_key, storage_client)
    
    elif task_type == 'batch_thumbnails':
        file_keys = task_data.get('file_keys', [])
        if file_keys:
            return process_batch_thumbnails_task(file_keys, storage_client)
    
    elif task_type == 'recent_orders':
        hours = task_data.get('hours', 24)
        max_thumbnails = task_data.get('max_thumbnails', 20)
        return process_recent_orders_task(hours, max_thumbnails, storage_client)
    
    else:
        logger.warning(f"Unknown task type: {task_type}")
        return False
    
    return False

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global exit_flag
    logger.info(f"Received signal {sig}, shutting down worker...")
    exit_flag = True
    sys.exit(0)

def worker_main():
    """Main worker process function"""
    global exit_flag
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting image processing worker")
    
    # Main worker loop
    while not exit_flag:
        try:
            # Check for task files
            task_files = sorted(list(task_path.glob("task_*.json")))
            
            if task_files:
                # Process the oldest task first
                task_file = task_files[0]
                
                try:
                    # Read task
                    with open(task_file, 'r') as f:
                        task_data = json.load(f)
                    
                    # Process task
                    task = Task.from_dict(task_data)
                    logger.info(f"Processing task: {task.task_type}")
                    
                    success = process_task(task, storage)
                    
                    if success:
                        logger.info(f"Successfully processed task: {task.task_type}")
                    else:
                        logger.warning(f"Failed to process task: {task.task_type}")
                    
                    # Remove task file regardless of success to avoid permanent failures
                    task_file.unlink()
                
                except Exception as e:
                    logger.error(f"Error processing task file {task_file}: {e}")
                    # Move to a failed folder to avoid endless reprocessing
                    failed_dir = task_path / "failed"
                    failed_dir.mkdir(exist_ok=True)
                    
                    try:
                        task_file.rename(failed_dir / task_file.name)
                    except Exception:
                        # If rename fails, just delete
                        task_file.unlink(missing_ok=True)
            
            # Check for recent orders periodically (every 5 minutes)
            if time.time() % 300 < 5:  # Run approximately every 5 minutes
                process_recent_orders_task(hours=24, max_thumbnails=20)
            
            # Sleep to avoid CPU spinning
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error in worker main loop: {e}")
            # Sleep a bit longer after an error
            time.sleep(5)
    
    logger.info("Worker process exiting")

def add_task(task_type, data, priority=0):
    """Add a task to the processing queue"""
    task = Task(task_type, data, priority)
    
    # Save to a file in the task directory
    task_path.mkdir(exist_ok=True)
    task_file = task_path / f"task_{int(time.time() * 1000)}_{os.getpid()}.json"
    
    with open(task_file, 'w') as f:
        json.dump(task.to_dict(), f)
    
    return True

if __name__ == "__main__":
    worker_main()