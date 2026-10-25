"""Exit 0 only if at least one worker is listening on the default queue."""

import sys

from redis import Redis
from rq import Queue, Worker

from app.core.config import get_settings
from app.jobs.worker import QUEUE_NAME


def main() -> int:
    connection = Redis.from_url(get_settings().redis_url.get_secret_value(), socket_timeout=3)
    return 0 if Worker.count(queue=Queue(QUEUE_NAME, connection=connection)) > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
