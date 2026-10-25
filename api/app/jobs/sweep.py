"""Delete the stored files of expired uploads. `python -m app.jobs.sweep` runs it once by hand;
the scheduler (app/jobs/scheduler.py) runs it every limits.sweep_interval_seconds."""

import logging

from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.db.session import get_engine
from app.services.uploads import SweepResult, sweep_expired_uploads
from app.storage import LocalDiskStorage

logger = logging.getLogger("indesk.sweep")


def sweep() -> SweepResult:
    settings = get_settings()
    storage = LocalDiskStorage(settings.storage_dir)
    with Session(get_engine(settings.database_url.get_secret_value())) as db:
        return sweep_expired_uploads(db, storage, clock.utcnow())


def run_sweep() -> int:
    """The RQ job: returns how many uploads were deleted."""
    result = sweep()
    logger.info(
        "upload sweep: deleted=%d in_use=%d failed=%d", result.deleted, result.in_use, result.failed
    )
    return result.deleted


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run_sweep()


if __name__ == "__main__":
    main()
