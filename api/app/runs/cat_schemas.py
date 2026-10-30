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

from app.core.enums import ClaimOrigin, ClaimStatus, Confidence, ReportReason, RunOutcome
from app.runs.numbers import QUANTITY_REASON
from app.schemas.not_answerable import NotAnswerable
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


class PdfClaimsOut(BaseModel):
    """The writer's answer about a PDF: FLAT parallel lists, one entry per claim. claim_quotes[i] is
    copied word for word from the passage on page claim_pages[i] (pages count from 1);
    claim_values[i] is the figure the quote gives, or "" when it has none.

    `found` is false when the passages do not answer the question: then there are NO claims (the
    lists are empty) and the run ends not_answerable. A slip in either direction (found false with
    claims, found true with none) is not rejected: it also ends not_answerable, claims unread."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    found: bool
    title: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    answer: Annotated[str, StringConstraints(min_length=1, max_length=600)]
    claim_texts: list[Annotated[str, StringConstraints(min_length=1, max_length=240)]] = Field(
        max_length=MAX_CLAIMS
    )
    claim_quotes: list[Annotated[str, StringConstraints(max_length=300)]] = Field(
        max_length=MAX_CLAIMS
    )
    claim_pages: list[int] = Field(max_length=MAX_CLAIMS)
    claim_values: list[Annotated[str, StringConstraints(max_length=60)]] = Field(
        max_length=MAX_CLAIMS
    )
    meaning: Annotated[str, StringConstraints(max_length=500)]
    next_steps: list[Annotated[str, StringConstraints(max_length=200)]] = Field(max_length=3)

    @model_validator(mode="after")
    def _paired(self) -> "PdfClaimsOut":
        sizes = {
            len(self.claim_texts), len(self.claim_quotes), len(self.claim_pages),
            len(self.claim_values),
        }  # fmt: skip
        if len(sizes) != 1:
            raise ValueError("one quote, page and value per claim")
        return self


class ClaimRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    n: int
    text: str
    status: ClaimStatus
    computed_value: str | None
    evidence_refs: list[str]
    # Document claims (P14a part 2); an Ask claim keeps the defaults.
    origin: ClaimOrigin = ClaimOrigin.ANSWER
    doc_quote: str | None = None
    doc_location: str | None = None  # "p12"
    doc_value: str | None = None


class EvidenceRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    ref: str
    type: Literal["table", "critic_note", "passage"]
    location: str | None
    payload: EvidencePayload
    source: Literal["beaver", "cat", "hound"]  # whose trace line the evidence hangs on


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
    # The quantity-word check (numbers.unsupported_quantity_words): how many sentences were dropped
    # and how many claims were demoted. Counters only, never the text.
    quantity_dropped: int = 0
    quantity_demoted: int = 0


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
    # Quantity words with no support (a size said in words): sentences dropped, claims demoted, and
    # the closed reason code. Counters and a code, never the text.
    quantity_dropped: int = 0
    quantity_demoted: int = 0
    quantity_reason: str | None = None
    # Only when the run ends not_answerable: the closed reason code, facts from the file and the
    # suggested questions (app.runs.not_answerable). Never model text.
    not_answerable: NotAnswerable | None = None


def payload_with_quantity(payload: CatPayload, draft: ReportDraft | None) -> CatPayload:
    """`payload` with the quantity-word counters of the draft (and the reason code when either is
    above zero). The draft's own text never goes in."""
    if draft is None or not (draft.quantity_dropped or draft.quantity_demoted):
        return payload
    return payload.model_copy(
        update={
            "quantity_dropped": draft.quantity_dropped,
            "quantity_demoted": draft.quantity_demoted,
            "quantity_reason": QUANTITY_REASON,
        }
    )
