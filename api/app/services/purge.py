"""The daily purge: expired reports (with their run), old finished runs that never made a report,
old ai_calls rows and used or expired email tokens. Never deletes usage_events (the free-run quota
source; run_id becomes NULL through its foreign key), usage_daily, uploads, users, audit_log, or a
run that is not finished."""

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, exists, or_, select
from sqlalchemy.orm import Session

from app.core.config import Limits
from app.core.enums import RunStatus
from app.db.models import AiCall, EmailToken, Report, Run
from app.storage import Storage

logger = logging.getLogger("indesk.purge")


@dataclass(frozen=True)
class PurgePass:
    expired_runs: int = 0  # runs removed because their report expired (report, claims, ... cascade)
    old_no_report_runs: int = 0  # finished runs without a report, older than the limit
    ai_calls: int = 0
    email_tokens: int = 0  # used or expired link tokens, older than the retention
    pdf_failed: int = 0  # report PDFs that could not be removed (best effort)

    @property
    def total(self) -> int:
        return self.expired_runs + self.old_no_report_runs + self.ai_calls + self.email_tokens


def _purge_expired_reports(
    db: Session, storage: Storage, now: datetime, batch: int
) -> tuple[int, int]:
    rows = db.execute(
        select(Run.id, Report.pdf_key)
        .join(Report, Report.run_id == Run.id)
        .where(Run.status == RunStatus.FINISHED, Report.expires_at <= now)
        .order_by(Report.expires_at)
        .limit(batch)
        .with_for_update(of=Run, skip_locked=True)
    ).all()
    if not rows:
        db.commit()  # nothing changed; this ends the transaction and releases the locks
        return 0, 0
    db.execute(delete(Run).where(Run.id.in_([run_id for run_id, _ in rows])))
    db.commit()
    failed = 0
    for _, pdf_key in rows:
        if pdf_key is None:
            continue
        try:
            storage.delete(pdf_key)
        except Exception:  # best effort: a stuck file must never fail the pass
            failed += 1
    return len(rows), failed


def _purge_old_runs_without_report(db: Session, now: datetime, days: int, batch: int) -> int:
    ids = db.scalars(
        select(Run.id)
        .where(
            Run.status == RunStatus.FINISHED,
            Run.finished_at < now - timedelta(days=days),
            ~exists().where(Report.run_id == Run.id),
        )
        .order_by(Run.finished_at)
        .limit(batch)
        .with_for_update(skip_locked=True)
    ).all()
    return _delete_by_id(db, Run, ids)


def _purge_old_ai_calls(db: Session, now: datetime, days: int, batch: int) -> int:
    ids = db.scalars(
        select(AiCall.id)
        .where(AiCall.created_at < now - timedelta(days=days))
        .order_by(AiCall.created_at)
        .limit(batch)
        .with_for_update(skip_locked=True)
    ).all()
    return _delete_by_id(db, AiCall, ids)


def _purge_old_email_tokens(db: Session, now: datetime, days: int, batch: int) -> int:
    cutoff = now - timedelta(days=days)
    ids = db.scalars(
        select(EmailToken.id)
        .where(or_(EmailToken.used_at < cutoff, EmailToken.expires_at < cutoff))
        .order_by(EmailToken.expires_at)
        .limit(batch)
        .with_for_update(skip_locked=True)
    ).all()
    return _delete_by_id(db, EmailToken, ids)


def _delete_by_id(
    db: Session, model: type[Run] | type[AiCall] | type[EmailToken], ids: Sequence[uuid.UUID]
) -> int:
    if not ids:
        db.commit()
        return 0
    db.execute(delete(model).where(model.id.in_(ids)))
    db.commit()
    return len(ids)


def purge_pass(db: Session, storage: Storage, limits: Limits, now: datetime) -> PurgePass:
    batch = limits.purge_batch
    expired, pdf_failed = _purge_expired_reports(db, storage, now, batch)
    return PurgePass(
        expired_runs=expired,
        old_no_report_runs=_purge_old_runs_without_report(
            db, now, limits.purge_no_report_days, batch
        ),
        ai_calls=_purge_old_ai_calls(db, now, limits.ai_calls_retention_days, batch),
        email_tokens=_purge_old_email_tokens(db, now, limits.email_token_retention_days, batch),
        pdf_failed=pdf_failed,
    )


def purge_expired(db: Session, storage: Storage, limits: Limits, now: datetime) -> PurgePass:
    """Repeat passes until one finds nothing; returns the sums. One log line per pass (counts)."""
    totals = PurgePass()
    while True:
        done = purge_pass(db, storage, limits, now)
        logger.info(
            "purge pass: expired_runs=%d old_no_report_runs=%d ai_calls=%d email_tokens=%d"
            " pdf_failed=%d",
            done.expired_runs,
            done.old_no_report_runs,
            done.ai_calls,
            done.email_tokens,
            done.pdf_failed,
        )
        totals = PurgePass(
            totals.expired_runs + done.expired_runs,
            totals.old_no_report_runs + done.old_no_report_runs,
            totals.ai_calls + done.ai_calls,
            totals.email_tokens + done.email_tokens,
            totals.pdf_failed + done.pdf_failed,
        )
        if done.total == 0:
            return totals
