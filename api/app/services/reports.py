"""Read a report. The owner only: someone else's report, a missing one, an expired or deleted one
and a malformed id all give the same 404."""

import base64
import binascii
import uuid
from datetime import datetime

from sqlalchemy import delete, func, literal, select, tuple_
from sqlalchemy.orm import Session

from app.core import clock
from app.core.enums import RunStatus, UploadMime
from app.core.errors import AppError, ErrorCode
from app.db.models import AuditLog, Claim, Evidence, Report, Run, RunFile, Upload, User
from app.schemas.reports import Claim as ClaimView
from app.schemas.reports import Evidence as EvidenceView
from app.schemas.reports import Report as ReportView
from app.schemas.reports import ReportDetail, ReportListItem, ReportPage

DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 50
AUDIT_REPORT_DELETED = "report_deleted"


def report_view(report: Report, lang: str) -> ReportView:
    """The report as the API shows it. `lang` is not a reports column: it is the run's."""
    columns = {name: getattr(report, name) for name in ReportView.model_fields if name != "lang"}
    return ReportView.model_validate({**columns, "lang": lang})


def get_report_detail(db: Session, user: User, raw_id: str) -> ReportDetail:
    not_found = AppError(404, ErrorCode.NOT_FOUND)
    try:
        report_id = uuid.UUID(raw_id)
    except ValueError:
        raise not_found from None
    row = db.execute(
        select(Report, Run.lang)
        .join(Run, Run.id == Report.run_id)
        .where(
            Report.id == report_id,
            Report.owner_id == user.id,
            Report.deleted_at.is_(None),
            Report.expires_at > clock.utcnow(),
        )
    ).first()
    if row is None:
        raise not_found
    report, lang = row
    claims = db.scalars(
        select(Claim)
        .where(Claim.report_id == report.id, Claim.owner_id == user.id)
        .order_by(Claim.n)
    ).all()
    evidence = db.scalars(
        select(Evidence)
        .where(Evidence.run_id == report.run_id, Evidence.owner_id == user.id)
        .order_by(Evidence.ref)
    ).all()
    return ReportDetail(
        report=report_view(report, lang),
        claims=[ClaimView.model_validate(c) for c in claims],
        evidence=[EvidenceView.model_validate(e) for e in evidence],
    )


def _encode_cursor(created_at: datetime, report_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{report_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        stamp, raw_id = raw.split("|")
        created_at = datetime.fromisoformat(stamp)
        if created_at.tzinfo is None:
            raise ValueError
        return created_at, uuid.UUID(raw_id)
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise AppError(422, ErrorCode.VALIDATION_ERROR) from None


def list_reports(db: Session, user: User, *, limit: int, cursor: str | None) -> ReportPage:
    """The caller's visible reports (not deleted, not expired), newest first. Keyset on
    (created_at, id). Only answered and partial runs write a report, so only they appear."""
    pdf = func.bool_or(Upload.mime == UploadMime.PDF)
    files = (
        select(RunFile.run_id, func.count().label("n"), pdf.label("has_pdf"))
        .join(Upload, Upload.id == RunFile.upload_id)
        .group_by(RunFile.run_id)
        .subquery()
    )
    stmt = (
        select(Report, Run.outcome, Run.lang, files.c.n, files.c.has_pdf)
        .join(Run, Run.id == Report.run_id)
        .outerjoin(files, files.c.run_id == Report.run_id)
        .where(
            Report.owner_id == user.id,
            Report.deleted_at.is_(None),
            Report.expires_at > clock.utcnow(),
        )
        .order_by(Report.created_at.desc(), Report.id.desc())
        .limit(limit + 1)
    )
    if cursor is not None:
        stamp, last_id = _decode_cursor(cursor)
        stmt = stmt.where(
            tuple_(Report.created_at, Report.id) < tuple_(literal(stamp), literal(last_id))
        )
    rows = db.execute(stmt).all()
    page = rows[:limit]
    items = [
        ReportListItem(
            id=str(r.id), title=r.title, created_at=r.created_at, expires_at=r.expires_at,
            verified_count=r.verified_count, total_claims=r.total_claims, outcome=outcome,
            language=lang, file_kind=None if n is None else ("pdf" if has_pdf else "csv"),
            file_count=n or 0,
        )
        for r, outcome, lang, n, has_pdf in page
    ]  # fmt: skip
    more = len(rows) > limit
    last = page[-1][0] if more else None
    return ReportPage(
        items=items,
        next_cursor=_encode_cursor(last.created_at, last.id) if last is not None else None,
    )


def delete_report(db: Session, user: User, raw_id: str) -> None:
    """Delete the whole run; the foreign keys cascade to the report, claims, evidence, steps and
    run_files. usage_events and ai_calls keep their rows (run_id set to NULL), and nothing in
    usage is touched: no refund. Someone else's, a missing, an expired and a malformed id all give
    the same 404. The run row is locked, so a finish at the same moment cannot interleave."""
    not_found = AppError(404, ErrorCode.NOT_FOUND)
    try:
        report_id = uuid.UUID(raw_id)
    except ValueError:
        raise not_found from None
    row = db.execute(
        select(Run.id, Run.status)
        .join(Report, Report.run_id == Run.id)
        .where(
            Report.id == report_id,
            Report.owner_id == user.id,
            Run.user_id == user.id,
            Report.deleted_at.is_(None),
            Report.expires_at > clock.utcnow(),
        )
        .with_for_update(of=Run)
    ).first()
    if row is None:
        db.rollback()
        raise not_found
    run_id, status = row
    if status != RunStatus.FINISHED:
        db.rollback()
        raise AppError(409, ErrorCode.RUN_IN_PROGRESS)
    db.execute(delete(Run).where(Run.id == run_id, Run.user_id == user.id))
    db.add(AuditLog(user_id=user.id, action=AUDIT_REPORT_DELETED, target=str(report_id)))
    db.commit()
