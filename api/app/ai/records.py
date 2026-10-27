"""One ai_calls row per model request. Metadata only: never a prompt, an answer or a cost.
failure_kind is a closed code, never a response body, a URL or a key."""

import uuid
from decimal import Decimal

from app.ai.caps import SessionFactory
from app.core.enums import AiCallStatus, AiPurpose, FailureKind
from app.db.models import AiCall


def record_attempt(
    session_factory: SessionFactory,
    *,
    user_id: uuid.UUID,
    run_id: uuid.UUID | None,
    purpose: AiPurpose,
    model: str,
    attempt: int,
    status: AiCallStatus,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    failure_kind: FailureKind | None = None,
    est_cost_usd: Decimal = Decimal(0),
) -> None:
    """May raise; the gateway catches it. est_cost_usd stays 0 for text models (Decision #74: no
    price table); only embedding calls set it, from the price in limits.toml."""
    with session_factory() as db, db.begin():
        db.add(
            AiCall(
                user_id=user_id,
                run_id=run_id,
                purpose=purpose.value,
                model=model,
                attempt=attempt,
                status=status.value,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                est_cost_usd=est_cost_usd,
                failure_kind=failure_kind.value if failure_kind else None,
            )
        )
