"""Run model-written pandas code in the sandbox service. `run_pandas` never raises: it returns
SandboxOk, or SandboxError with one fixed code (SandboxErrorCode.UNAVAILABLE when the service
cannot be reached or answers nonsense). It never logs the code or the CSV: only a job id, the
duration and the outcome code."""

import base64
import json
import logging
import time
import urllib.error
import urllib.request
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from app.core.config import get_settings
from app.core.enums import SandboxErrorCode

logger = logging.getLogger("indesk.sandbox")

TOTAL_TIMEOUT_SECONDS = 15.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # the sandbox caps a result at 1 MiB


class SandboxOk(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: Literal[True] = True
    result: JsonValue
    duration_ms: int


class SandboxError(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: Literal[False] = False
    code: SandboxErrorCode
    duration_ms: int


SandboxResult = SandboxOk | SandboxError


def _fail(code: SandboxErrorCode, started: float) -> SandboxError:
    return SandboxError(code=code, duration_ms=int((time.monotonic() - started) * 1000))


def _code_from(body: bytes) -> SandboxErrorCode:
    """The fixed code in an error answer; anything unknown means the service is not behaving."""
    try:
        return SandboxErrorCode(json.loads(body)["error"])
    except (ValueError, KeyError, TypeError):
        return SandboxErrorCode.UNAVAILABLE


def _post(url: str, payload: bytes, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(  # noqa: S310  # the URL comes from settings, not from a user
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        with error:
            return error.code, error.read(MAX_RESPONSE_BYTES + 1)


def _interpret(status: int, body: bytes, started: float) -> SandboxResult:
    if len(body) > MAX_RESPONSE_BYTES:
        return _fail(SandboxErrorCode.UNAVAILABLE, started)
    if status in (400, 413):
        return _fail(SandboxErrorCode.BAD_INPUT, started)
    if status != 200:
        return _fail(SandboxErrorCode.UNAVAILABLE, started)
    data = json.loads(body)
    duration = int((time.monotonic() - started) * 1000)
    if data["ok"] is True:
        return SandboxOk(result=data["result"], duration_ms=duration)
    return SandboxError(code=_code_from(body), duration_ms=duration)


def run_pandas(
    code: str, csv_bytes: bytes, *, timeout: float = TOTAL_TIMEOUT_SECONDS
) -> SandboxResult:
    started = time.monotonic()
    job_id = str(uuid.uuid4())
    result: SandboxResult
    try:
        if not isinstance(code, str) or not isinstance(csv_bytes, bytes):
            raise TypeError
        payload = json.dumps(
            {
                "job_id": job_id,
                "code": code,
                "csv_b64": base64.b64encode(csv_bytes).decode("ascii"),
            }
        ).encode()
    except (TypeError, AttributeError, ValueError):  # code or csv_bytes of the wrong type
        result = _fail(SandboxErrorCode.BAD_INPUT, started)
    else:
        try:
            url = get_settings().sandbox_url.rstrip("/") + "/run"
            status, body = _post(url, payload, timeout)
            result = _interpret(status, body, started)
        except Exception:  # noqa: BLE001  # never raise: timeouts, refused connections, bad JSON
            result = _fail(SandboxErrorCode.UNAVAILABLE, started)
    outcome = "ok" if isinstance(result, SandboxOk) else result.code.value
    logger.info("sandbox job %s %s %dms", job_id, outcome, result.duration_ms)
    return result


class PdfParsed(BaseModel):
    """What the sandbox returns for a parsed PDF: the text of each page in order (0 = page 1)."""

    model_config = ConfigDict(frozen=True)

    page_count: int = Field(ge=1)
    pages: list[str] = Field(repr=False)  # the document text: kept out of repr, like a prompt


class PdfParseOk(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: Literal[True] = True
    parsed: PdfParsed
    duration_ms: int


PdfParseResult = PdfParseOk | SandboxError


def parse_pdf(
    pdf_bytes: bytes,
    *,
    max_pages: int,
    max_chars: int,
    timeout: float = TOTAL_TIMEOUT_SECONDS,
) -> PdfParseResult:
    """Parse a PDF in the parser service (its own container, see compose.yaml). Never raises. A busy
    parse slot, a stopped parser and an answer that does not fit the shape all give
    SandboxErrorCode.UNAVAILABLE. Never logs the PDF or its text."""
    started = time.monotonic()
    job_id = str(uuid.uuid4())
    result: PdfParseResult
    try:
        payload = json.dumps(
            {
                "job_id": job_id,
                "pdf_b64": base64.b64encode(pdf_bytes).decode("ascii"),
                "max_pages": max_pages,
                "max_chars": max_chars,
            }
        ).encode()
        url = get_settings().parser_url.rstrip("/") + "/parse-pdf"
        status, body = _post(url, payload, timeout)
        answer = _interpret(status, body, started)
        if isinstance(answer, SandboxError):
            result = answer
        else:
            parsed = PdfParsed.model_validate(answer.result)
            if len(parsed.pages) != parsed.page_count:
                raise ValueError("page count does not match")
            result = PdfParseOk(parsed=parsed, duration_ms=answer.duration_ms)
    except (ValidationError, ValueError, TypeError):
        result = _fail(SandboxErrorCode.UNAVAILABLE, started)
    except Exception:  # noqa: BLE001  # never raise: timeouts, refused connections, bad JSON
        result = _fail(SandboxErrorCode.UNAVAILABLE, started)
    outcome = "ok" if isinstance(result, PdfParseOk) else result.code.value
    logger.info("sandbox parse %s %s %dms", job_id, outcome, result.duration_ms)
    return result
