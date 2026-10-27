"""PDF parse jobs against the RUNNING parser service (P14a). Not part of the default `pytest`. The
parser is its own container on parse_net, which only the api shares, so run these from the api:

    docker compose up -d --build parser
    docker compose run --rm api pytest -m parser

Every case ends in a fixed code, within the limits, and the next parse still works.
"""

import base64
import json
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

import pytest

from app.core.config import get_settings
from app.core.enums import SandboxErrorCode
from app.sandbox_client import PdfParseOk, SandboxError, parse_pdf
from tests.pdf_builder import bomb_content, build_pdf, sentences, text_pdf

pytestmark = pytest.mark.parser

PAGES, CHARS = 30, 150_000


def post(path: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        get_settings().parser_url.rstrip("/") + path, data=json.dumps(body).encode(), method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def raw(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return post("/parse-pdf", body)


def request_for(pdf: bytes, **over: Any) -> dict[str, Any]:
    return {
        "job_id": str(uuid.uuid4()),
        "pdf_b64": base64.b64encode(pdf).decode(),
        "max_pages": PAGES,
        "max_chars": CHARS,
        **over,
    }


def code_of(pdf: bytes, **kw: int) -> SandboxErrorCode:
    result = parse_pdf(
        pdf, max_pages=kw.get("max_pages", PAGES), max_chars=kw.get("max_chars", CHARS)
    )
    assert isinstance(result, SandboxError), result
    return result.code


@pytest.fixture(autouse=True)
def _the_next_parse_still_works() -> Any:
    yield
    result = parse_pdf(text_pdf(1), max_pages=PAGES, max_chars=CHARS)
    assert isinstance(result, PdfParseOk), result


def test_a_text_pdf_comes_back_page_by_page() -> None:
    result = parse_pdf(text_pdf(3, lines=5), max_pages=PAGES, max_chars=CHARS)
    assert isinstance(result, PdfParseOk)
    assert result.parsed.page_count == 3 and len(result.parsed.pages) == 3
    assert "Line 2 of page 2" in result.parsed.pages[1]
    assert "Line 2 of page 1" not in result.parsed.pages[1]


def test_korean_text_is_read_through_its_unicode_map() -> None:
    line = "서울 지하철 2호선 승차 인원은 1,234명이다."
    result = parse_pdf(
        build_pdf([[line, "합정역 환승"]], korean=True), max_pages=PAGES, max_chars=CHARS
    )
    assert isinstance(result, PdfParseOk)
    assert line in result.parsed.pages[0] and "합정역 환승" in result.parsed.pages[0]


def test_a_scan_has_pages_and_no_text() -> None:
    result = parse_pdf(build_pdf([[""]] * 3, image_only=True), max_pages=PAGES, max_chars=CHARS)
    assert isinstance(result, PdfParseOk)
    assert result.parsed.page_count == 3 and not any(p.strip() for p in result.parsed.pages)


def test_an_encrypted_pdf_is_refused_without_a_password_attempt() -> None:
    assert code_of(build_pdf([sentences(3)], encrypted=True)) is SandboxErrorCode.ENCRYPTED


def test_too_many_pages_and_too_much_text_are_fixed_codes() -> None:
    assert code_of(text_pdf(5), max_pages=4) is SandboxErrorCode.TOO_MANY_PAGES
    assert code_of(text_pdf(3), max_chars=100) is SandboxErrorCode.TOO_MUCH_TEXT


@pytest.mark.parametrize(
    "pdf",
    [
        text_pdf(3)[:700],
        b"%PDF-1.4 and then nothing useful",
        b"%PDF-1.7\n" + bytes(range(256)) * 40,
    ],
    ids=["truncated", "garbage-after-header", "binary-noise"],
)
def test_damaged_files_are_unreadable_not_errors(pdf: bytes) -> None:
    assert code_of(pdf) is SandboxErrorCode.UNREADABLE


def test_a_stream_bomb_ends_in_a_fixed_code_inside_the_limits() -> None:
    started = time.monotonic()
    code = code_of(build_pdf([[""]], content=bomb_content(2_500_000)))
    assert code in {SandboxErrorCode.UNREADABLE, SandboxErrorCode.TIMEOUT, SandboxErrorCode.MEMORY}
    assert time.monotonic() - started < 15


def test_bad_requests_are_400_with_a_fixed_code() -> None:
    good = request_for(text_pdf(1))
    for bad in (
        {**good, "pdf_b64": "!!!not base64"},
        {**good, "pdf_b64": ""},
        {**good, "max_pages": 0},
        {**good, "max_pages": 100_000},
        {**good, "max_chars": True},
        {**good, "job_id": "../x"},
        {k: v for k, v in good.items() if k != "max_chars"},
    ):
        status, body = raw(bad)
        assert status == 400 and body["error"] == "bad_input", bad.keys()


def test_a_second_parse_is_refused_at_once_while_one_runs() -> None:
    """One parse slot. While a slow parse runs, a second one is answered `unavailable`
    (PARSER_BUSY in the API) without waiting. (A pandas run is another container, never held up.)"""
    slow = build_pdf([[""]], content=bomb_content(200_000))  # valid but heavy: seconds of CPU
    outcome: dict[str, Any] = {}

    def run_slow() -> None:
        outcome["result"] = parse_pdf(slow, max_pages=PAGES, max_chars=200_000)

    thread = threading.Thread(target=run_slow)
    thread.start()
    time.sleep(1.0)  # let it start
    started = time.monotonic()
    second = parse_pdf(text_pdf(1), max_pages=PAGES, max_chars=CHARS)
    refused_in = time.monotonic() - started
    thread.join(timeout=30)

    assert isinstance(second, SandboxError) and second.code is SandboxErrorCode.UNAVAILABLE
    assert refused_in < 1.0
    assert isinstance(outcome["result"], PdfParseOk)  # the slow parse itself finished fine


def test_the_parser_has_no_run_route() -> None:
    """The parser is parse-only: a perfectly good /run request is a 404, not a pandas job."""
    body = {
        "job_id": str(uuid.uuid4()),
        "code": "result = 1",
        "csv_b64": base64.b64encode(b"a\n1\n").decode(),
        "check_ast": False,
    }
    status, answer = post("/run", body)
    assert status == 404 and answer == {"ok": False, "error": "bad_input"}


def test_the_api_cannot_resolve_the_sandbox_and_does_resolve_the_parser() -> None:
    """parse_net holds the api and the parser only; the model-code sandbox is elsewhere."""
    import socket  # noqa: PLC0415

    with pytest.raises(OSError):
        socket.gethostbyname("sandbox")
    assert socket.gethostbyname("parser")
