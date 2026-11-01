"""Delete expired reports (with their runs), old finished runs without a report, old ai_calls and
old email tokens.
`python -m app.jobs.purge` runs it once by hand; the scheduler (app/jobs/scheduler.py) runs it
daily.
It uses DATABASE_URL, which is the app role in compose (DECISIONS #118)."""

import logging

from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.db.session import get_engine
from app.services.purge import PurgePass, purge_expired
from app.storage import LocalDiskStorage


def purge() -> PurgePass:
    settings = get_settings()
    storage = LocalDiskStorage(settings.storage_dir)
    with Session(get_engine(settings.database_url.get_secret_value())) as db:
        return purge_expired(db, storage, settings.limits, clock.utcnow())


def purge_expired_job() -> int:
    """The RQ job: returns how many rows were deleted."""
    done = purge()
    return done.total


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    purge_expired_job()


if __name__ == "__main__":
    main()
