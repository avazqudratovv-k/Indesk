"""Builders for the quota tests: two signed-in users on the real API with the real database (rolled
back per test), a fake queue, and readers for what a refused or finished run left behind."""

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Connection, func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.enums import RunOutcome, RunReason, RunStatus
from app.db.models import Run, UsageDaily, UsageEvent
from app.main import app
from app.routers.runs import get_enqueue, get_session_factory
from app.runs import store
from tests.ai_helpers import factory_for
from tests.test_auth import MakeClient
from tests.test_runs_api import body, db_of, new_upload
from tests.test_uploads import settings_for, signed_in

URL = "/api/runs"


@dataclass
class Rig:
    alice: TestClient
    bob: TestClient
    connection: Connection
    enqueued: list[uuid.UUID]

    def start(self, client: TestClient | None = None) -> Any:
        who = client or self.alice
        return who.post(URL, json=body(new_upload(who)))

    def start_ok(self, client: TestClient | None = None) -> str:
        response = self.start(client)
        assert response.status_code == 202, response.text
        return str(response.json()["id"])

    def finish(self, run_id: str, outcome: RunOutcome, reason: RunReason | None = None) -> None:
        """Run the real transitions: queued -> running -> finished, through store.finish_run."""
        with db_of(self.connection) as db:
            assert store.claim_run(db, uuid.UUID(run_id), clock.utcnow())
            assert store.finish_run(
                db,
                uuid.UUID(run_id),
                expected=RunStatus.RUNNING,
                outcome=outcome,
                reason=reason,
                final=None,
                now=clock.utcnow(),
            )

    def start_and_finish(
        self,
        outcome: RunOutcome,
        reason: RunReason | None = None,
        client: TestClient | None = None,
    ) -> str:
        run_id = self.start_ok(client)
        self.finish(run_id, outcome, reason)
        return run_id

    def snapshot(self) -> tuple[int, int, list[tuple[str, int, int]]]:
        """Runs, usage events and every daily counter: what a refused POST must leave untouched."""
        with db_of(self.connection) as db:
            runs = int(db.scalar(select(func.count()).select_from(Run)) or 0)
            events = int(db.scalar(select(func.count()).select_from(UsageEvent)) or 0)
            counters = [
                (r.scope, r.runs, r.model_calls)
                for r in db.scalars(select(UsageDaily).order_by(UsageDaily.scope))
            ]
        return runs, events, counters

    def counter(self, scope: str, day: Any = None) -> int:
        """Runs counted in a usage_daily row (0 when there is no row)."""
        with db_of(self.connection) as db:
            row = db.scalars(
                select(UsageDaily).where(
                    UsageDaily.scope == scope, UsageDaily.day == (day or clock.quota_day())
                )
            ).first()
            return row.runs if row else 0

    def user_scope(self, client: TestClient | None = None) -> str:
        return f"user:{self.user_id(client)}"

    def user_id(self, client: TestClient | None = None) -> uuid.UUID:
        email = "bob@example.com" if client is self.bob else "alice@example.com"
        from app.db.models import User  # noqa: PLC0415

        with db_of(self.connection) as db:
            found = db.scalar(select(User.id).where(User.email == email))
            assert found is not None
            return found


def make_rig_for(
    make_client: MakeClient, connection: Connection, tmp_path: Path, **limits: Any
) -> Rig:
    enqueued: list[uuid.UUID] = []
    app.dependency_overrides[get_enqueue] = lambda: enqueued.append
    app.dependency_overrides[get_session_factory] = lambda: factory_for(connection)
    settings = settings_for(tmp_path, **limits)
    alice = signed_in(make_client, settings, "alice@example.com", 10)
    bob = signed_in(make_client, settings, "bob@example.com", 11)
    return Rig(alice, bob, connection, enqueued)


def session_of(connection: Connection) -> Session:
    return db_of(connection)
