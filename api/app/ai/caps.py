"""Daily model-call caps on usage_daily: check and increment in ONE atomic SQL statement per scope.

Why SQL and not Redis: the table and its unique (day, scope) key already exist for this, so there is
one store of truth and nothing to drift. The cost is a hot 'global' row; the transaction is short.

Order is user row, then global row, in one transaction. If either is at its cap the whole
transaction rolls back, so a refused reserve counts nothing. Any database error fails closed."""

import logging
import uuid
from collections.abc import Callable
from datetime import date

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.enums import CapDecision
from app.db.models import UsageDaily

logger = logging.getLogger("indesk.ai")

SessionFactory = Callable[[], Session]


class _Refused(Exception):  # noqa: N818  # control flow inside reserve_call only
    def __init__(self, decision: CapDecision) -> None:
        super().__init__(decision.value)
        self.decision = decision


def _bump(db: Session, *, day: date, scope: str, user_id: uuid.UUID | None, cap: int) -> bool:
    """Add one call to (day, scope) unless it is already at `cap`. True if it was added."""
    statement = (
        insert(UsageDaily)
        .values(day=day, scope=scope, user_id=user_id, model_calls=1)
        .on_conflict_do_update(
            index_elements=[UsageDaily.day, UsageDaily.scope],
            set_={"model_calls": UsageDaily.model_calls + 1},
            where=UsageDaily.model_calls < cap,
        )
        .returning(UsageDaily.model_calls)
    )
    return db.execute(statement).first() is not None


def reserve_call(
    session_factory: SessionFactory,
    *,
    user_id: uuid.UUID,
    day: date,
    per_user: int,
    per_day: int,
) -> CapDecision:
    try:
        with session_factory() as db, db.begin():
            if not _bump(db, day=day, scope=f"user:{user_id}", user_id=user_id, cap=per_user):
                raise _Refused(CapDecision.USER_CAP)
            if not _bump(db, day=day, scope="global", user_id=None, cap=per_day):
                raise _Refused(CapDecision.GLOBAL_CAP)  # rolls the user increment back too
    except _Refused as refused:
        return refused.decision
    except Exception:  # noqa: BLE001  # fail closed on any store error; never raise, never log it
        logger.error("ai cap store failed code=%s", "AI_CAP_STORE_DOWN")
        return CapDecision.UNAVAILABLE
    return CapDecision.RESERVED
