import uuid
from typing import Annotated, Self

from pydantic import (
    AliasChoices,
    AwareDatetime,
    Field,
    StringConstraints,
    model_validator,
)

from app.core.enums import (
    AgentKey,
    Bubble,
    FileRole,
    Lang,
    QuestionType,
    RunMode,
    RunOutcome,
    RunReason,
    RunStatus,
    StepKind,
    StepState,
)
from app.schemas.common import ApiModel, Id
from app.schemas.not_answerable import NotAnswerable

# A trace line is a message key (translated in the browser) plus plain values, never model text.
MessageKey = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")]
ShortText = Annotated[str, StringConstraints(max_length=120)]
MessageArgs = dict[MessageKey, ShortText | int | float | bool | None]


class AgentStep(ApiModel):
    """One trace event of a run. `seq` is monotonic per run (the SSE event id)."""

    id: Id
    run_id: Id
    seq: int
    agent: AgentKey
    kind: StepKind
    state: StepState
    key: MessageKey
    args: MessageArgs
    tok: int
    bubble: Bubble | None
    attempt: int
    started_at: AwareDatetime | None
    finished_at: AwareDatetime | None


class Run(ApiModel):
    id: Id
    user_id: Id
    question: str
    mode: RunMode
    question_type: QuestionType | None
    status: RunStatus
    outcome: RunOutcome | None
    outcome_reason: str | None
    counted: bool
    lang: Lang
    tokens_in: int
    tokens_out: int
    tool_calls: int
    cost_usd: float
    started_at: AwareDatetime | None
    finished_at: AwareDatetime | None
    error: str | None
    # Additive (not in the mock records).
    created_at: AwareDatetime | None = None
    steps: list[AgentStep] = Field(default_factory=list)
    report_id: Id | None = None


class RunFileIn(ApiModel):
    upload_id: uuid.UUID
    role: FileRole


# Files per mode: Check 1 document + up to 4 sources; Compare 1 + 1. Ask takes ONE CSV in v1, but
# the schema lets up to _MAX_ASK_FILES + 1 files (even a repeated one) through so that the service
# answers TOO_MANY_FILES instead of a generic validation error.
_MAX_ASK_FILES = 5
_MAX_CHECK_SOURCES = 4


class RunCreate(ApiModel):
    """POST /api/runs. Only the mode, the question and the files come from the client; user, lang,
    price, plan and limits are decided on the server."""

    mode: RunMode
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
    ]
    files: Annotated[list[RunFileIn], Field(min_length=1, max_length=_MAX_ASK_FILES + 1)]

    @model_validator(mode="after")
    def _roles_match_mode(self) -> Self:
        roles = [f.role for f in self.files]
        count = roles.count
        if self.mode is RunMode.ASK:
            ok = count(FileRole.SUBJECT) == len(roles)
        elif self.mode is RunMode.CHECK:
            ok = count(FileRole.SUBJECT) == 1 and count(FileRole.SOURCE) == len(roles) - 1
            ok = ok and count(FileRole.SOURCE) <= _MAX_CHECK_SOURCES
        else:
            ok = len(roles) == 2 and count(FileRole.A) == 1 and count(FileRole.B) == 1
        if self.mode is not RunMode.ASK and len({f.upload_id for f in self.files}) != len(roles):
            ok = False  # an upload can be used once (Ask: the service refuses with TOO_MANY_FILES)
        if not ok:
            raise ValueError("file roles do not fit the mode")
        return self


class RunCreated(ApiModel):
    """The answer to POST /api/runs (202)."""

    id: Id
    status: RunStatus


class RunView(ApiModel):
    """GET /api/runs/{id}. Written for the owner's browser: no user id, no cost, no error text, no
    step payload, no model name. `reason` is a code the browser translates."""

    id: Id
    mode: RunMode
    question: str
    status: RunStatus
    outcome: RunOutcome | None
    reason: RunReason | None = Field(validation_alias=AliasChoices("reason", "outcome_reason"))
    lang: Lang
    tokens_in: int
    tokens_out: int
    tool_calls: int
    created_at: AwareDatetime | None
    started_at: AwareDatetime | None
    finished_at: AwareDatetime | None
    steps: list[AgentStep]
    report_id: Id | None
    # Additive: only for a not_answerable run (filled by the service from the closing payload).
    not_answerable: NotAnswerable | None = None
    # Additive: the server clock (UTC) when the view was built, so the browser can work out its
    # offset. Set by the service; never part of a list or a report.
    server_now: AwareDatetime | None = None
