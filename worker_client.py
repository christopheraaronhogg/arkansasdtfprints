#!/usr/bin/env python3
"""
Client interface to the image processing worker.
This module provides functions to submit tasks to the worker process
from the main Flask application.
"""

import os
import sys
import time
import logging
import threading
import importlib
import subprocess
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('worker_client')

# Ensure worker module is available
try:
    worker = importlib.import_module('worker')
    logger.info("Successfully imported worker module")
except ImportError:
    logger.warning("Could not import worker module directly, falling back to subprocess communication")
    worker = None

# Worker management
worker_process = None
worker_manager_process = None
initialization_lock = threading.Lock()
initialized = False

def ensure_worker_running():
    """Ensure that the worker process is running"""
    global worker_process, worker_manager_process, initialized
    
    # Use a lock to prevent multiple simultaneous initializations
    with initialization_lock:
        if initialized:
            return
        
        # Check if worker module is directly available (in-process mode)
        if worker:
            logger.info("Using in-process worker mode")
            # Start the worker thread if not already running
            if not hasattr(ensure_worker_running, 'worker_thread') or not ensure_worker_running.worker_thread.is_alive():
                ensure_worker_running.worker_thread = threading.Thread(
                    target=worker.worker_main,
                    daemon=True  # Make thread a daemon so it exits when main process exits
                )
                ensure_worker_running.worker_thread.start()
                logger.info("Started worker thread")
        else:
            # Out-of-process mode
            logger.info("Using out-of-process worker mode")
            try:
                # Start the worker manager process
                worker_manager_process = subprocess.Popen(
                    [sys.executable, 'worker_manager.py'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
                logger.info(f"Started worker manager process with PID {worker_manager_process.pid}")
                
                # Start thread to monitor manager output
                threading.Thread(
                    target=monitor_process_output,
                    args=(worker_manager_process, "[MANAGER]"),
                    daemon=True
                ).start()
            except Exception as e:
                logger.error(f"Failed to start worker manager: {str(e)}")
        
        initialized = True

def monitor_process_output(process, prefix):
    """Monitor and log output from a subprocess"""
    for line in process.stdout:
        line = line.rstrip()
        if line:
            logger.info(f"{prefix} {line}")

def add_task(task_type, data, priority=0):
    """Add a task to the worker's processing queue"""
    # Ensure worker is running
    ensure_worker_running()
    
    if worker:
        # In-process mode
        return worker.add_task(task_type, data, priority)
    else:
        # Since we're in out-of-process mode and don't have direct access to the worker,
        # we'll use a simple file-based approach to submit tasks
        logger.warning("Out-of-process task submission not fully implemented")
        logger.info(f"Would submit task: {task_type} with data: {data}")
        return f"task_{int(time.time())}"

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

# Initialize when module is imported
ensure_worker_running()