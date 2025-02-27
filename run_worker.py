#!/usr/bin/env python
"""
Redis Queue worker script for processing background tasks.
Run this script separately to ensure emails are processed even when the web application is idle.
"""

import os
import sys
import logging
from redis import Redis
from rq import Worker, Queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Import configuration
from config import Config

def main():
    logger.info("Starting RQ email worker...")

    # Connect to Redis
    try:
        redis_url = Config.REDIS_URL
        redis_conn = Redis.from_url(redis_url)

        # Create a worker listening on the 'emails' queue
        worker = Worker(['emails'], connection=redis_conn)
        logger.info(f"Worker listening to queue: emails")

        # Start the worker
        worker.work(with_scheduler=True)
    except Exception as e:
        logger.error(f"Worker failed: {str(e)}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())