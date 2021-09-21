import sys

from redis import Redis
from rq import Connection, Queue, Worker
from rq import get_current_job


def custom_handler(job, exc_type, exc_value, traceback):
    try:
        print("Killing tatt")
        process = job.meta["bug_handler"]
        if process and hasattr(process, "terminate"):
            process.terminate()
            process.kill()
    except Exception as e:
        raise e


redis_connection = Redis(host="", password="")

with Connection(redis_connection):
    q = Queue(sys.argv[1])
    try:
        w = Worker([q])
        w.push_exc_handler(custom_handler)
        w.work()
    except Exception as e:
        process = get_current_job().meta["bug_handler"]
        if process and hasattr(process, "terminate"):
            process.terminate()
            process.kill()
