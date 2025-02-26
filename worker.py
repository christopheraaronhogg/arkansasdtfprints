import os
import redis
from rq import Worker, Queue
from redis import Redis

listen = ['emails']

# Use Unix socket for Redis connection
redis_conn = Redis(unix_socket_path='/tmp/redis.sock', db=0)

if __name__ == '__main__':
    with redis_conn:
        worker = Worker([Queue('emails', connection=redis_conn)])
        worker.work()