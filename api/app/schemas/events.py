"""Server-sent events of a run (GET /api/runs/{id}/events). Text is a message key plus args;
the browser translates it. Free model text never travels in an event."""

from typing import Annotated, Literal

from pydantic import Field

from app.core.enums import (
    AgentKey,
    Bubble,
    EvidenceType,
    RunOutcome,
    RunReason,
    StepKind,
    StepState,
)
from app.schemas.common import ApiModel, Id
from app.schemas.runs import MessageArgs, MessageKey


class StepEvent(ApiModel):
    event: Literal["step"] = "step"
    run_id: Id
    seq: int  # becomes the SSE event id, so a client can resume with Last-Event-ID
    agent: AgentKey
    kind: StepKind
    state: StepState
    key: MessageKey
    args: MessageArgs
    tok: int
    bubble: Bubble | None = None


class EvidenceEvent(ApiModel):
    """Evidence is ready. The payload itself is read from the report, not streamed."""

    event: Literal["evidence"] = "evidence"
    run_id: Id
    step_seq: int
    ref: str
    type: EvidenceType
    file_name: str
    location: str | None = None


class DoneEvent(ApiModel):
    event: Literal["done"] = "done"
    run_id: Id
    outcome: RunOutcome
    report_id: Id | None = None
    reason: RunReason | None = None  # additive: why a failed or rejected run ended


RunEvent = Annotated[StepEvent | EvidenceEvent | DoneEvent, Field(discriminator="event")]
