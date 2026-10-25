import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis import Redis

from app.core.config import Settings, get_settings
from app.core.errors import ErrorCode, error_response
from app.db.session import database_answers

logger = logging.getLogger("indesk.health")
router = APIRouter()


def redis_answers(url: str) -> bool:
    try:
        return bool(Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2).ping())
    except Exception:
        return False


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=None)
def ready(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str] | JSONResponse:
    failed = []
    if not database_answers(settings.database_url.get_secret_value()):
        failed.append("db")
    if not redis_answers(settings.redis_url.get_secret_value()):
        failed.append("redis")
    if failed:
        logger.warning("not ready: %s", ",".join(failed))
        return error_response(503, ErrorCode.NOT_READY)
    return {"status": "ready"}
