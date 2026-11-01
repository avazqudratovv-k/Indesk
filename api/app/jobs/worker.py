from redis import Redis
from rq import Queue, Worker

from app.core.config import get_settings
from app.email.factory import check_worker_ready

QUEUE_NAME = "default"


def main() -> None:
    settings = get_settings()
    check_worker_ready(settings)  # production: no key or from-address, no start
    connection = Redis.from_url(settings.redis_url.get_secret_value())
    Worker([Queue(QUEUE_NAME, connection=connection)], connection=connection).work()


if __name__ == "__main__":
    main()
