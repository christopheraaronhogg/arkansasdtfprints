#!/usr/bin/env python3
"""
Worker process manager for image processing.
This script starts and monitors the image processing worker.
It automatically restarts the worker if it crashes or exits unexpectedly.
"""

import os
import sys
import time
import signal
import logging
import subprocess
import threading
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('worker_manager')

# Configuration
WORKER_SCRIPT = 'worker.py'
CHECK_INTERVAL = 5  # seconds between checking worker status
MAX_RESTART_ATTEMPTS = 10  # Maximum number of restart attempts per hour
RESTART_COOLDOWN = 60  # seconds to wait after a restart

# Worker process management
worker_process = None
restart_count = 0
last_restart_time = None
manager_running = True

def restart_count_monitor():
    """Reset restart count after an hour to prevent endless restarts"""
    global restart_count
    while manager_running:
        time.sleep(3600)  # 1 hour
        if restart_count > 0:
            logger.info(f"Resetting restart count from {restart_count} to 0")
            restart_count = 0

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global manager_running
    logger.info(f"Received signal {sig}, shutting down worker manager...")
    manager_running = False
    
    # Terminate worker process if running
    if worker_process:
        logger.info("Sending termination signal to worker process...")
        worker_process.terminate()
        try:
            worker_process.wait(timeout=10)
            logger.info("Worker process terminated gracefully")
        except subprocess.TimeoutExpired:
            logger.warning("Worker process did not terminate in time, forcing kill")
            worker_process.kill()

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def start_worker():
    """Start the worker process and return subprocess handle"""
    global restart_count, last_restart_time
    
    # Check if we've restarted too many times
    current_time = time.time()
    if restart_count >= MAX_RESTART_ATTEMPTS:
        if last_restart_time and (current_time - last_restart_time) < 3600:
            logger.error(f"Too many restart attempts ({restart_count}), waiting for cooldown period")
            time.sleep(RESTART_COOLDOWN)
    
    # Update restart tracking
    restart_count += 1
    last_restart_time = current_time
    
    # Start the worker process
    try:
        process = subprocess.Popen([sys.executable, WORKER_SCRIPT],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,
                                   universal_newlines=True,
                                   bufsize=1)  # Line-buffered
        logger.info(f"Started worker process with PID {process.pid}")
        
        # Start thread to monitor worker output
        threading.Thread(target=monitor_worker_output, 
                        args=(process,), 
                        daemon=True).start()
        
        return process
    
    except Exception as e:
        logger.error(f"Failed to start worker process: {str(e)}")
        return None

def monitor_worker_output(process):
    """Monitor and log output from the worker process"""
    for line in process.stdout:
        # Strip newline and output to manager's log
        line = line.rstrip()
        if line:
            logger.info(f"[WORKER] {line}")

def check_worker(process):
    """Check if worker process is still running, return True if alive"""
    if process is None:
        return False
    
    return process.poll() is None

def main():
    """Main function for the worker manager"""
    global worker_process, manager_running
    
    logger.info("Starting image processing worker manager")
    
    # Start restart count monitor thread
    threading.Thread(target=restart_count_monitor, daemon=True).start()
    
    # Initial worker start
    worker_process = start_worker()
    
    # Main monitoring loop
    while manager_running:
        if not check_worker(worker_process):
            exit_code = worker_process.returncode if worker_process else "N/A"
            logger.warning(f"Worker process not running (exit code: {exit_code}), restarting...")
            
            # Wait a bit before restarting to prevent rapid restart loops
            time.sleep(RESTART_COOLDOWN)
            
            # Restart the worker
            worker_process = start_worker()
        
        # Sleep before next check
        time.sleep(CHECK_INTERVAL)
    
    logger.info("Worker manager shutting down")

if __name__ == "__main__":
    main()