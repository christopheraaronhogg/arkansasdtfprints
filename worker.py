import os
import redis
from rq import Worker, Queue
from redis import Redis

listen = ['emails']

# Use TCP connection for Redis
redis_conn = Redis(host='localhost', port=6379, db=0)

if __name__ == '__main__':
    with redis_conn:
        worker = Worker([Queue('emails', connection=redis_conn)])
        worker.work()