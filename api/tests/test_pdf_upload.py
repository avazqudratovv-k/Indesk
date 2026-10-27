"""PDF uploads (P14a). The sandbox is replaced by a fake parser: these tests check what the API does
with its answer (codes, rows, files). The real parser is tested in test_sandbox_parse.py
(-m sandbox)."""

import hashlib
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import sandbox_client
from app.core.config import Settings
from app.core.enums import SandboxErrorCode
from app.db.models import AuditLog, Chunk, DocumentPage, Upload
from app.sandbox_client import PdfParsed, PdfParseOk, PdfParseResult, SandboxError
from tests.pdf_builder import text_pdf
from tests.test_auth import MakeClient
from tests.test_uploads import err, post, settings_for, signed_in, stored_files

PDF = text_pdf(3)
PAGE_TEXT = (
    "Hapjeong station rose 18 percent between 2019 and 2025, the largest rise of any station."
)


def ok(pages: list[str]) -> PdfParseOk:
    return PdfParseOk(parsed=PdfParsed(page_count=len(pages), pages=pages), duration_ms=5)


def refuse(code: SandboxErrorCode) -> SandboxError:
    return SandboxError(code=code, duration_ms=5)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return settings_for(tmp_path)


@pytest.fixture
def parser(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """`state["result"]` is what the fake sandbox answers; `calls` records what it was asked."""
    state: dict[str, Any] = {"result": ok([PAGE_TEXT * 3] * 3), "calls": []}

    def fake(
        pdf: bytes, *, max_pages: int, max_chars: int, timeout: float = 15.0
    ) -> PdfParseResult:
        state["calls"].append((len(pdf), max_pages, max_chars))
        result = state["result"]
        assert isinstance(result, (PdfParseOk, SandboxError))
        return result

    monkeypatch.setattr(sandbox_client, "parse_pdf", fake)
    return state


@pytest.fixture
def alice(make_client: MakeClient, settings: Settings) -> TestClient:
    return signed_in(make_client, settings, "alice@example.com", 10)


def pdf_post(client: TestClient, data: bytes = PDF, name: str = "report.pdf", **kw: Any) -> Any:
    return post(client, data, name, kw.pop("mime", "application/pdf"), **kw)


def test_a_pdf_is_stored_with_its_pages_and_chunks(
    alice: TestClient, settings: Settings, parser: dict[str, Any], db_connection: Any
) -> None:
    response = pdf_post(alice)
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["mime"], body["page_count"], body["row_count"]) == ("application/pdf", 3, None)
    assert (body["status"], body["moderation"]) == ("ready", "pending")
    assert "storage_key" not in response.text and "sha256" not in response.text
    # The sandbox was asked with the limits of limits.toml, not with numbers from the client.
    assert parser["calls"] == [
        (len(PDF), settings.limits.max_pdf_pages, settings.limits.max_pdf_chars)
    ]

    (path,) = stored_files(settings)
    assert path.read_bytes() == PDF
    with Session(bind=db_connection) as db:
        row = db.scalar(select(Upload).where(Upload.id == body["id"]))
        assert row is not None and row.sha256 == hashlib.sha256(PDF).hexdigest()
        pages = db.scalars(select(DocumentPage).order_by(DocumentPage.page)).all()
        assert [p.page for p in pages] == [1, 2, 3]
        assert all(p.owner_id == row.user_id and p.char_count == len(p.text) for p in pages)
        chunks = db.scalars(select(Chunk).order_by(Chunk.ord)).all()
        assert chunks and [c.ord for c in chunks] == list(range(len(chunks)))
        for chunk in chunks:
            page_text = pages[chunk.page - 1].text
            assert page_text[chunk.char_start : chunk.char_end] == chunk.text
            assert chunk.embedding is None and chunk.embedding_model is None
            assert chunk.owner_id == row.user_id
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "upload_created")
            )
            == 1
        )


def test_the_stored_text_is_cleaned(
    alice: TestClient, parser: dict[str, Any], db_connection: Any
) -> None:
    parser["result"] = ok(["Café a\x00b station rose 18 percent. " * 8] * 2)
    assert pdf_post(alice).status_code == 201
    with Session(bind=db_connection) as db:
        text = db.scalars(select(DocumentPage.text)).first()
    assert text is not None and "\x00" not in text and text.startswith("Café ab station")


@pytest.mark.parametrize(
    ("sandbox_code", "status", "code"),
    [
        (SandboxErrorCode.ENCRYPTED, 422, "PDF_ENCRYPTED"),
        (SandboxErrorCode.TOO_MANY_PAGES, 422, "PDF_TOO_MANY_PAGES"),
        (SandboxErrorCode.TOO_MUCH_TEXT, 422, "PDF_TOO_MUCH_TEXT"),
        (SandboxErrorCode.UNREADABLE, 422, "PDF_UNREADABLE"),
        (SandboxErrorCode.TIMEOUT, 422, "PDF_UNREADABLE"),
        (SandboxErrorCode.MEMORY, 422, "PDF_UNREADABLE"),
        (SandboxErrorCode.OUTPUT_TOO_LARGE, 422, "PDF_UNREADABLE"),
        (SandboxErrorCode.BAD_INPUT, 422, "PDF_UNREADABLE"),
        (SandboxErrorCode.UNAVAILABLE, 503, "PARSER_BUSY"),
    ],
)
def test_what_the_sandbox_says_becomes_a_code(
    alice: TestClient,
    settings: Settings,
    parser: dict[str, Any],
    db_connection: Any,
    sandbox_code: SandboxErrorCode,
    status: int,
    code: str,
) -> None:
    parser["result"] = refuse(sandbox_code)
    response = pdf_post(alice)
    err(response, status, code)
    if status == 503:
        assert response.headers["Retry-After"] == "5"
    assert stored_files(settings) == []  # a refused PDF leaves no file
    with Session(bind=db_connection) as db:
        assert db.scalar(select(func.count()).select_from(Upload)) == 0
        assert db.scalar(select(func.count()).select_from(Chunk)) == 0


@pytest.mark.parametrize(
    ("pages", "code"),
    [
        ([""] * 4, "PDF_NO_TEXT"),  # a scan: pages, no text
        (["tiny"] * 3, "PDF_NO_TEXT"),  # under pdf_min_text_chars in total
        ([PAGE_TEXT * 3, "", "", ""], "PDF_NO_TEXT"),  # text on fewer than half of the pages
        ([PAGE_TEXT] * 31, "PDF_TOO_MANY_PAGES"),  # the sandbox allowed it, the policy says no
        (["x" * 60_000] * 3, "PDF_TOO_MUCH_TEXT"),
    ],
    ids=["scan", "tiny", "mostly-blank", "31-pages", "too-much-text"],
)
def test_the_page_and_text_policy_is_applied_here(
    alice: TestClient, parser: dict[str, Any], pages: list[str], code: str
) -> None:
    parser["result"] = ok(pages)
    err(pdf_post(alice), 422, code)


def test_half_the_pages_with_text_is_enough(alice: TestClient, parser: dict[str, Any]) -> None:
    parser["result"] = ok([PAGE_TEXT * 3, ""])
    assert pdf_post(alice).status_code == 201


@pytest.mark.parametrize(
    ("name", "mime", "data", "code"),
    [
        ("report.pdf", "text/csv", PDF, "TYPE_MISMATCH"),
        ("report.pdf", "image/png", PDF, "TYPE_MISMATCH"),
        ("report.pdf", "application/pdf", b"a,b\n1,2\n", "TYPE_MISMATCH"),  # not a PDF inside
        ("report.pdf", "application/pdf", b"PK\x03\x04" + b"\x00" * 50, "TYPE_MISMATCH"),
    ],
)
def test_declared_type_and_magic_number(
    alice: TestClient, parser: dict[str, Any], name: str, mime: str, data: bytes, code: str
) -> None:
    err(pdf_post(alice, data, name, mime=mime), 415, code)
    assert parser["calls"] == []  # the sandbox is not asked about something that is not a PDF


def test_an_empty_pdf_and_an_oversized_pdf(
    make_client: MakeClient, tmp_path: Path, parser: dict[str, Any]
) -> None:
    client = signed_in(
        make_client, settings_for(tmp_path, max_file_bytes=len(PDF) - 1), "b@example.com", 11
    )
    err(pdf_post(client, b""), 422, "EMPTY_FILE")
    err(pdf_post(client), 413, "FILE_TOO_LARGE")
    assert parser["calls"] == []


def test_csv_uploads_do_not_touch_the_parser(alice: TestClient, parser: dict[str, Any]) -> None:
    assert post(alice).status_code == 201
    assert parser["calls"] == []


def test_uppercase_extension_goes_the_pdf_way(alice: TestClient, parser: dict[str, Any]) -> None:
    assert pdf_post(alice, name="REPORT.PDF").status_code == 201
    assert len(parser["calls"]) == 1


def test_a_database_failure_leaves_no_file(
    alice: TestClient,
    settings: Settings,
    parser: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args: Any, **kwargs: Any) -> list[Any]:
        raise RuntimeError("database trouble")

    monkeypatch.setattr("app.services.chunking.chunk_document", boom)
    assert pdf_post(alice).status_code == 500
    assert stored_files(settings) == []


def test_the_pdf_route_is_only_for_the_owner_of_the_rows(
    make_client: MakeClient,
    settings: Settings,
    parser: dict[str, Any],
    db_connection: Any,
) -> None:
    alice = signed_in(make_client, settings, "alice@example.com", 10)
    bob = signed_in(make_client, settings, "bob@example.com", 11)
    upload_id = pdf_post(alice).json()["id"]
    assert bob.get(f"/api/uploads/{upload_id}").status_code == 404
    assert bob.delete(f"/api/uploads/{upload_id}").status_code == 404
    with Session(bind=db_connection) as db:
        assert (
            db.scalar(select(func.count()).select_from(Chunk)) or 0
        ) > 0  # bob's delete changed nothing
