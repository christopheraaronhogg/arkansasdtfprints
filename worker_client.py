"""
Client interface to the image processing worker.
This module provides functions to submit tasks to the worker process
from the main Flask application.
"""

import os
import sys
import subprocess
import threading
import logging
import time
import json
import queue
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
task_queue = queue.Queue()
worker_manager_process = None
worker_thread = None
worker_running = False

def ensure_worker_running():
    """Ensure that the worker process is running"""
    global worker_manager_process, worker_thread, worker_running
    
    if worker_running and worker_manager_process and worker_manager_process.poll() is None:
        return True  # Worker is already running
    
    try:
        # Start the worker manager process
        worker_manager_process = subprocess.Popen(
            [sys.executable, 'worker_manager.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Start a thread to monitor the output
        if worker_thread is None:
            worker_thread = threading.Thread(
                target=monitor_process_output, 
                args=(worker_manager_process, "[MANAGER] "),
                daemon=True
            )
            worker_thread.start()
        
        worker_running = True
        logger.info("Started worker manager process with PID %d", worker_manager_process.pid)
        return True
    except Exception as e:
        logger.error(f"Failed to start worker manager: {str(e)}")
        return False

def monitor_process_output(process, prefix):
    """Monitor and log output from a subprocess"""
    while True:
        try:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
                
            if line:
                logger.info(f"{prefix}{line.rstrip()}")
        except Exception as e:
            logger.error(f"Error reading process output: {str(e)}")
            break
    
    logger.warning(f"Process monitoring thread exiting (return code: {process.returncode})")

def add_task(task_type, data, priority=0):
    """Add a task to the worker's processing queue"""
    try:
        # Ensure the worker is running
        if not ensure_worker_running():
            logger.error("Cannot add task, worker is not running")
            return False
        
        # Create task data
        task = {
            'type': task_type,
            'data': data,
            'priority': priority,
            'timestamp': time.time()
        }
        
        # Add task to the queue
        # In a more sophisticated setup, this would use IPC, Redis, or another
        # message queue to communicate with the worker process
        task_queue.put(task)
        
        # For now, we'll use a simple file-based approach
        # This is not ideal for production but works for our demo
        task_path = Path("worker_tasks")
        task_path.mkdir(exist_ok=True)
        
        # Write task to a file
        task_file = task_path / f"task_{int(time.time() * 1000)}_{os.getpid()}.json"
        with open(task_file, 'w') as f:
            json.dump(task, f)
        
        return True
    except Exception as e:
        logger.error(f"Error adding task to worker: {str(e)}")
        return False

def submit_thumbnail_task(file_key, priority=0):
    """Submit a task to generate a thumbnail for a specific file"""
    return add_task('thumbnail', {'file_key': file_key}, priority)

def submit_batch_thumbnails_task(file_keys, priority=0):
    """Submit a task to generate thumbnails for multiple files"""
    return add_task('batch_thumbnails', {'file_keys': file_keys}, priority)

def submit_recent_orders_task(hours=24, max_thumbnails=20, priority=0):
    """Submit a task to process thumbnails for recent orders"""
    return add_task('recent_orders', {
        'hours': hours,
        'max_thumbnails': max_thumbnails
    }, priority)

# Start the worker process when this module is imported
ensure_worker_running()