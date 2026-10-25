import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("indesk.errors")

_CODES = {
    HTTPStatus.NOT_FOUND: "NOT_FOUND",
    HTTPStatus.METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
}


def error_response(status: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code}})


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101  # narrows the handler type for mypy
    code = _CODES.get(HTTPStatus(exc.status_code), "ERROR")
    return error_response(exc.status_code, code)


async def _validation_error(_: Request, __: Exception) -> JSONResponse:
    # Never echo the input back: it can hold file contents or a question.
    return error_response(422, "VALIDATION_ERROR")


async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    # Type name and route only: exception text can carry secrets or request data.
    logger.error("unhandled %s on %s %s", type(exc).__name__, request.method, request.url.path)
    return error_response(500, "INTERNAL")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled_error)
