"""Shapes handed between the agents of the PDF flow (P14a part 2). Owl's step is code, Hound's
result carries the passages to the writer. None of this is sent to the browser; the payloads stored
on the trace lines hold counts, pages and scores, never passage text."""

import uuid

from pydantic import BaseModel, ConfigDict


class OwlPdfPlan(BaseModel):
    """Owl's routing for a PDF, decided in code from the upload type (no model call)."""

    model_config = ConfigDict(frozen=True)

    upload_id: uuid.UUID


class HoundPassage(BaseModel):
    model_config = ConfigDict(frozen=True)

    page: int
    text: str
    score: float  # the fused rank score, 0 to 1
    cosine: float | None = None  # the raw cosine similarity; None for a word-search-only passage


class HoundResult(BaseModel):
    """Handed to the flow (not stored, not sent): the passages for the writer."""

    model_config = ConfigDict(frozen=True)

    upload_id: uuid.UUID
    filename: str
    page_count: int
    mode: str  # "hybrid" or "keyword"
    passages: list[HoundPassage]


class HoundPayload(BaseModel):
    """Stored on Hound's closing line (agent_steps.payload): how the search went."""

    model_config = ConfigDict(frozen=True)

    mode: str
    matched: int
    pages: list[int]
    scores: list[float]
    cosines: list[float | None]  # raw cosine of each kept passage, apart from the fused scores
    top_cosine: float | None  # the best cosine of any chunk, before the similarity floor
    embed_tokens: int
