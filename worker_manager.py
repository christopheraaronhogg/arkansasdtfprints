"""
Worker process manager for image processing.
This script starts and monitors the image processing worker.
It automatically restarts the worker if it crashes or exits unexpectedly.
"""

import os
import sys
import subprocess
import threading
import time
import logging
import signal

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
worker_process = None
exit_flag = False
restart_count = 0
max_restarts = 5  # Max restarts per hour
restart_timer = None

def restart_count_monitor():
    """Reset restart count after an hour to prevent endless restarts"""
    global restart_count
    restart_count = 0
    logger.info("Reset worker restart count")

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global exit_flag, worker_process
    logger.info(f"Received signal {sig}, shutting down worker manager...")
    exit_flag = True
    
    if worker_process:
        try:
            worker_process.terminate()
            # Give it a moment to shut down gracefully
            time.sleep(1)
            if worker_process.poll() is None:
                worker_process.kill()
        except Exception as e:
            logger.error(f"Error terminating worker process: {str(e)}")
    
    sys.exit(0)

def start_worker():
    """Start the worker process and return subprocess handle"""
    try:
        logger.info("Starting image processing worker")
        process = subprocess.Popen(
            [sys.executable, 'worker.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        logger.info(f"Started worker process with PID {process.pid}")
        return process
    except Exception as e:
        logger.error(f"Failed to start worker process: {str(e)}")
        return None

def monitor_worker_output(process):
    """Monitor and log output from the worker process"""
    while process and not exit_flag:
        try:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
                
            if line:
                logger.info(f"[WORKER] {line.rstrip()}")
        except Exception as e:
            logger.error(f"Error reading worker output: {str(e)}")
            break

def check_worker(process):
    """Check if worker process is still running, return True if alive"""
    if process is None:
        return False
    
    return process.poll() is None

def main():
    """Main function for the worker manager"""
    global worker_process, restart_count, restart_timer, exit_flag
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting image processing worker manager")
    
    # Start the restart count monitor
    restart_timer = threading.Timer(3600, restart_count_monitor)
    restart_timer.daemon = True
    restart_timer.start()
    
    while not exit_flag:
        # Start worker if not running
        if worker_process is None or worker_process.poll() is not None:
            if worker_process is not None:
                # Worker exited
                exit_code = worker_process.poll()
                logger.warning(f"Worker process not running (exit code: {exit_code}), restarting...")
                
                # Increment restart count and check if we've restarted too many times
                restart_count += 1
                if restart_count > max_restarts:
                    logger.error(f"Too many worker restarts ({restart_count}), waiting for one hour")
                    time.sleep(3600)  # Wait an hour before trying again
                    restart_count = 0
            
            # Start a new worker process
            worker_process = start_worker()
            
            if worker_process:
                # Start output monitoring thread
                monitor_thread = threading.Thread(
                    target=monitor_worker_output,
                    args=(worker_process,),
                    daemon=True
                )
                monitor_thread.start()
        
        # Sleep a bit to avoid CPU spinning
        time.sleep(3)
    
    logger.info("Worker manager exiting")

if __name__ == "__main__":
    main()