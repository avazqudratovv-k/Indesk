"""Shapes for Cat (P9). `ClaimsOut` is what the writer model returns: FLAT (parallel lists, no
nested model, no pattern in the JSON schema) like OwlPlan and BeaverCode. The rest is built by code.

The writer's text is UNTRUSTED model output: Cat checks and scrubs it before anything is stored."""

import re
from typing import Annotated, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.enums import ClaimStatus, Confidence, ReportReason, RunOutcome
from app.schemas.reports import EvidencePayload, ReportSummary

MAX_CLAIMS: Final = 6
_REF: Final = r"(?:r\d{1,2}c\d{1,2}|s\d{1,2})"
CELL_LIST: Final = re.compile(rf"^{_REF}(?:,{_REF}){{0,5}}$")


class ClaimsOut(BaseModel):
    """claim_texts[i] cites the cells in claim_cells[i], for example "r1c1,r1c2" (rows and columns
    count from 1) or "s1" (the first scalar)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    answer: Annotated[str, StringConstraints(min_length=1, max_length=600)]
    claim_texts: list[Annotated[str, StringConstraints(min_length=1, max_length=240)]] = Field(
        min_length=1, max_length=MAX_CLAIMS
    )
    claim_cells: list[Annotated[str, StringConstraints(max_length=80)]] = Field(
        min_length=1, max_length=MAX_CLAIMS
    )
    meaning: Annotated[str, StringConstraints(max_length=500)]
    next_steps: list[Annotated[str, StringConstraints(max_length=200)]] = Field(max_length=3)

    @field_validator("claim_cells")
    @classmethod
    def _cell_lists(cls, value: list[str]) -> list[str]:
        # Not in the JSON schema (Gemini's support for `pattern` is unverified); checked here.
        if not all(CELL_LIST.match(item.replace(" ", "")) for item in value):
            raise ValueError("cell references must look like r1c2 or s1")
        return [item.replace(" ", "") for item in value]

    @model_validator(mode="after")
    def _paired(self) -> "ClaimsOut":
        if len(self.claim_texts) != len(self.claim_cells):
            raise ValueError("one cell list per claim")
        return self


class ClaimRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    n: int
    text: str
    status: ClaimStatus
    computed_value: str | None
    evidence_refs: list[str]


class EvidenceRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    ref: str
    type: Literal["table", "critic_note"]
    location: str | None
    payload: EvidencePayload
    source: Literal["beaver", "cat"]  # whose trace line the evidence hangs on


class ReportDraft(BaseModel):
    """Everything the store needs to write the report, the claims and the evidence."""

    model_config = ConfigDict(frozen=True)

    title: str
    summary: ReportSummary
    confidence: Confidence | None
    verified_count: int
    total_claims: int
    claims: list[ClaimRow]
    evidence: list[EvidenceRow]


class CatResult(BaseModel):
    """Handed to the flow (not stored, not sent)."""

    model_config = ConfigDict(frozen=True)

    outcome: RunOutcome
    report: ReportDraft | None


class VerdictRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    n: int
    status: ClaimStatus
    reason: ReportReason | None


class CatPayload(BaseModel):
    """Stored on Cat's final line (agent_steps.payload). Never sent to the browser. Statuses and
    codes only: no prompt, no model text."""

    model_config = ConfigDict(frozen=True)

    prompt_version: str
    rows_mismatch: bool
    verdicts: list[VerdictRecord]
