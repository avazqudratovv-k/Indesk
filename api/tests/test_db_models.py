import uuid
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    AgentStep,
    AiCall,
    AuditLog,
    Claim,
    Evidence,
    RefreshToken,
    Report,
    Run,
    RunFile,
    Upload,
    UsageDaily,
    UsageEvent,
    User,
)
from tests.factories import (
    NOW,
    add,
    make_claim,
    make_evidence,
    make_report,
    make_run,
    make_run_file,
    make_step,
    make_upload,
    make_user,
)

Build = Callable[[Session], object]


def rejected(session: Session, build: Build) -> None:
    """The database must refuse the row. The savepoint keeps the test session usable afterwards."""
    with pytest.raises(IntegrityError), session.begin_nested():
        build(session)


def count(session: Session, model: type[Base]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


# ---- enums are text + CHECK, and bad values are refused ----

BAD_VALUES: dict[str, Build] = {
    "user.plan": lambda s: make_user(s, plan="gold"),
    "user.lang": lambda s: make_user(s, lang="xx"),
    "user.theme": lambda s: make_user(s, theme="blue"),
    "user.default_view": lambda s: make_user(s, default_view="wide"),
    "upload.mime": lambda s: make_upload(s, make_user(s), mime="application/zip"),
    "upload.status": lambda s: make_upload(s, make_user(s), status="gone"),
    "upload.moderation": lambda s: make_upload(s, make_user(s), moderation="maybe"),
    "run.mode": lambda s: make_run(s, make_user(s), mode="chat"),
    "run.question_type": lambda s: make_run(s, make_user(s), question_type="other"),
    "run.status": lambda s: make_run(s, make_user(s), status="waiting"),
    "run.outcome": lambda s: make_run(s, make_user(s), outcome="great"),
    "run.lang": lambda s: make_run(s, make_user(s), lang="de"),
    "run_file.role": lambda s: _run_file(s, role="primary"),
    "agent_step.agent": lambda s: _step(s, agent="owl"),  # UI name; the database key is `manager`
    "agent_step.kind": lambda s: _step(s, kind="result"),
    "agent_step.state": lambda s: _step(s, state="working"),  # UI word for `running`
    "agent_step.bubble": lambda s: _step(s, bubble="catBubble"),
    "agent_step.attempt": lambda s: _step(s, attempt=3),
    "evidence.type": lambda s: _evidence(s, type="screenshot"),
    "report.mode": lambda s: _report(s, mode="chat"),
    "report.confidence": lambda s: _report(s, confidence="certain"),
    "report.template": lambda s: _report(s, template="fancy"),
    "report.typeface": lambda s: _report(s, typeface="comic"),
    "report.text_size": lambda s: _report(s, text_size="xl"),
    "claim.status": lambda s: _claim(s, status="true"),
    "claim.origin": lambda s: _claim(s, origin="web"),
    "ai_call.purpose": lambda s: _ai_call(s, purpose="chat"),
    "ai_call.status": lambda s: _ai_call(s, status="slow"),
    "ai_call.attempt": lambda s: _ai_call(s, attempt=4),
    "usage_event.kind": lambda s: add(
        s, UsageEvent(user_id=make_user(s).id, kind="refund", amount=1)
    ),
}


def _run_file(s: Session, **kw: Any) -> RunFile:
    user = make_user(s)
    return make_run_file(s, make_run(s, user), make_upload(s, user), **kw)


def _step(s: Session, **kw: Any) -> AgentStep:
    return make_step(s, make_run(s, make_user(s)), **kw)


def _evidence(s: Session, **kw: Any) -> Evidence:
    run = make_run(s, make_user(s))
    return make_evidence(s, run, make_step(s, run), **kw)


def _report(s: Session, **kw: Any) -> Report:
    return make_report(s, make_run(s, make_user(s)), **kw)


def _claim(s: Session, **kw: Any) -> Claim:
    return make_claim(s, _report(s), **kw)


def _ai_call(s: Session, **kw: Any) -> AiCall:
    values: dict[str, Any] = {
        "user_id": make_user(s).id,
        "purpose": "compute",
        "model": "gemini-3.8-flash",
        "attempt": 1,
        "status": "ok",
    }
    return add(s, AiCall(**{**values, **kw}))


@pytest.mark.parametrize("name", BAD_VALUES)
def test_bad_enum_values_are_rejected(session: Session, name: str) -> None:
    rejected(session, BAD_VALUES[name])


def test_good_values_for_the_same_builders_are_accepted(session: Session) -> None:
    # Guards the test above: it must fail because of the bad value, not because a builder is broken.
    _run_file(session)
    _step(session)
    _evidence(session)
    _claim(session)
    _ai_call(session)
    assert count(session, Claim) == 1


def test_no_native_postgres_enum_types(session: Session) -> None:
    kinds = session.scalar(text("SELECT count(*) FROM pg_type WHERE typtype = 'e'"))
    assert kinds == 0


def test_all_timestamps_are_timestamptz(session: Session) -> None:
    rows = session.execute(
        text(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' AND data_type LIKE 'timestamp%' "
            "AND data_type <> 'timestamp with time zone'"
        )
    ).all()
    assert rows == []


# ---- users ----


def test_email_must_be_lowercase_and_unique(session: Session) -> None:
    rejected(session, lambda s: make_user(s, email="Kim@Example.com"))
    make_user(session, email="kim@example.com", handle="kim")
    rejected(session, lambda s: make_user(s, email="kim@example.com", handle="kim2"))
    rejected(session, lambda s: make_user(s, email="other@example.com", handle="kim"))


def test_user_field_limits(session: Session) -> None:
    rejected(session, lambda s: make_user(s, display_name=""))
    rejected(session, lambda s: make_user(s, display_name="x" * 61))
    rejected(session, lambda s: make_user(s, handle="ab"))
    rejected(session, lambda s: make_user(s, handle="x" * 31))


def test_user_defaults(session: Session) -> None:
    user = make_user(session)
    session.refresh(user)
    assert (user.plan, user.lang, user.default_view) == ("free", "en", "simple")
    assert user.discoverable is False
    assert user.notify is True
    assert user.created_at.tzinfo is not None


def test_refresh_tokens_store_only_a_hash_and_a_family(session: Session) -> None:
    columns = {c.name for c in inspect(RefreshToken).columns}
    assert {"token_hash", "family_id", "revoked_at", "replaced_by", "expires_at"} <= columns
    assert not {"token", "refresh_token", "secret"} & columns
    user = make_user(session)
    family = uuid.uuid4()
    first = add(
        session,
        RefreshToken(user_id=user.id, family_id=family, token_hash="sha256:aa", expires_at=NOW),
    )
    add(
        session,
        RefreshToken(user_id=user.id, family_id=family, token_hash="sha256:bb", expires_at=NOW),
    )
    first.replaced_by = first.id
    session.flush()
    rejected(
        session,
        lambda s: add(
            s,
            RefreshToken(user_id=user.id, family_id=family, token_hash="sha256:aa", expires_at=NOW),
        ),
    )


# ---- uploads ----


def test_upload_sha256_must_be_64_hex(session: Session) -> None:
    user = make_user(session)
    rejected(session, lambda s: make_upload(s, user, sha256="9f2c…"))
    rejected(session, lambda s: make_upload(s, user, sha256="A" * 64))
    rejected(session, lambda s: make_upload(s, user, size=-1))
    rejected(session, lambda s: make_upload(s, user, filename="x" * 256))


def test_deleted_upload_row_stays_without_storage_key(session: Session) -> None:
    upload = make_upload(
        session, make_user(session), status="deleted", storage_key=None, deleted_at=NOW
    )
    session.refresh(upload)
    assert upload.storage_key is None


# ---- runs ----


def test_run_constraints(session: Session) -> None:
    user = make_user(session)
    rejected(session, lambda s: make_run(s, user, question=""))
    rejected(session, lambda s: make_run(s, user, question="x" * 1001))
    rejected(session, lambda s: make_run(s, user, tokens_in=-1))
    rejected(
        session, lambda s: make_run(s, user, status="finished")
    )  # a finished run has an outcome
    make_run(session, user, status="finished", outcome="failed")


def test_run_defaults(session: Session) -> None:
    run = make_run(session, make_user(session))
    session.refresh(run)
    assert run.status == "queued"
    assert run.counted is False
    assert float(run.cost_usd) == 0
    assert (run.tokens_in, run.tokens_out, run.tool_calls) == (0, 0, 0)


# ---- agent steps ----


def test_seq_is_unique_per_run_but_not_across_runs(session: Session) -> None:
    user = make_user(session)
    run_a, run_b = make_run(session, user), make_run(session, user)
    make_step(session, run_a, seq=1)
    make_step(session, run_a, seq=2)
    rejected(session, lambda s: make_step(s, run_a, seq=2))
    rejected(session, lambda s: make_step(s, run_a, seq=0))
    make_step(session, run_b, seq=1)  # same seq in another run is fine


def test_step_key_is_short_and_args_default_to_empty(session: Session) -> None:
    run = make_run(session, make_user(session))
    rejected(session, lambda s: make_step(s, run, seq=1, key=""))
    rejected(session, lambda s: make_step(s, run, seq=1, key="k" * 65))
    step = add(
        session,
        AgentStep(
            run_id=run.id,
            owner_id=run.user_id,
            seq=1,
            agent="data",
            kind="tool",
            state="queued",
            key="readCsv",
        ),
    )
    session.refresh(step)
    assert step.args == {}
    assert step.tok == 0
    assert step.bubble is None


def test_step_cannot_claim_another_users_run(session: Session) -> None:
    alice, mallory = make_user(session), make_user(session)
    run = make_run(session, alice)
    rejected(
        session,
        lambda s: add(
            s,
            AgentStep(
                run_id=run.id,
                owner_id=mallory.id,
                seq=1,
                agent="data",
                kind="tool",
                state="queued",
                key="x",
            ),
        ),
    )


# ---- a run cannot use another user's upload ----


def test_run_cannot_use_another_users_upload(session: Session) -> None:
    alice, bob = make_user(session), make_user(session)
    run = make_run(session, alice)
    bobs_upload = make_upload(session, bob)
    # Owner stated as Alice: the upload is not hers.
    rejected(session, lambda s: make_run_file(s, run, bobs_upload))
    # Owner stated as Bob: the run is not his.
    rejected(session, lambda s: make_run_file(s, run, bobs_upload, owner_id=bob.id))
    make_run_file(session, run, make_upload(session, alice))  # her own upload works


def test_run_files_one_subject_but_many_sources(session: Session) -> None:
    user = make_user(session)
    run = make_run(session, user, mode="check")
    subject_upload = make_upload(session, user)
    make_run_file(session, run, subject_upload, role="subject")
    rejected(session, lambda s: make_run_file(s, run, make_upload(s, user), role="subject"))
    make_run_file(session, run, make_upload(session, user), role="source")
    make_run_file(session, run, make_upload(session, user), role="source")
    # The same upload cannot be attached to the same run twice.
    rejected(session, lambda s: make_run_file(s, run, subject_upload, role="source"))


# ---- evidence, reports, claims ----


def test_evidence_ref_is_unique_per_run_and_step_must_belong_to_the_run(session: Session) -> None:
    user = make_user(session)
    run, other = make_run(session, user), make_run(session, user)
    step, other_step = make_step(session, run), make_step(session, other)
    make_evidence(session, run, step, ref="D1")
    rejected(session, lambda s: make_evidence(s, run, step, ref="D1"))
    rejected(session, lambda s: make_evidence(s, run, other_step, ref="D2"))
    make_evidence(session, run, step, ref="D2")
    make_evidence(session, other, other_step, ref="D1")


def test_report_rules(session: Session) -> None:
    user = make_user(session)
    run = make_run(session, user)
    rejected(session, lambda s: make_report(s, run, verified_count=3, total_claims=2))
    rejected(
        session, lambda s: make_report(s, run, total_claims=0, verified_count=0, confidence="high")
    )
    rejected(session, lambda s: make_report(s, run, title=""))
    other_user = make_user(session)
    rejected(session, lambda s: make_report(s, run, owner_id=other_user.id))  # not the run's owner
    report = make_report(session, run, total_claims=0, verified_count=0, confidence=None)
    session.refresh(report)
    assert report.translations is None
    assert (report.template, report.typeface, report.text_size) == ("plain", "clean", "m")
    rejected(session, lambda s: make_report(s, run))  # one report per run


def test_claim_numbers_are_unique_per_report_and_owned(session: Session) -> None:
    report = _report(session)
    make_claim(session, report, n=1)
    rejected(session, lambda s: make_claim(s, report, n=1))
    rejected(session, lambda s: make_claim(s, report, n=0))
    rejected(session, lambda s: make_claim(s, report, n=2, owner_id=make_user(s).id))
    unverified = make_claim(session, report, n=3, status="unverified", evidence_refs=[])
    session.refresh(unverified)
    assert unverified.evidence_refs == []


def test_report_mode_text_round_trips_jsonb(session: Session) -> None:
    run = make_run(session, make_user(session))
    summary = {"answer": "x", "top_rows": [{"label": "A", "value": "+1%", "status": "verified"}]}
    report = make_report(session, run, summary_json=summary, translations={"ko": {"title": "제목"}})
    session.expire_all()
    assert session.get(Report, report.id).summary_json == summary  # type: ignore[union-attr]


# ---- usage and logs ----


def test_usage_daily_unique_key_and_scope_rule(session: Session) -> None:
    user = make_user(session)
    day = date(2026, 10, 25)
    add(session, UsageDaily(day=day, scope="global"))
    add(session, UsageDaily(day=day, scope=f"user:{user.id}", user_id=user.id))
    rejected(session, lambda s: add(s, UsageDaily(day=day, scope="global")))
    rejected(
        session, lambda s: add(s, UsageDaily(day=day, scope=f"user:{user.id}", user_id=user.id))
    )
    other = date(2026, 10, 26)
    rejected(session, lambda s: add(s, UsageDaily(day=other, scope="global", user_id=user.id)))
    rejected(
        session,
        lambda s: add(s, UsageDaily(day=other, scope="user:not-this-user", user_id=user.id)),
    )
    rejected(session, lambda s: add(s, UsageDaily(day=other, scope=f"user:{user.id}")))


def test_usage_daily_supports_an_atomic_cap_check(session: Session) -> None:
    """The later cap check is one statement: INSERT .. ON CONFLICT DO UPDATE .. WHERE runs < cap."""
    cap, day = 2, date(2026, 10, 25)

    def take_one() -> int | None:
        upsert = (
            insert(UsageDaily)
            .values(day=day, scope="global", runs=1)
            .on_conflict_do_update(
                index_elements=["day", "scope"],
                set_={"runs": UsageDaily.runs + 1},
                where=UsageDaily.runs < cap,
            )
            .returning(UsageDaily.runs)
        )
        return session.execute(upsert).scalar()

    assert [take_one(), take_one(), take_one()] == [
        1,
        2,
        None,
    ]  # the third is refused by the database


def test_usage_event_amount_is_positive(session: Session) -> None:
    user = make_user(session)
    rejected(session, lambda s: add(s, UsageEvent(user_id=user.id, kind="run", amount=0)))
    add(session, UsageEvent(user_id=user.id, kind="run", amount=1))


def test_ai_calls_hold_metadata_only() -> None:
    columns = {c.name for c in inspect(AiCall).columns}
    assert columns == {
        "id",
        "run_id",
        "step_id",
        "user_id",
        "purpose",
        "model",
        "attempt",
        "status",
        "tokens_in",
        "tokens_out",
        "est_cost_usd",
        "latency_ms",
        "created_at",
    }


def test_audit_log_survives_user_deletion_without_the_user(session: Session) -> None:
    user = make_user(session)
    entry = add(
        session,
        AuditLog(
            user_id=user.id, action="share_link_created", target="rep_01", ip_hash="sha256:31c0"
        ),
    )
    session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    session.expire_all()
    assert session.get(AuditLog, entry.id).user_id is None  # type: ignore[union-attr]


# ---- deleting a user ----


def test_deleting_a_user_removes_everything_they_own_and_nothing_else(session: Session) -> None:
    def build(user: User) -> None:
        upload = make_upload(session, user)
        run = make_run(session, user)
        make_run_file(session, run, upload)
        step = make_step(session, run)
        make_evidence(session, run, step)
        report = make_report(session, run)
        make_claim(session, report)
        add(
            session,
            RefreshToken(
                user_id=user.id, family_id=uuid.uuid4(), token_hash=f"h-{user.id}", expires_at=NOW
            ),
        )
        add(session, UsageEvent(user_id=user.id, run_id=run.id, kind="run", amount=1))
        add(session, UsageDaily(day=date(2026, 10, 25), scope=f"user:{user.id}", user_id=user.id))
        add(
            session,
            AiCall(
                user_id=user.id,
                run_id=run.id,
                step_id=step.id,
                purpose="compute",
                model="gemini-3.8-flash",
                attempt=1,
                status="ok",
            ),
        )

    doomed, kept = make_user(session), make_user(session)
    build(doomed)
    build(kept)
    models: list[type[Base]] = [
        Upload,
        Run,
        RunFile,
        AgentStep,
        Evidence,
        Report,
        Claim,
        RefreshToken,
        UsageEvent,
        UsageDaily,
        AiCall,
    ]
    before = {m.__name__: count(session, m) for m in models}
    assert all(n >= 2 for n in before.values())

    doomed_id = doomed.id
    session.execute(text("DELETE FROM users WHERE id = :id"), {"id": doomed_id})
    session.expire_all()

    for model in models:
        assert count(session, model) == before[model.__name__] - 1, model.__name__
    assert session.get(User, kept.id) is not None
    assert (
        session.scalar(select(func.count()).select_from(Run).where(Run.user_id == doomed_id)) == 0
    )
    assert (
        session.scalar(select(func.count()).select_from(Report).where(Report.owner_id == doomed_id))
        == 0
    )


def test_every_owned_table_has_an_indexed_owner_column(session: Session) -> None:
    owner_column = {
        "refresh_tokens": "user_id",
        "uploads": "user_id",
        "runs": "user_id",
        "run_files": "owner_id",
        "agent_steps": "owner_id",
        "evidence": "owner_id",
        "reports": "owner_id",
        "claims": "owner_id",
        "ai_calls": "user_id",
        "usage_daily": "user_id",
        "usage_events": "user_id",
        "audit_log": "user_id",
    }
    inspector = inspect(session.connection())
    for table, column in owner_column.items():
        indexed = [ix["column_names"][0] for ix in inspector.get_indexes(table)]
        assert column in indexed, f"{table}.{column} has no index that starts with it"
