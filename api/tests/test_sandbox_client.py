"""run_pandas never raises, and never logs the code or the data. A fake HTTP server stands in for
the sandbox service."""

import json
import logging
import threading
import time
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace
from typing import Any

import pytest

from app import sandbox_client
from app.core.enums import SandboxErrorCode
from app.sandbox_client import SandboxError, SandboxOk, run_pandas

SECRET_CODE = "result = 'CODE-CANARY-7f3a'"
SECRET_CSV = b"name,value\nCSV-CANARY-9c1d,1\n"

Reply = tuple[int, bytes] | Callable[[bytes], tuple[int, bytes]]


class Fake:
    def __init__(self) -> None:
        self.reply: Reply = (200, b"{}")
        self.delay = 0.0
        self.seen: list[dict[str, Any]] = []


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Iterator[Fake]:
    state = Fake()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            state.seen.append(json.loads(body))
            time.sleep(state.delay)
            status, payload = state.reply(body) if callable(state.reply) else state.reply
            self.send_response(status)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(
        sandbox_client, "get_settings", lambda: SimpleNamespace(sandbox_url=url, parser_url=url)
    )
    yield state
    server.shutdown()
    server.server_close()


def answer(status: int, payload: Any) -> tuple[int, bytes]:
    return status, json.dumps(payload).encode()


def test_ok_answer(fake: Fake) -> None:
    fake.reply = answer(200, {"ok": True, "result": {"a": [1, 2]}, "duration_ms": 12})
    result = run_pandas("result = 1", b"a\n1\n")
    assert isinstance(result, SandboxOk) and result.result == {"a": [1, 2]}
    sent = fake.seen[0]
    assert set(sent) == {"job_id", "code", "csv_b64"}  # the client never sets check_ast


JOB_CODES = [c for c in SandboxErrorCode if c is not SandboxErrorCode.UNAVAILABLE]


@pytest.mark.parametrize("code", JOB_CODES)
def test_every_fixed_code_comes_back_typed(fake: Fake, code: SandboxErrorCode) -> None:
    fake.reply = answer(200, {"ok": False, "error": code.value, "duration_ms": 3})
    result = run_pandas("x", b"a\n1\n")
    assert isinstance(result, SandboxError) and result.code is code


@pytest.mark.parametrize(
    ("status", "payload", "expected"),
    [
        (503, b'{"ok": false, "error": "unavailable"}', SandboxErrorCode.UNAVAILABLE),
        (500, b"boom", SandboxErrorCode.UNAVAILABLE),
        (404, b"", SandboxErrorCode.UNAVAILABLE),
        (400, b'{"ok": false, "error": "bad_input"}', SandboxErrorCode.BAD_INPUT),
        (413, b"too big", SandboxErrorCode.BAD_INPUT),
        (200, b"not json", SandboxErrorCode.UNAVAILABLE),
        (200, b"[1, 2]", SandboxErrorCode.UNAVAILABLE),
        (200, b'{"ok": false, "error": "made_up"}', SandboxErrorCode.UNAVAILABLE),
        (200, b'{"ok": true}', SandboxErrorCode.UNAVAILABLE),
        (200, b"x" * (3 * 1024 * 1024), SandboxErrorCode.UNAVAILABLE),
    ],
)
def test_bad_answers_never_raise(
    fake: Fake, status: int, payload: bytes, expected: SandboxErrorCode
) -> None:
    fake.reply = (status, payload)
    result = run_pandas("x", b"a\n1\n")
    assert isinstance(result, SandboxError) and result.code is expected


def test_connection_refused_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sandbox_client, "get_settings", lambda: SimpleNamespace(sandbox_url="http://127.0.0.1:1")
    )
    result = run_pandas("x", b"a\n1\n")
    assert isinstance(result, SandboxError) and result.code is SandboxErrorCode.UNAVAILABLE


def test_unknown_host_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sandbox_client,
        "get_settings",
        lambda: SimpleNamespace(sandbox_url="http://no-such-host.invalid"),
    )
    assert isinstance(run_pandas("x", b"a\n1\n"), SandboxError)


def test_slow_service_times_out(fake: Fake) -> None:
    fake.delay = 2
    fake.reply = answer(200, {"ok": True, "result": 1, "duration_ms": 1})
    started = time.monotonic()
    result = run_pandas("x", b"a\n1\n", timeout=0.5)
    assert isinstance(result, SandboxError) and result.code is SandboxErrorCode.UNAVAILABLE
    assert time.monotonic() - started < 1.5


def test_the_default_timeout_is_15_seconds() -> None:
    assert sandbox_client.TOTAL_TIMEOUT_SECONDS == 15.0


def test_wrong_argument_types_are_bad_input_not_an_exception() -> None:
    for code, data in ((None, b"x"), ("x", None), (123, b"x")):
        result = run_pandas(code, data)  # type: ignore[arg-type]
        assert isinstance(result, SandboxError) and result.code is SandboxErrorCode.BAD_INPUT


def test_broken_settings_do_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise RuntimeError("settings exploded")

    monkeypatch.setattr(sandbox_client, "get_settings", boom)
    result = run_pandas("x", b"a\n1\n")
    assert isinstance(result, SandboxError) and result.code is SandboxErrorCode.UNAVAILABLE


@pytest.mark.parametrize("scenario", ["ok", "error", "down", "garbage"])
def test_nothing_about_the_code_or_the_data_is_logged(
    fake: Fake,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    fake.reply = {
        "ok": answer(200, {"ok": True, "result": "r", "duration_ms": 1}),
        "error": answer(200, {"ok": False, "error": "forbidden", "duration_ms": 1}),
        "down": (200, b""),
        "garbage": (200, SECRET_CODE.encode() + SECRET_CSV),
    }[scenario]
    if scenario == "down":
        monkeypatch.setattr(
            sandbox_client,
            "get_settings",
            lambda: SimpleNamespace(sandbox_url="http://127.0.0.1:1"),
        )
    with caplog.at_level(logging.DEBUG):
        run_pandas(SECRET_CODE, SECRET_CSV)
    logged = "\n".join(f"{r.getMessage()} {r.exc_text or ''} {r.args}" for r in caplog.records)
    assert "CODE-CANARY" not in logged and "CSV-CANARY" not in logged
    assert "result =" not in logged
    sandbox_lines = [r for r in caplog.records if r.name == "indesk.sandbox"]
    assert len(sandbox_lines) == 1  # one line: job id, outcome, duration


# ---- parse_pdf (P14a) ----

PDF_BYTES = b"%PDF-1.4 PDF-CANARY-4e8b"


def test_parse_pdf_ok_answer(fake: Fake) -> None:
    fake.reply = answer(
        200, {"ok": True, "result": {"page_count": 2, "pages": ["one", "two"]}, "duration_ms": 9}
    )
    result = sandbox_client.parse_pdf(PDF_BYTES, max_pages=30, max_chars=1000)
    assert isinstance(result, sandbox_client.PdfParseOk)
    assert result.parsed.pages == ["one", "two"] and result.parsed.page_count == 2
    sent = fake.seen[0]
    assert set(sent) == {"job_id", "pdf_b64", "max_pages", "max_chars"}
    assert (sent["max_pages"], sent["max_chars"]) == (30, 1000)


@pytest.mark.parametrize(
    "code",
    [
        SandboxErrorCode.ENCRYPTED,
        SandboxErrorCode.TOO_MANY_PAGES,
        SandboxErrorCode.TOO_MUCH_TEXT,
        SandboxErrorCode.UNREADABLE,
        SandboxErrorCode.TIMEOUT,
        SandboxErrorCode.MEMORY,
    ],
)
def test_parse_pdf_codes_come_back_typed(fake: Fake, code: SandboxErrorCode) -> None:
    fake.reply = answer(200, {"ok": False, "error": code.value, "duration_ms": 3})
    result = sandbox_client.parse_pdf(PDF_BYTES, max_pages=30, max_chars=1000)
    assert isinstance(result, SandboxError) and result.code is code


@pytest.mark.parametrize(
    "reply",
    [
        (503, b'{"ok": false, "error": "unavailable"}'),  # the parse slot is taken
        (500, b"boom"),
        (200, b"not json"),
        (
            200,
            b'{"ok": true, "result": {"page_count": 2, "pages": ["only one"]}}',
        ),  # count mismatch
        (200, b'{"ok": true, "result": {"page_count": 0, "pages": []}}'),
        (200, b'{"ok": true, "result": {"pages": ["x"]}}'),
        (200, b'{"ok": true, "result": [1, 2]}'),
        (200, b'{"ok": true, "result": {"page_count": 1, "pages": [5]}}'),
    ],
)
def test_parse_pdf_bad_answers_are_unavailable_and_never_raise(
    fake: Fake, reply: tuple[int, bytes]
) -> None:
    fake.reply = reply
    result = sandbox_client.parse_pdf(PDF_BYTES, max_pages=30, max_chars=1000)
    assert isinstance(result, SandboxError) and result.code is SandboxErrorCode.UNAVAILABLE


def test_parse_pdf_connection_refused_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sandbox_client, "get_settings", lambda: SimpleNamespace(parser_url="http://127.0.0.1:1")
    )
    result = sandbox_client.parse_pdf(PDF_BYTES, max_pages=30, max_chars=1000)
    assert isinstance(result, SandboxError) and result.code is SandboxErrorCode.UNAVAILABLE


def test_parse_pdf_logs_neither_the_pdf_nor_its_text(
    fake: Fake, caplog: pytest.LogCaptureFixture
) -> None:
    fake.reply = answer(
        200,
        {"ok": True, "result": {"page_count": 1, "pages": ["TEXT-CANARY-2d7a"]}, "duration_ms": 1},
    )
    with caplog.at_level(logging.DEBUG):
        result = sandbox_client.parse_pdf(PDF_BYTES, max_pages=30, max_chars=1000)
    assert isinstance(result, sandbox_client.PdfParseOk)
    assert "CANARY" not in caplog.text and "CANARY" not in repr(result)
