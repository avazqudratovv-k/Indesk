"""`lang` on the Report response comes from the run (runs.lang), with no new column."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, select

from app.core.config import Settings
from app.db.models import User
from tests.ai_helpers import factory_for
from tests.factories import make_claim, make_evidence, make_report, make_run, make_step
from tests.test_auth import MakeClient
from tests.test_uploads import settings_for, signed_in


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return settings_for(tmp_path)


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_the_report_carries_the_language_of_its_run(
    make_client: MakeClient, settings: Settings, db_connection: Connection, lang: str
) -> None:
    alice: TestClient = signed_in(make_client, settings, "alice@example.com", 10)
    factory = factory_for(db_connection)
    with factory() as db, db.begin():
        user = db.scalars(select(User).where(User.email == "alice@example.com")).one()
        run = make_run(db, user, lang=lang)
        make_evidence(db, run, make_step(db, run))
        report = make_report(db, run)
        make_claim(db, report)
        report_id = str(report.id)
    body = alice.get(f"/api/reports/{report_id}")
    assert body.status_code == 200, body.text
    assert body.json()["report"]["lang"] == lang
