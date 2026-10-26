"""One ai_calls row per model request. Metadata only: never a prompt, an answer or a cost."""

import uuid

from app.ai.caps import SessionFactory
from app.core.enums import AiCallStatus, AiPurpose
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
) -> None:
    """May raise; the gateway catches it. est_cost_usd is left at its default 0 (Decision #74)."""
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
            )
        )
