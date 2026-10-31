"""The PDF run through the HTTP API (P14b): upload, run, GET /runs, the stream and GET /reports,
with the fake parser and the fake model client. What the web will read for a PDF: the upload
fields, the quote and page on a claim, the passage evidence, a summary without `top_rows`,
ownership, and the delete of the text and the vectors with the upload."""

import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, func, select

from app import sandbox_client
from app.core.config import Settings
from app.db.models import Chunk, DocumentPage, Run, RunFile
from app.main import app
from app.routers.runs import get_enqueue, get_session_factory
from app.runs.executor import run_job
from app.schemas.reports import ReportDetail
from tests.ai_helpers import factory_for
from tests.pdf_builder import text_pdf
from tests.pdf_run_helpers import GOOD_QUOTE, PAGES, QUESTION, pdf_rig, writer_answer
from tests.runs_helpers import World
from tests.test_auth import MakeClient
from tests.test_uploads import post as upload_file
from tests.test_uploads import settings_for, signed_in

PDF = text_pdf(3)
PAGE_TEXT = (
    "Hapjeong station rose 18 percent between 2019 and 2025, the largest rise of any station."
)


@pytest.fixture
def enqueued() -> list[uuid.UUID]:
    return []


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return settings_for(tmp_path)


@pytest.fixture(autouse=True)
def _wire(db_connection: Connection, enqueued: list[uuid.UUID]) -> None:
    app.dependency_overrides[get_enqueue] = lambda: enqueued.append
    app.dependency_overrides[get_session_factory] = lambda: factory_for(db_connection)


@pytest.fixture
def parsed(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """`state["pages"]` is what the fake parser returns."""
    state: dict[str, list[str]] = {"pages": list(PAGES)}

    def fake(
        pdf: bytes, *, max_pages: int, max_chars: int, timeout: float = 15.0
    ) -> sandbox_client.PdfParseResult:
        texts = state["pages"]
        parsed_pages = sandbox_client.PdfParsed(page_count=len(texts), pages=texts)
        return sandbox_client.PdfParseOk(parsed=parsed_pages, duration_ms=5)

    monkeypatch.setattr(sandbox_client, "parse_pdf", fake)
    return state


@pytest.fixture
def alice(make_client: MakeClient, settings: Settings) -> TestClient:
    return signed_in(make_client, settings, "alice@example.com", 10)


@pytest.fixture
def bob(make_client: MakeClient, settings: Settings) -> TestClient:
    return signed_in(make_client, settings, "bob@example.com", 11)


@pytest.fixture
def anonymous(make_client: MakeClient, settings: Settings) -> TestClient:
    return make_client(settings, peer=("203.0.113.99", 50000))


def upload_pdf(client: TestClient) -> dict[str, Any]:
    response = upload_file(client, PDF, "report.pdf", "application/pdf")
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def finished_pdf_run(client: TestClient, db_connection: Connection, upload_id: str) -> uuid.UUID:
    factory = factory_for(db_connection)
    started = client.post(
        "/api/runs",
        json={
            "mode": "ask",
            "question": QUESTION,
            "files": [{"upload_id": upload_id, "role": "subject"}],
        },
    )
    assert started.status_code == 202, started.text
    run_id = uuid.UUID(started.json()["id"])
    with factory() as db:
        user_id = db.scalar(select(Run.user_id).where(Run.id == run_id))
        uploads = tuple(db.scalars(select(RunFile.upload_id).where(RunFile.run_id == run_id)))
    assert user_id is not None
    world = World(user_id, run_id, uploads)
    rig, _ = pdf_rig(factory, world, writer_answer([GOOD_QUOTE], [2], values=["18 percent"]))
    run_job(run_id, rig.deps)
    return run_id


# ---- the upload response ----


def test_a_pdf_upload_reports_its_pages(alice: TestClient, parsed: dict[str, list[str]]) -> None:
    body = upload_pdf(alice)
    assert (body["mime"], body["page_count"], body["row_count"]) == ("application/pdf", 3, None)
    assert body["status"] == "ready"  # parsed and chunked before the 201: no parsing state to poll
    assert body["pages_without_text"] == 0
    assert alice.get(f"/api/uploads/{body['id']}").json()["pages_without_text"] == 0
    (listed,) = alice.get("/api/uploads").json()
    assert listed["pages_without_text"] == 0


def test_pages_without_text_counts_the_blank_pages_from_the_stored_text(
    alice: TestClient, parsed: dict[str, list[str]]
) -> None:
    parsed["pages"] = [PAGE_TEXT * 3, PAGE_TEXT * 3, "   \n  ", "tiny"]  # 2 of 4 have text
    body = upload_pdf(alice)
    assert body["page_count"] == 4 and body["pages_without_text"] == 2
    assert alice.get(f"/api/uploads/{body['id']}").json()["pages_without_text"] == 2


def test_a_csv_upload_has_no_such_field(alice: TestClient) -> None:
    response = upload_file(alice)
    assert response.status_code == 201
    assert "pages_without_text" not in response.json()


# ---- the run and the report ----


def test_a_pdf_report_has_quotes_pages_and_no_top_rows(
    alice: TestClient, db_connection: Connection, parsed: dict[str, list[str]]
) -> None:
    upload = upload_pdf(alice)
    run_id = finished_pdf_run(alice, db_connection, upload["id"])

    run = alice.get(f"/api/runs/{run_id}")
    assert run.status_code == 200 and run.json()["outcome"] == "answered"
    assert [s["key"] for s in run.json()["steps"]][2:4] == ["search", "bestPassage"]
    events = alice.get(f"/api/runs/{run_id}/events")
    assert "event: done" in events.text
    for body in (run.text, events.text):
        assert "Hapjeong" not in body  # no passage text on the trace or in the stream
        assert '"payload"' not in body

    report_id = run.json()["report_id"]
    report = alice.get(f"/api/reports/{report_id}")
    assert report.status_code == 200, report.text
    detail = report.json()
    ReportDetail.model_validate(detail)  # the schema the web reads accepts a PDF report
    summary = detail["report"]["summary_json"]
    assert "top_rows" not in summary and summary["in_short"]
    (claim,) = detail["claims"]
    assert (claim["status"], claim["origin"]) == ("verified", "document")
    assert (claim["doc_quote"], claim["doc_location"], claim["doc_value"]) == (
        GOOD_QUOTE, "p2", "18 percent",
    )  # fmt: skip
    passage = next(e for e in detail["evidence"] if e["type"] == "passage")
    assert passage["location"] == "page 2" and passage["file_name"] == "report.pdf"
    assert passage["payload"]["quote"] == GOOD_QUOTE
    assert set(passage["payload"]) <= {"quote", "reason", "text", "title", "body"}
    assert passage["ref"] in claim["evidence_refs"]


def test_another_user_cannot_read_a_pdf_report(
    alice: TestClient,
    bob: TestClient,
    anonymous: TestClient,
    db_connection: Connection,
    parsed: dict[str, list[str]],
) -> None:
    run_id = finished_pdf_run(alice, db_connection, upload_pdf(alice)["id"])
    report_id = alice.get(f"/api/runs/{run_id}").json()["report_id"]
    assert bob.get(f"/api/reports/{report_id}").json() == {"error": {"code": "NOT_FOUND"}}
    assert bob.get(f"/api/runs/{run_id}").status_code == 404
    assert anonymous.get(f"/api/reports/{report_id}").status_code == 401


# ---- delete ----


def test_deleting_the_upload_deletes_its_text_and_vectors_but_not_the_report(
    alice: TestClient, db_connection: Connection, parsed: dict[str, list[str]]
) -> None:
    upload = upload_pdf(alice)
    run_id = finished_pdf_run(alice, db_connection, upload["id"])
    report_id = alice.get(f"/api/runs/{run_id}").json()["report_id"]
    factory = factory_for(db_connection)
    upload_id = uuid.UUID(upload["id"])
    with factory() as db:
        embedded = db.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.embedding.is_not(None))
        )
        assert embedded and embedded > 0  # the run made vectors

    assert alice.delete(f"/api/uploads/{upload['id']}").status_code == 204
    with factory() as db:
        for table in (Chunk, DocumentPage):
            count = db.scalar(
                select(func.count()).select_from(table).where(table.upload_id == upload_id)
            )
            assert count == 0
    assert alice.get(f"/api/uploads/{upload['id']}").status_code == 404
    kept = alice.get(f"/api/reports/{report_id}").json()  # the evidence snapshot stays
    passage = next(e for e in kept["evidence"] if e["type"] == "passage")
    assert passage["payload"]["quote"] == GOOD_QUOTE


def test_a_pdf_upload_cannot_be_deleted_by_someone_else(
    alice: TestClient, bob: TestClient, db_connection: Connection, parsed: dict[str, list[str]]
) -> None:
    upload = upload_pdf(alice)
    assert bob.delete(f"/api/uploads/{upload['id']}").status_code == 404
    with factory_for(db_connection)() as db:
        assert db.scalar(select(func.count()).select_from(DocumentPage)) == 3
