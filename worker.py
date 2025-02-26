import os
import redis
from rq import Worker, Queue
from redis import Redis

listen = ['emails']
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
conn = redis.from_url(redis_url)

if __name__ == '__main__':
    with conn:
        worker = Worker([Queue('emails', connection=conn)])
        worker.work()