#!/usr/bin/env python3
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
from io import BytesIO
import threading
import queue
import signal
import traceback
from datetime import datetime, timedelta
import sqlite3

# Setup logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('image_worker')

# Import app-specific modules
from utils import generate_thumbnail, get_thumbnail_key
from storage import ObjectStorage
from models import Order, OrderItem
from app import db, app

# Global task queue
task_queue = queue.Queue()
WORKER_RUNNING = True
POLL_INTERVAL = 5  # seconds between checking for new tasks
MAX_RETRIES = 3    # Maximum attempts for failed tasks

# Default batch sizes
DEFAULT_BATCH_SIZE = 10

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global WORKER_RUNNING
    logger.info(f"Received signal {sig}, shutting down worker...")
    WORKER_RUNNING = False

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

class Task:
    """Represents a processing task with metadata"""
    def __init__(self, task_type, data, priority=0):
        self.id = f"task_{int(time.time())}_{hash(str(data))}"
        self.type = task_type  # 'thumbnail', 'validate', etc.
        self.data = data       # Task-specific data
        self.priority = priority  # Higher number = higher priority
        self.attempts = 0
        self.created_at = datetime.now()
        self.status = 'pending'
        self.result = None
        self.error = None
    
    def to_dict(self):
        """Convert task to dictionary for serialization"""
        return {
            'id': self.id,
            'type': self.type,
            'data': self.data,
            'priority': self.priority,
            'attempts': self.attempts,
            'created_at': self.created_at.isoformat(),
            'status': self.status,
            'result': self.result,
            'error': self.error
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create task from dictionary"""
        task = cls(data['type'], data['data'], data['priority'])
        task.id = data['id']
        task.attempts = data['attempts']
        task.created_at = datetime.fromisoformat(data['created_at'])
        task.status = data['status']
        task.result = data['result']
        task.error = data['error']
        return task

def process_thumbnail_task(file_key, storage_client):
    """Process a single thumbnail generation task"""
    logger.info(f"Processing thumbnail for {file_key}")
    thumbnail_key = get_thumbnail_key(file_key)
    
    try:
        # Check if thumbnail already exists
        if storage_client.get_file(thumbnail_key):
            logger.info(f"Thumbnail already exists for {file_key}")
            return {'success': True, 'existed': True, 'thumbnail_key': thumbnail_key}
        
        # Get original file
        file_data = storage_client.get_file(file_key)
        if not file_data:
            logger.error(f"Original file not found: {file_key}")
            return {'success': False, 'error': 'Original file not found'}
        
        # Generate thumbnail
        thumb_data = generate_thumbnail(file_data)
        if not thumb_data:
            logger.error(f"Failed to generate thumbnail for {file_key}")
            return {'success': False, 'error': 'Thumbnail generation failed'}
        
        # Upload thumbnail
        if storage_client.upload_file(BytesIO(thumb_data), thumbnail_key):
            logger.info(f"Successfully generated and uploaded thumbnail for {file_key}")
            return {'success': True, 'existed': False, 'thumbnail_key': thumbnail_key}
        else:
            logger.error(f"Failed to upload thumbnail for {file_key}")
            return {'success': False, 'error': 'Failed to upload thumbnail'}
    
    except Exception as e:
        error_msg = f"Error processing thumbnail for {file_key}: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return {'success': False, 'error': error_msg}

def process_batch_thumbnails_task(batch_file_keys, storage_client):
    """Process a batch of thumbnails"""
    results = []
    
    for file_key in batch_file_keys:
        result = process_thumbnail_task(file_key, storage_client)
        results.append({
            'file_key': file_key,
            'result': result
        })
    
    return {
        'success': True,
        'results': results,
        'successful': sum(1 for r in results if r['result']['success']),
        'failed': sum(1 for r in results if not r['result']['success'])
    }

def process_recent_orders_task(hours=24, max_thumbnails=20, storage_client=None):
    """Process thumbnails for recent orders"""
    if storage_client is None:
        storage_client = ObjectStorage()
    
    with app.app_context():
        try:
            logger.info(f"Processing thumbnails for orders from the last {hours} hours")
            # Get recent orders
            recent_orders = Order.query.filter(
                Order.created_at >= datetime.now() - timedelta(hours=hours)
            ).order_by(Order.created_at.desc()).all()
            
            logger.info(f"Found {len(recent_orders)} recent orders")
            
            # Track thumbnails to process
            thumbnails_to_process = []
            ordered_file_keys = []
            
            # Find files that need thumbnails
            for order in recent_orders:
                if len(thumbnails_to_process) >= max_thumbnails:
                    break
                
                for item in order.items:
                    file_key = item.file_key
                    thumbnail_key = get_thumbnail_key(file_key)
                    
                    # Check if thumbnail already exists
                    if storage_client.get_file(thumbnail_key):
                        continue
                    
                    # Add to processing list if not already included
                    if file_key not in thumbnails_to_process:
                        thumbnails_to_process.append(file_key)
                        ordered_file_keys.append(file_key)
                    
                    if len(thumbnails_to_process) >= max_thumbnails:
                        break
            
            # Process all thumbnails
            results = []
            processed_count = 0
            
            for file_key in ordered_file_keys:
                result = process_thumbnail_task(file_key, storage_client)
                results.append({
                    'file_key': file_key,
                    'result': result
                })
                
                if result['success'] and not result.get('existed', False):
                    processed_count += 1
            
            logger.info(f"Processed {processed_count} new thumbnails from recent orders")
            
            return {
                'success': True,
                'thumbnail_count': len(thumbnails_to_process),
                'processed_new': processed_count,
                'results': results
            }
        
        except Exception as e:
            error_msg = f"Error processing recent orders: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return {'success': False, 'error': error_msg}

def process_task(task, storage_client):
    """Process a single task based on its type"""
    logger.info(f"Processing task {task.id} of type {task.type}")
    
    try:
        # Increment attempt counter
        task.attempts += 1
        task.status = 'processing'
        
        # Process task based on type
        if task.type == 'thumbnail':
            file_key = task.data.get('file_key')
            if file_key:
                result = process_thumbnail_task(file_key, storage_client)
                task.result = result
                task.status = 'completed' if result['success'] else 'failed'
            else:
                task.status = 'failed'
                task.error = 'Missing file_key in task data'
        
        elif task.type == 'batch_thumbnails':
            batch_file_keys = task.data.get('file_keys', [])
            if batch_file_keys:
                result = process_batch_thumbnails_task(batch_file_keys, storage_client)
                task.result = result
                task.status = 'completed' if result['success'] else 'failed'
            else:
                task.status = 'failed'
                task.error = 'Missing or empty file_keys in task data'
        
        elif task.type == 'recent_orders':
            hours = task.data.get('hours', 24)
            max_thumbnails = task.data.get('max_thumbnails', 20)
            result = process_recent_orders_task(hours, max_thumbnails, storage_client)
            task.result = result
            task.status = 'completed' if result['success'] else 'failed'
        
        else:
            task.status = 'failed'
            task.error = f"Unknown task type: {task.type}"
        
    except Exception as e:
        task.status = 'failed'
        task.error = f"Error processing task: {str(e)}"
        logger.error(f"Error processing task {task.id}: {str(e)}")
        logger.error(traceback.format_exc())
    
    return task

def worker_main():
    """Main worker process function"""
    logger.info("Starting image processing worker...")
    
    # Initialize storage client
    storage_client = ObjectStorage()
    logger.info("Storage client initialized")
    
    # Main worker loop
    while WORKER_RUNNING:
        try:
            # First check if we have any tasks in the queue
            try:
                task = task_queue.get(block=False)
                logger.info(f"Got task from queue: {task.id} ({task.type})")
                
                # Process the task
                updated_task = process_task(task, storage_client)
                
                # Handle failed tasks
                if updated_task.status == 'failed' and updated_task.attempts < MAX_RETRIES:
                    logger.warning(f"Task {updated_task.id} failed, retrying later (attempt {updated_task.attempts}/{MAX_RETRIES})")
                    # Add back to queue with delay based on attempt count
                    retry_delay = 2 ** updated_task.attempts  # Exponential backoff
                    threading.Timer(retry_delay, lambda t=updated_task: task_queue.put(t)).start()
                else:
                    # Task completed or max retries reached
                    if updated_task.status == 'failed':
                        logger.error(f"Task {updated_task.id} failed after {updated_task.attempts} attempts")
                    else:
                        logger.info(f"Task {updated_task.id} completed successfully")
                
                # Mark task as done in the queue
                task_queue.task_done()
                continue
            
            except queue.Empty:
                # No tasks in memory queue, proceed to check for periodic tasks
                pass
            
            # Check if it's time to process recent orders
            # This is a periodic task that runs even if no explicit tasks are queued
            with app.app_context():
                # Process recent orders every 5 minutes
                periodic_task = Task('recent_orders', {
                    'hours': 24,
                    'max_thumbnails': 20
                })
                process_task(periodic_task, storage_client)
            
            # Sleep before next iteration
            time.sleep(POLL_INTERVAL)
        
        except Exception as e:
            logger.error(f"Error in worker main loop: {str(e)}")
            logger.error(traceback.format_exc())
            # Sleep a bit to avoid tight error loops
            time.sleep(5)
    
    logger.info("Worker process shutting down")

def add_task(task_type, data, priority=0):
    """Add a task to the processing queue"""
    task = Task(task_type, data, priority)
    task_queue.put(task)
    logger.info(f"Added task {task.id} of type {task.type} to queue")
    return task.id

if __name__ == "__main__":
    # Run the worker process
    worker_main()