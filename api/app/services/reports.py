"""Read a report. The owner only: someone else's report, a missing one, an expired or deleted one
and a malformed id all give the same 404."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import AppError, ErrorCode
from app.db.models import Claim, Evidence, Report, Run, User
from app.schemas.reports import Claim as ClaimView
from app.schemas.reports import Evidence as EvidenceView
from app.schemas.reports import Report as ReportView
from app.schemas.reports import ReportDetail


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
