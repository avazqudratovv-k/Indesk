"""Small row builders for the database tests. Each one flushes, so foreign keys are real."""

import itertools
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.db.models import (
    AgentStep,
    Claim,
    EmailToken,
    Evidence,
    Report,
    Run,
    RunFile,
    Upload,
    User,
)

_counter = itertools.count(1)
NOW = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)


def add[T](session: Session, obj: T) -> T:
    session.add(obj)
    session.flush()
    return obj


def make_user(session: Session, **kw: Any) -> User:
    n = next(_counter)
    values: dict[str, Any] = {
        "email": f"user{n}@example.com",
        "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$not-a-real-hash",
        "display_name": f"User {n}",
        "handle": f"user{n}",
    }
    return add(session, User(**{**values, **kw}))


def make_user_before_0007(session: Session) -> User:
    """A user inserted with only the columns that exist before migration 0007, for tests that
    build rows in an old database. The ORM insert of `make_user` would name the newer columns.
    Returns a stand-in that has just the `id` the other builders read."""
    n = next(_counter)
    user_id = session.execute(
        insert(User)
        .values(
            email=f"old{n}@example.com",
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$not-a-real-hash",
            display_name=f"Old {n}",
            handle=f"old{n}",
        )
        .returning(User.id)
    ).scalar_one()
    return SimpleNamespace(id=user_id)  # type: ignore[return-value]


def make_email_token(session: Session, user: User, **kw: Any) -> EmailToken:
    n = next(_counter)
    values: dict[str, Any] = {
        "user_id": user.id,
        "purpose": "reset",
        "token_hash": f"{n:064x}",
        "expires_at": NOW + timedelta(minutes=30),
    }
    return add(session, EmailToken(**{**values, **kw}))


def make_upload(session: Session, user: User, **kw: Any) -> Upload:
    n = next(_counter)
    values: dict[str, Any] = {
        "user_id": user.id,
        "filename": f"file{n}.csv",
        "mime": "text/csv",
        "size": 1000,
        "sha256": "9f2c" * 16,
        "storage_key": f"uploads/{user.id}/{n}",
        "row_count": 10,
        "expires_at": NOW + timedelta(hours=24),
    }
    return add(session, Upload(**{**values, **kw}))


def make_run(session: Session, user: User, **kw: Any) -> Run:
    values: dict[str, Any] = {
        "user_id": user.id,
        "question": "Which stations grew fastest since 2019?",
        "mode": "ask",
        "lang": "en",
    }
    return add(session, Run(**{**values, **kw}))


def make_run_file(session: Session, run: Run, upload: Upload, **kw: Any) -> RunFile:
    values: dict[str, Any] = {
        "run_id": run.id,
        "upload_id": upload.id,
        "owner_id": run.user_id,
        "role": "subject",
    }
    return add(session, RunFile(**{**values, **kw}))


def make_step(session: Session, run: Run, seq: int = 1, **kw: Any) -> AgentStep:
    values: dict[str, Any] = {
        "run_id": run.id,
        "owner_id": run.user_id,
        "seq": seq,
        "agent": "manager",
        "kind": "say",
        "state": "running",
        "key": "plan",
        "args": {"files": 2},
        "tok": 1240,
        "bubble": "owlSplit",
    }
    return add(session, AgentStep(**{**values, **kw}))


def make_evidence(session: Session, run: Run, step: AgentStep, **kw: Any) -> Evidence:
    values: dict[str, Any] = {
        "run_id": run.id,
        "owner_id": run.user_id,
        "step_id": step.id,
        "ref": "D1",
        "type": "table",
        "file_name": "seoul-subway-ridership.csv",
        "location": "rows 1-4800",
        "payload": {"title": "Growth by station", "rows_used": 4800},
    }
    return add(session, Evidence(**{**values, **kw}))


def make_report(session: Session, run: Run, **kw: Any) -> Report:
    values: dict[str, Any] = {
        "run_id": run.id,
        "owner_id": run.user_id,
        "mode": run.mode,
        "title": "Hapjeong leads station growth since 2019",
        "summary_json": {"answer": "Hapjeong grew fastest."},
        "confidence": "high",
        "verified_count": 1,
        "total_claims": 1,
        "expires_at": NOW + timedelta(days=30),
    }
    return add(session, Report(**{**values, **kw}))


def make_claim(session: Session, report: Report, n: int = 1, **kw: Any) -> Claim:
    values: dict[str, Any] = {
        "report_id": report.id,
        "owner_id": report.owner_id,
        "n": n,
        "text": "Hapjeong grew fastest: +18.2%.",
        "status": "verified",
        "origin": "answer",
        "computed_value": "+18.2%",
        "evidence_refs": ["D1"],
    }
    return add(session, Claim(**{**values, **kw}))


def new_id() -> uuid.UUID:
    return uuid.uuid4()
