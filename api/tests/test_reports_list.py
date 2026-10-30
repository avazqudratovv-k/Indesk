"""GET /api/reports (the list) and DELETE /api/reports/{id}, against the real Postgres."""

import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, func, select, update
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import Settings
from app.db.models import (
    AgentStep,
    AiCall,
    Claim,
    Evidence,
    Report,
    Run,
    RunFile,
    Upload,
    UsageDaily,
    UsageEvent,
    User,
)
from app.runs import quota
from tests.factories import (
    make_claim,
    make_evidence,
    make_report,
    make_run,
    make_run_file,
    make_step,
    make_upload,
)
from tests.test_auth import MakeClient
from tests.test_uploads import err, settings_for, signed_in

URL = "/api/reports"
LEAK = "SENTINEL_LEAK_9c1d"
ROW_KEYS = {
    "id", "title", "created_at", "expires_at", "verified_count", "total_claims",
    "outcome", "language", "file_kind", "file_count",
}  # fmt: skip
EMPTY = dict.fromkeys(("runs", "reports", "claims", "evidence", "steps", "run_files"), 0)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return settings_for(tmp_path)


@pytest.fixture
def alice(make_client: MakeClient, settings: Settings) -> TestClient:
    return signed_in(make_client, settings, "alice@example.com", 10)


@pytest.fixture
def bob(make_client: MakeClient, settings: Settings) -> TestClient:
    return signed_in(make_client, settings, "bob@example.com", 11)


@pytest.fixture
def db(db_connection: Connection) -> Session:
    return Session(bind=db_connection)


def user_of(db: Session, email: str) -> User:
    return db.scalars(select(User).where(User.email == email)).one()


def seed(db: Session, user: User, *, age_minutes: int = 0, pdf: bool = False, **kw: Any) -> Report:
    """A finished run with one file, one step, one evidence row, one claim and a report."""
    run = make_run(db, user, status="finished", outcome="answered")
    mime = "application/pdf" if pdf else "text/csv"
    make_run_file(db, run, make_upload(db, user, mime=mime))
    step = make_step(db, run)
    make_evidence(db, run, step, payload={"title": LEAK, "quote": LEAK, "code": LEAK})
    report = make_report(
        db,
        run,
        summary_json={"answer": LEAK},
        created_at=clock.utcnow() - timedelta(minutes=age_minutes),
        expires_at=clock.utcnow() + timedelta(days=30),
        **kw,
    )
    make_claim(db, report, text=LEAK)
    db.commit()
    return report


def rows(client: TestClient, query: str = "") -> dict[str, Any]:
    response = client.get(f"{URL}{query}")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def ids(body: dict[str, Any]) -> list[str]:
    return [i["id"] for i in body["items"]]


# ---- list ----


def test_the_list_is_the_owners_own_newest_first(
    alice: TestClient, bob: TestClient, db: Session
) -> None:
    old = seed(db, user_of(db, "alice@example.com"), age_minutes=10)
    new = seed(db, user_of(db, "alice@example.com"), age_minutes=1)
    theirs = seed(db, user_of(db, "bob@example.com"))
    body = rows(alice)
    assert ids(body) == [str(new.id), str(old.id)]
    assert body["next_cursor"] is None
    assert ids(rows(bob)) == [str(theirs.id)]


def test_the_list_needs_a_session(make_client: MakeClient, settings: Settings) -> None:
    err(make_client(settings).get(URL), 401, "UNAUTHENTICATED")


def test_deleted_and_expired_reports_are_not_listed(alice: TestClient, db: Session) -> None:
    me = user_of(db, "alice@example.com")
    keep = seed(db, me)
    gone = seed(db, me)
    old = seed(db, me)
    db.execute(update(Report).where(Report.id == gone.id).values(deleted_at=clock.utcnow()))
    db.execute(
        update(Report)
        .where(Report.id == old.id)
        .values(expires_at=clock.utcnow() - timedelta(seconds=1))
    )
    db.commit()
    assert ids(rows(alice)) == [str(keep.id)]


def test_the_row_shape(alice: TestClient, db: Session) -> None:
    me = user_of(db, "alice@example.com")
    csv = seed(db, me, age_minutes=2, title="csv one")
    pdf = seed(db, me, age_minutes=1, pdf=True, verified_count=0, total_claims=2, confidence=None)
    db.execute(update(Run).where(Run.id == pdf.run_id).values(outcome="partial", lang="ko"))
    db.commit()
    by_id = {i["id"]: i for i in rows(alice)["items"]}
    one, two = by_id[str(csv.id)], by_id[str(pdf.id)]
    assert set(one) == ROW_KEYS
    assert (one["file_kind"], one["file_count"], one["title"]) == ("csv", 1, "csv one")
    assert (one["outcome"], one["language"]) == ("answered", "en")
    assert (two["file_kind"], two["outcome"], two["language"]) == ("pdf", "partial", "ko")
    assert (two["verified_count"], two["total_claims"]) == (0, 2)


def test_the_list_leaks_no_report_text(alice: TestClient, db: Session) -> None:
    seed(db, user_of(db, "alice@example.com"))
    text = alice.get(URL).text
    assert LEAK not in text
    for word in (
        "summary", '"claims"', "evidence", "payload", "prompt", "passage", "quote", "code",
        "confidence", "owner_id", "run_id", "pdf_key", "translations",
    ):  # fmt: skip
        assert word not in text, word


def test_limit_default_cap_and_validation(alice: TestClient, db: Session) -> None:
    me = user_of(db, "alice@example.com")
    for n in range(23):
        seed(db, me, age_minutes=n)
    assert len(rows(alice)["items"]) == 20
    assert len(rows(alice, "?limit=5")["items"]) == 5
    assert len(rows(alice, "?limit=50")["items"]) == 23
    for bad in ("0", "51", "-1", "x"):
        err(alice.get(f"{URL}?limit={bad}"), 422, "VALIDATION_ERROR")


def test_the_cursor_walks_every_report_once(alice: TestClient, db: Session) -> None:
    me = user_of(db, "alice@example.com")
    made = [str(seed(db, me, age_minutes=n).id) for n in range(7)]
    seen: list[str] = []
    cursor = None
    while True:
        body = rows(alice, "?limit=3" + (f"&cursor={cursor}" if cursor else ""))
        seen += ids(body)
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert seen == made  # age_minutes grows, so creation order here is newest first


def test_the_cursor_breaks_ties_on_id(alice: TestClient, db: Session) -> None:
    me = user_of(db, "alice@example.com")
    made = [seed(db, me) for _ in range(4)]
    db.execute(update(Report).values(created_at=clock.utcnow()))
    db.commit()
    expected = [str(r.id) for r in sorted(made, key=lambda r: r.id, reverse=True)]
    first = rows(alice, "?limit=2")
    second = rows(alice, f"?limit=2&cursor={first['next_cursor']}")
    assert ids(first) + ids(second) == expected
    assert second["next_cursor"] is None


@pytest.mark.parametrize("cursor", ["x", "!!!", "bm90LWEtY3Vyc29y", "MjAyNi0xMC0yNXx4"])
def test_a_bad_cursor_is_a_validation_error(alice: TestClient, cursor: str) -> None:
    err(alice.get(f"{URL}?cursor={cursor}"), 422, "VALIDATION_ERROR")


# ---- delete ----


def counts(db: Session, run_id: uuid.UUID) -> dict[str, int]:
    def n(model: Any, column: Any) -> int:
        return int(db.scalar(select(func.count()).select_from(model).where(column == run_id)) or 0)

    return {
        "runs": n(Run, Run.id),
        "reports": n(Report, Report.run_id),
        "claims": int(db.scalar(select(func.count()).select_from(Claim)) or 0),
        "evidence": n(Evidence, Evidence.run_id),
        "steps": n(AgentStep, AgentStep.run_id),
        "run_files": n(RunFile, RunFile.run_id),
    }


def test_delete_cascades_and_changes_no_quota(alice: TestClient, db: Session) -> None:
    me = user_of(db, "alice@example.com")
    report = seed(db, me)
    run_id, report_id = report.run_id, report.id
    step = db.scalars(select(AgentStep).where(AgentStep.run_id == run_id)).one()
    db.add(UsageEvent(user_id=me.id, run_id=run_id, kind="run", amount=1))
    db.add(
        UsageDaily(
            day=clock.utcnow().date(),
            scope=quota.user_scope(me.id),
            user_id=me.id,
            runs=1,
            model_calls=3,
        )
    )
    db.add(
        AiCall(
            run_id=run_id, step_id=step.id, user_id=me.id, purpose="critic", model="m",
            attempt=1, status="ok",
        )
    )  # fmt: skip
    db.commit()
    used_before = quota.free_runs_used(db, me.id)
    daily_before = db.execute(select(UsageDaily.runs, UsageDaily.model_calls)).all()
    upload_id = db.scalars(select(RunFile.upload_id).where(RunFile.run_id == run_id)).one()
    assert counts(db, run_id) == dict.fromkeys(EMPTY, 1)

    assert alice.delete(f"{URL}/{report_id}").status_code == 204
    db.expire_all()

    assert counts(db, run_id) == EMPTY
    assert quota.free_runs_used(db, me.id) == used_before == 1
    assert db.execute(select(UsageDaily.runs, UsageDaily.model_calls)).all() == daily_before
    event = db.scalars(select(UsageEvent).where(UsageEvent.user_id == me.id)).one()
    assert event.run_id is None
    assert db.scalars(select(AiCall.run_id).where(AiCall.user_id == me.id)).one() is None
    assert db.get(Upload, upload_id) is not None  # the file's own row is not part of the run
    err(alice.get(f"{URL}/{report_id}"), 404, "NOT_FOUND")
    assert rows(alice)["items"] == []
    err(alice.delete(f"{URL}/{report_id}"), 404, "NOT_FOUND")


def test_another_owner_gets_the_same_404_and_nothing_is_deleted(
    alice: TestClient, bob: TestClient, db: Session
) -> None:
    report = seed(db, user_of(db, "alice@example.com"))
    theirs = bob.delete(f"{URL}/{report.id}")
    missing = bob.delete(f"{URL}/{uuid.uuid4()}")
    malformed = bob.delete(f"{URL}/not-a-uuid")
    for response in (theirs, missing, malformed):
        err(response, 404, "NOT_FOUND")
    assert theirs.content == missing.content == malformed.content
    assert counts(db, report.run_id)["runs"] == 1
    assert ids(rows(alice)) == [str(report.id)]


def test_delete_needs_a_session(make_client: MakeClient, settings: Settings) -> None:
    err(make_client(settings).delete(f"{URL}/{uuid.uuid4()}"), 401, "UNAUTHENTICATED")


def test_an_active_run_is_a_409_and_nothing_is_deleted(alice: TestClient, db: Session) -> None:
    report = seed(db, user_of(db, "alice@example.com"))
    db.execute(update(Run).where(Run.id == report.run_id).values(status="running"))
    db.commit()
    err(alice.delete(f"{URL}/{report.id}"), 409, "RUN_IN_PROGRESS")
    assert counts(db, report.run_id)["runs"] == 1
    assert counts(db, report.run_id)["reports"] == 1
