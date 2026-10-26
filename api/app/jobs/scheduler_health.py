"""Exit 0 only if the scheduler process is still PID 1 of its container and Redis answers.
Simple on purpose: it proves the process is alive and can reach its queue, not that a job ran."""

import sys
from pathlib import Path

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

SCHEDULER_MODULE = b"app.jobs.scheduler"


def scheduler_is_pid_1(cmdline_file: Path = Path("/proc/1/cmdline")) -> bool:
    try:
        arguments = cmdline_file.read_bytes().split(b"\0")
    except OSError:
        return False
    return SCHEDULER_MODULE in arguments


def redis_answers(url: str) -> bool:
    try:
        return bool(Redis.from_url(url, socket_connect_timeout=3, socket_timeout=3).ping())
    except (RedisError, OSError):
        return False


def main() -> int:
    ok = scheduler_is_pid_1() and redis_answers(get_settings().redis_url.get_secret_value())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
