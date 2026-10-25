from redis import Redis
from rq import Queue, Worker

from app.core.config import get_settings

QUEUE_NAME = "default"


def main() -> None:
    connection = Redis.from_url(get_settings().redis_url.get_secret_value())
    Worker([Queue(QUEUE_NAME, connection=connection)], connection=connection).work()


if __name__ == "__main__":
    main()
