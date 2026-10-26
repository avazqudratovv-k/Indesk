"""Write a ReportDraft: the report, its claims and its evidence. Called by store.finish_run inside
the transaction that finishes the run, so the report and the run's end are one commit.

Ownership: the owner is the run's owner, read from the run row by the caller. The file name comes
from the run's own subject upload. Nothing here logs."""

import uuid
from datetime import datetime, timedelta
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AgentKey, FileRole, RunMode
from app.db.models import AgentStep, Claim, Evidence, Report, RunFile, Upload, User
from app.runs.cat_schemas import ReportDraft

# Report retention in days by plan (DATA.md reports.expires_at). Custom plans choose 90, 180 or 365;
# until checkout exists the shortest, 90, is used.
RETENTION_DAYS: Final[dict[str, int]] = {"free": 30, "pro": 90, "payg": 60, "custom": 90}
DEFAULT_RETENTION_DAYS: Final = 30


class ReportNotSavable(Exception):  # noqa: N818  # a bug (missing step line), never user input
    """The trace lines a report hangs on do not exist."""


def _step_id(db: Session, run_id: uuid.UUID, agent: AgentKey) -> uuid.UUID:
    found = db.scalar(
        select(AgentStep.id)
        .where(AgentStep.run_id == run_id, AgentStep.agent == agent, AgentStep.payload.is_not(None))
        .order_by(AgentStep.seq.desc())
        .limit(1)
    )
    if found is None:
        raise ReportNotSavable
    return found


def insert_report(
    db: Session, run_id: uuid.UUID, owner_id: uuid.UUID, draft: ReportDraft, now: datetime
) -> uuid.UUID:
    plan = db.scalar(select(User.plan).where(User.id == owner_id))
    file_name = db.scalar(
        select(Upload.filename)
        .join(RunFile, RunFile.upload_id == Upload.id)
        .where(RunFile.run_id == run_id, RunFile.owner_id == owner_id)
        .order_by((RunFile.role == FileRole.SUBJECT).desc(), RunFile.upload_id)
        .limit(1)
    )
    steps = {
        "beaver": _step_id(db, run_id, AgentKey.DATA),
        "cat": _step_id(db, run_id, AgentKey.CRITIC),
    }
    days = RETENTION_DAYS.get(str(plan), DEFAULT_RETENTION_DAYS)
    report = Report(
        run_id=run_id,
        owner_id=owner_id,
        mode=RunMode.ASK,
        title=draft.title,
        summary_json=draft.summary.model_dump(mode="json", exclude_none=True),
        confidence=draft.confidence.value if draft.confidence else None,
        verified_count=draft.verified_count,
        total_claims=draft.total_claims,
        expires_at=now + timedelta(days=days),
    )
    db.add(report)
    db.flush()
    for claim in draft.claims:
        db.add(
            Claim(
                report_id=report.id, owner_id=owner_id, n=claim.n, text=claim.text,
                status=claim.status.value, origin="answer", computed_value=claim.computed_value,
                evidence_refs=list(claim.evidence_refs),
            )
        )  # fmt: skip
    for item in draft.evidence:
        db.add(
            Evidence(
                run_id=run_id, owner_id=owner_id, step_id=steps[item.source], ref=item.ref,
                type=item.type, file_name=file_name or "", location=item.location,
                payload=item.payload.model_dump(mode="json", exclude_none=True),
            )
        )  # fmt: skip
    return report.id
