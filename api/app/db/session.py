from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings


@lru_cache
def get_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 2})


def database_answers(url: str) -> bool:
    try:
        with get_engine(url).connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


def get_db(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[Session]:
    """One session per request. Services commit; an unhandled error leaves it uncommitted."""
    with Session(get_engine(settings.database_url.get_secret_value())) as db:
        yield db
