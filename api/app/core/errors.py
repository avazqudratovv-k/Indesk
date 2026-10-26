import logging
from enum import StrEnum
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("indesk.errors")


class ErrorCode(StrEnum):
    """Every code the API can return. The browser translates the code, never a raw message."""

    # Framework-level.
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    NOT_READY = "NOT_READY"
    INTERNAL = "INTERNAL"
    # Auth.
    EMAIL_TAKEN = "EMAIL_TAKEN"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    RATE_LIMITED = "RATE_LIMITED"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    ORIGIN_NOT_ALLOWED = "ORIGIN_NOT_ALLOWED"
    # Uploads.
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    TOO_MANY_ROWS = "TOO_MANY_ROWS"
    TOO_MANY_COLUMNS = "TOO_MANY_COLUMNS"
    EMPTY_FILE = "EMPTY_FILE"
    BAD_CSV = "BAD_CSV"
    # Runs.
    MODE_NOT_AVAILABLE = "MODE_NOT_AVAILABLE"
    DAILY_CAP_USER = "DAILY_CAP_USER"
    DAILY_CAP_GLOBAL = "DAILY_CAP_GLOBAL"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    NOT_RETRYABLE = "NOT_RETRYABLE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    RUN_ACTIVE = "RUN_ACTIVE"  # one active run per user
    UPLOAD_NOT_READY = "UPLOAD_NOT_READY"
    TOO_MANY_STREAMS = "TOO_MANY_STREAMS"
    UPLOAD_IN_USE = "UPLOAD_IN_USE"  # an active run still uses the file


_CODES = {
    HTTPStatus.NOT_FOUND: ErrorCode.NOT_FOUND,
    HTTPStatus.METHOD_NOT_ALLOWED: ErrorCode.METHOD_NOT_ALLOWED,
}


class AppError(Exception):
    """Raised anywhere in a request to answer with {"error": {"code": ...}}. Carries no message."""

    def __init__(
        self,
        status: int,
        code: ErrorCode,
        headers: dict[str, str] | None = None,
        *,
        extra: dict[str, str] | None = None,
    ) -> None:
        super().__init__(code.value)
        self.status = status
        self.code = code
        self.headers = headers
        self.extra = extra  # additive fields of the error body, such as run_id on RUN_ACTIVE


def error_response(
    status: int,
    code: ErrorCode | str,
    headers: dict[str, str] | None = None,
    extra: dict[str, str] | None = None,
) -> JSONResponse:
    content = {"error": {"code": str(code), **(extra or {})}}
    return JSONResponse(status_code=status, content=content, headers=headers)


async def _app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101  # narrows the handler type for mypy
    return error_response(exc.status, exc.code, exc.headers, exc.extra)


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101  # narrows the handler type for mypy
    code = _CODES.get(HTTPStatus(exc.status_code), "ERROR")
    return error_response(exc.status_code, code)


async def _validation_error(_: Request, __: Exception) -> JSONResponse:
    # Never echo the input back: it can hold file contents or a question.
    return error_response(422, ErrorCode.VALIDATION_ERROR)


async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    # Type name and route only: exception text can carry secrets or request data.
    logger.error("unhandled %s on %s %s", type(exc).__name__, request.method, request.url.path)
    return error_response(500, ErrorCode.INTERNAL)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled_error)
