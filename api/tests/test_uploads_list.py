"""GET /api/uploads: the limit and include_deleted parameters."""

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import Settings
from app.db.models import Upload
from tests.test_auth import MakeClient
from tests.test_uploads import URL, err, post, settings_for, signed_in


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return settings_for(tmp_path)


@pytest.fixture
def alice(make_client: MakeClient, settings: Settings) -> TestClient:
    return signed_in(make_client, settings, "alice@example.com", 10)


def test_limit_default_cap_and_validation(alice: TestClient) -> None:
    for n in range(3):
        post(alice, name=f"f{n}.csv")
    assert len(alice.get(URL).json()) == 3
    assert len(alice.get(f"{URL}?limit=2").json()) == 2
    assert len(alice.get(f"{URL}?limit=100").json()) == 3
    for bad in ("0", "101", "-1", "x"):
        err(alice.get(f"{URL}?limit={bad}"), 422, "VALIDATION_ERROR")


def test_include_deleted_lists_deleted_rows_but_not_unswept_expired_ones(
    alice: TestClient, db_connection: Any
) -> None:
    keep = post(alice, name="keep.csv").json()
    gone = post(alice, name="gone.csv").json()
    old = post(alice, name="old.csv").json()
    assert alice.delete(f"{URL}/{gone['id']}").status_code == 204
    with Session(bind=db_connection) as db:
        db.execute(
            update(Upload)
            .where(Upload.id == old["id"])
            .values(expires_at=clock.utcnow() - timedelta(seconds=1))
        )
        db.commit()
    assert [u["id"] for u in alice.get(URL).json()] == [keep["id"]]
    assert [u["id"] for u in alice.get(f"{URL}?include_deleted=false").json()] == [keep["id"]]
    listed = alice.get(f"{URL}?include_deleted=true").json()
    assert [(u["id"], u["status"]) for u in listed] == [
        (gone["id"], "deleted"),
        (keep["id"], "ready"),
    ]
    assert "storage_key" not in str(listed)
    limited = alice.get(f"{URL}?include_deleted=true&limit=1").json()
    assert [u["id"] for u in limited] == [gone["id"]]


def test_include_deleted_never_shows_another_users_rows(
    alice: TestClient, make_client: MakeClient, settings: Settings
) -> None:
    mine = post(alice).json()
    assert alice.delete(f"{URL}/{mine['id']}").status_code == 204
    bob = signed_in(make_client, settings, "bob@example.com", 21)
    assert bob.get(f"{URL}?include_deleted=true").json() == []
