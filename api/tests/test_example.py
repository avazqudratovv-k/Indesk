"""GET /api/example: the cached report. No login, no database, no Redis, no model, and the file
carries nothing internal (Beaver's code, the plan, the payload columns, a real id)."""

import json
import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.ai.gateway import Gateway
from app.ai.real_client import GeminiRestClient
from app.db.session import get_db
from app.example import EXAMPLE_PATH, build_example, load_example
from app.main import app
from app.routers.deps import get_redis
from app.schemas.reports import ReportDetail

SENTINEL_CODE = "SENTINEL_CODE_c41e"
SENTINEL_COLUMN = "SENTINEL_COLUMN_9b02"
SENTINEL_ID = "5e47a2c4-0000-4000-8000-5e47a2c40001"
SENTINEL_FILE = "SENTINEL_PRIVATE_FILE.csv"
FORBIDDEN = [SENTINEL_CODE, SENTINEL_COLUMN, SENTINEL_ID, SENTINEL_FILE, "run_python(", "groupby"]
FORBIDDEN_KEYS = {"code", "columns", "plan", "group_by", "prompt_version", "time_column", "top_n"}
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def raise_if_called(*_: Any, **__: Any) -> Any:
    raise AssertionError("the example must not touch the database, Redis or a model")


@pytest.fixture
def bare_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A client whose database, Redis and model client all fail the test if they are used."""
    app.dependency_overrides[get_db] = raise_if_called
    app.dependency_overrides[get_redis] = raise_if_called
    monkeypatch.setattr(Gateway, "ask", raise_if_called)
    monkeypatch.setattr(GeminiRestClient, "generate", raise_if_called)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_a_hundred_calls_all_answer_without_login_database_or_model(
    bare_client: TestClient,
) -> None:
    expected = bare_client.get("/api/example").json()
    for _ in range(100):
        response = bare_client.get("/api/example")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "public, max-age=300"
        assert response.json() == expected
    assert "set-cookie" not in response.headers


def test_the_response_is_a_valid_report_detail(bare_client: TestClient) -> None:
    body = bare_client.get("/api/example").json()
    detail = ReportDetail.model_validate(body)
    assert detail.report.lang == "en" and detail.report.expires_at.year >= 2099
    assert detail.report.total_claims == len(detail.claims) > 0
    assert {r for c in detail.claims for r in c.evidence_refs} <= {e.ref for e in detail.evidence}


def test_a_broken_example_file_is_caught_when_it_is_loaded() -> None:
    load_example.cache_clear()
    good = EXAMPLE_PATH.read_text(encoding="utf-8")
    try:
        EXAMPLE_PATH.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="validation error"):
            load_example()
    finally:
        EXAMPLE_PATH.write_text(good, encoding="utf-8")
        load_example.cache_clear()


# ---- the example carries nothing internal ----


def dirty_source() -> ReportDetail:
    """A report as the database would give it, with a sentinel in every place that must not leak."""
    source = load_example().model_dump(mode="json", exclude_unset=True)
    source["report"].update(id=SENTINEL_ID, run_id=SENTINEL_ID, owner_id=SENTINEL_ID)
    source["report"]["pdf_key"] = SENTINEL_FILE
    for claim in source["claims"]:
        claim.update(id=SENTINEL_ID, report_id=SENTINEL_ID)
    for evidence in source["evidence"]:
        evidence.update(id=SENTINEL_ID, run_id=SENTINEL_ID, step_id=SENTINEL_ID)
        evidence["file_name"] = SENTINEL_FILE
        evidence["payload"].update(code=SENTINEL_CODE, columns=[SENTINEL_COLUMN])
    return ReportDetail.model_validate(source)


def all_keys(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from all_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from all_keys(item)


def test_the_builder_drops_every_sentinel() -> None:
    built = build_example(dirty_source())
    text = json.dumps(built, ensure_ascii=False)
    for sentinel in FORBIDDEN:
        assert sentinel not in text
    assert not FORBIDDEN_KEYS & set(all_keys(built))
    assert built["report"]["pdf_key"] is None
    assert {e["file_name"] for e in built["evidence"]} == {"seoul-subway-ridership.csv"}
    ReportDetail.model_validate(built)  # still a valid report


def test_the_example_file_carries_no_code_plan_payload_or_real_id() -> None:
    raw = EXAMPLE_PATH.read_text(encoding="utf-8")
    body = json.loads(raw)
    assert not FORBIDDEN_KEYS & set(all_keys(body))
    assert set(UUID.findall(raw)) == {"00000000-0000-0000-0000-000000000000"}
    for needle in ("run_python(", "groupby", "import pandas", "def ", "SELECT "):
        assert needle not in raw
    assert {e["file_name"] for e in body["evidence"]} == {"seoul-subway-ridership.csv"}


def test_the_example_reads_like_a_finished_english_report() -> None:
    detail = load_example()
    texts = [detail.report.title, detail.report.summary_json.answer]
    texts += [c.text for c in detail.claims]
    assert not any(re.search(r"[ㄱ-힝]", t) for t in texts)  # no Korean
    assert not any("_" in t for t in texts)  # no raw column name
    assert all(c.status == "verified" for c in detail.claims)
    labels = [r.label for r in detail.report.summary_json.top_rows or []]
    assert len(labels) == len(set(labels))
