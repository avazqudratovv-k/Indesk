"""Every way a PDF upload is refused (P14b): the code, and that a refusal leaves NOTHING behind: no
model call (no ai_calls row), no usage event or counter, no upload, page or chunk row, no stored
file. A refused PDF is also never a used free run (an upload is not a run).

Two matrices: the default one answers the sandbox with a fake parser and checks what the API does
with it; the `parser` ones send real PDFs to the running parser service (run them from the api
container: `docker compose run --rm api pytest -m parser`)."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import sandbox_client
from app.core.config import Settings
from app.core.enums import SandboxErrorCode
from app.db.models import AiCall, Chunk, DocumentPage, Upload, UsageDaily, UsageEvent
from app.sandbox_client import PdfParsed, PdfParseOk, PdfParseResult, SandboxError
from tests.pdf_builder import build_pdf, sentences, text_pdf
from tests.test_auth import MakeClient
from tests.test_uploads import err, post, settings_for, signed_in, stored_files

PDF = text_pdf(3)
PAGE_TEXT = (
    "Hapjeong station rose 18 percent between 2019 and 2025, the largest rise of any station."
)
TABLES = (AiCall, UsageEvent, UsageDaily, Upload, DocumentPage, Chunk)


def assert_nothing_left(db: Any, settings: Settings) -> None:
    """The refusal left no model call, no usage, no rows and no file."""
    with Session(bind=db) as session:
        counts = {t.__name__: session.scalar(select(func.count()).select_from(t)) for t in TABLES}
    assert counts == {t.__name__: 0 for t in TABLES}
    assert stored_files(settings) == []


def pdf_post(client: TestClient, data: bytes = PDF, mime: str = "application/pdf") -> Any:
    return post(client, data, "report.pdf", mime)


# ---- the default matrix: a fake parser ----


@pytest.fixture
def parser(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"result": None, "calls": 0}

    def fake(
        pdf: bytes, *, max_pages: int, max_chars: int, timeout: float = 15.0
    ) -> PdfParseResult:
        state["calls"] += 1
        result = state["result"]
        assert isinstance(result, (PdfParseOk, SandboxError))
        return result

    monkeypatch.setattr(sandbox_client, "parse_pdf", fake)
    return state


def pages(texts: list[str]) -> PdfParseOk:
    return PdfParseOk(parsed=PdfParsed(page_count=len(texts), pages=texts), duration_ms=5)


def refused(code: SandboxErrorCode) -> SandboxError:
    return SandboxError(code=code, duration_ms=5)


@pytest.mark.parametrize(
    ("result", "status", "code"),
    [
        (pages([""] * 4), 422, "PDF_NO_TEXT"),  # a scan: pages and no text
        (pages(["tiny"] * 3), 422, "PDF_NO_TEXT"),  # under pdf_min_text_chars
        (pages([PAGE_TEXT * 3, "", "", ""]), 422, "PDF_NO_TEXT"),  # fewer than half have text
        (pages([PAGE_TEXT] * 31), 422, "PDF_TOO_MANY_PAGES"),  # the policy, after the parse
        (pages(["x" * 60_000] * 3), 422, "PDF_TOO_MUCH_TEXT"),
        (refused(SandboxErrorCode.TOO_MANY_PAGES), 422, "PDF_TOO_MANY_PAGES"),
        (refused(SandboxErrorCode.TOO_MUCH_TEXT), 422, "PDF_TOO_MUCH_TEXT"),
        (refused(SandboxErrorCode.ENCRYPTED), 422, "PDF_ENCRYPTED"),
        (refused(SandboxErrorCode.UNREADABLE), 422, "PDF_UNREADABLE"),
        (refused(SandboxErrorCode.TIMEOUT), 422, "PDF_UNREADABLE"),
        (refused(SandboxErrorCode.UNAVAILABLE), 503, "PARSER_BUSY"),
    ],
    ids=[
        "scan", "tiny", "mostly-blank", "31-pages", "too-much-text", "sandbox-pages",
        "sandbox-text", "encrypted", "unreadable", "timeout", "parser-busy",
    ],
)  # fmt: skip
def test_a_refused_pdf_leaves_nothing_behind(
    make_client: MakeClient,
    tmp_path: Path,
    db_connection: Any,
    parser: dict[str, Any],
    result: Any,
    status: int,
    code: str,
) -> None:
    settings = settings_for(tmp_path)
    client = signed_in(make_client, settings, "alice@example.com", 10)
    parser["result"] = result
    err(pdf_post(client), status, code)
    assert_nothing_left(db_connection, settings)


def test_a_refused_pdf_is_not_a_used_free_run(
    make_client: MakeClient, tmp_path: Path, db_connection: Any, parser: dict[str, Any]
) -> None:
    settings = settings_for(tmp_path)
    client = signed_in(make_client, settings, "alice@example.com", 10)
    parser["result"] = pages([""] * 3)
    err(pdf_post(client), 422, "PDF_NO_TEXT")
    usage = client.get("/api/usage").json()
    assert usage["free_runs_used"] == 0
    assert_nothing_left(db_connection, settings)


@pytest.mark.parametrize(
    ("data", "mime", "status", "code"),
    [
        (b"", "application/pdf", 422, "EMPTY_FILE"),
        (PDF, "text/csv", 415, "TYPE_MISMATCH"),
        (b"a,b\n1,2\n", "application/pdf", 415, "TYPE_MISMATCH"),  # not a PDF inside
    ],
    ids=["empty", "wrong-mime", "not-a-pdf"],
)
def test_a_pdf_refused_before_the_parser_leaves_nothing_and_never_asks_it(
    make_client: MakeClient,
    tmp_path: Path,
    db_connection: Any,
    parser: dict[str, Any],
    data: bytes,
    mime: str,
    status: int,
    code: str,
) -> None:
    settings = settings_for(tmp_path)
    client = signed_in(make_client, settings, "alice@example.com", 10)
    err(pdf_post(client, data, mime), status, code)
    assert parser["calls"] == 0
    assert_nothing_left(db_connection, settings)


def test_an_oversized_pdf_is_refused_before_the_parser(
    make_client: MakeClient, tmp_path: Path, db_connection: Any, parser: dict[str, Any]
) -> None:
    settings = settings_for(tmp_path, max_file_bytes=len(PDF) - 1)
    client = signed_in(make_client, settings, "alice@example.com", 10)
    err(pdf_post(client), 413, "FILE_TOO_LARGE")
    assert parser["calls"] == 0
    assert_nothing_left(db_connection, settings)


# ---- the same, with real PDFs and the running parser service ----


@pytest.mark.parser
@pytest.mark.parametrize(
    ("make_pdf", "limits", "status", "code"),
    [
        (lambda: build_pdf([[""]] * 3, image_only=True), {}, 422, "PDF_NO_TEXT"),  # a scan
        (lambda: build_pdf([sentences(3)], encrypted=True), {}, 422, "PDF_ENCRYPTED"),
        (lambda: text_pdf(3)[:700], {}, 422, "PDF_UNREADABLE"),  # truncated
        (lambda: b"%PDF-1.7\n" + bytes(range(256)) * 40, {}, 422, "PDF_UNREADABLE"),  # noise
        (lambda: text_pdf(5), {"max_pdf_pages": 4}, 422, "PDF_TOO_MANY_PAGES"),
        (lambda: text_pdf(3), {"max_pdf_chars": 500}, 422, "PDF_TOO_MUCH_TEXT"),
    ],
    ids=["scan", "encrypted", "truncated", "noise", "too-many-pages", "too-much-text"],
)
def test_real_pdfs_are_refused_and_leave_nothing_behind(
    make_client: MakeClient,
    tmp_path: Path,
    db_connection: Any,
    make_pdf: Any,
    limits: dict[str, int],
    status: int,
    code: str,
) -> None:
    settings = settings_for(tmp_path, **limits)
    client = signed_in(make_client, settings, "alice@example.com", 10)
    err(pdf_post(client, make_pdf()), status, code)
    assert_nothing_left(db_connection, settings)


@pytest.mark.parser
def test_a_real_good_pdf_is_accepted_after_the_refusals(
    make_client: MakeClient, tmp_path: Path
) -> None:
    """The parser still works after a run of refusals (a refusal does not wedge it)."""
    settings = settings_for(tmp_path)
    client = signed_in(make_client, settings, "alice@example.com", 10)
    err(pdf_post(client, build_pdf([[""]] * 3, image_only=True)), 422, "PDF_NO_TEXT")
    assert pdf_post(client).status_code == 201
