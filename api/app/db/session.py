from functools import lru_cache

from sqlalchemy import Engine, create_engine, text


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
