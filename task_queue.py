import os
import logging
import time
import redis
from rq import Queue
from rq.retry import Retry
from rq.job import Job

logger = logging.getLogger(__name__)

# Get Redis URL from environment variable or use a default local Redis
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Try to connect to Redis, if unsuccessful, fallback to in-memory queue
try:
    # Initialize Redis connection
    redis_conn = redis.from_url(REDIS_URL)
    # Test the connection
    redis_conn.ping()
    
    # Initialize RQ queue with Redis
    queue = Queue(connection=redis_conn, default_timeout=600)  # 10-minute timeout for jobs
    logger.info("Successfully connected to Redis for task queue")
    
    # Flag to track if we're using Redis
    using_redis = True
except Exception as e:
    logger.warning(f"Could not connect to Redis: {str(e)}. Using in-memory task queue instead.")
    # Fallback to a simple in-memory queue for development/testing
    class InMemoryQueue:
        def __init__(self):
            self.jobs = []
        
        def enqueue(self, func, *args, retry=None, **kwargs):
            # Execute job immediately in the same thread
            try:
                result = func(*args, **kwargs)
                logger.info(f"Executed job in-memory: {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Failed to execute job in-memory: {func.__name__}, Error: {str(e)}")
                # Implement simple retry logic
                if retry and isinstance(retry, Retry):
                    for attempt in range(retry.max, 0, -1):
                        logger.info(f"Retrying job in-memory, attempt {retry.max - attempt + 1}")
                        try:
                            time.sleep(2)  # Simple backoff
                            result = func(*args, **kwargs)
                            return result
                        except Exception as retry_e:
                            logger.error(f"Retry attempt failed: {str(retry_e)}")
                    logger.error("All retry attempts failed")
                return None
    
    queue = InMemoryQueue()
    using_redis = False

def enqueue_email_task(func, *args, **kwargs):
    """
    Enqueue an email sending task to the queue with retry capabilities.
    
    Args:
        func: The function to execute
        *args: Arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        Job object if using Redis, or the result if using in-memory queue
    """
    retry_config = Retry(max=3, interval=[10, 30, 60])  # Retry up to 3 times with increasing intervals
    
    try:
        job = queue.enqueue(
            func,
            *args,
            retry=retry_config,
            **kwargs
        )
        logger.info(f"Enqueued email task: {func.__name__}")
        return job
    except Exception as e:
        logger.error(f"Failed to enqueue task: {str(e)}")
        # If we can't enqueue, try to execute directly as a last resort
        try:
            logger.warning(f"Attempting to execute email task directly: {func.__name__}")
            return func(*args, **kwargs)
        except Exception as direct_e:
            logger.error(f"Direct execution of email task failed: {str(direct_e)}")
            return None

def get_job_status(job_id):
    """
    Get the status of a job by its ID (only works with Redis queue)
    
    Args:
        job_id: The ID of the job
        
    Returns:
        Status string if using Redis, or None if using in-memory queue
    """
    if not using_redis:
        return "unavailable (in-memory queue)"
    
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        return job.get_status()
    except Exception as e:
        logger.error(f"Failed to fetch job status: {str(e)}")
        return "unknown"