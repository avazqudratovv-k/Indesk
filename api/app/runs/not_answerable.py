"""Why a run ended not_answerable, built in code (no model call). The reason is a closed code; every
page, column, row count and year in the facts comes from the file or from Hound's stored search,
never from model memory, and the writer's answer, title and meaning are never read. The question
is used only to pick numbers out of it (a page, a year) that are then compared with the file.

Suggestions are fixed templates filled with real column names or a stored page. Nothing here
claims that a suggested question can be answered."""

import re
import uuid
from typing import Final

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AgentKey, NotAnswerableReason, SuggestionKind
from app.db.models import AgentStep
from app.runs.cat_checks import PLACEHOLDER, clean_label
from app.runs.pdf_schemas import HoundResult
from app.runs.profile import YEAR_NAMES, CsvProfile, TimeSpan
from app.schemas.not_answerable import (
    MAX_FACT_COLUMNS,
    MAX_FACT_PAGES,
    MAX_SUGGESTIONS,
    NotAnswerable,
    NotAnswerableFacts,
    Suggestion,
)

PAYLOAD_KEY: Final = "not_answerable"

# "page 7", "pages 7", "p. 7", "p.7", "7쪽", "7페이지". Only the first number after the word counts.
_PAGE: Final = re.compile(
    r"(?<![A-Za-z])(?:pages?|p\.)\s*(\d{1,4})(?!\d)|(?<!\d)(\d{1,4})\s*(?:쪽|페이지)", re.IGNORECASE
)
# A four-digit year, not part of a longer number ("2,450", "1999.5").
_YEAR: Final = re.compile(r"(?<![\d,.])((?:19|20)\d\d)(?!\d|,\d|\.\d)")


def asked_page_beyond(question: str, page_count: int) -> int | None:
    """The first page the question names that the document does not have, else None."""
    for hit in _PAGE.finditer(question):
        page = int(hit.group(1) or hit.group(2))
        if page > page_count:
            return page
    return None


def years_in(question: str) -> list[int]:
    return [int(hit.group(1)) for hit in _YEAR.finditer(question)]


def _label(name: str) -> str | None:
    shown = clean_label(name)
    return None if not shown or shown == PLACEHOLDER else shown


# ---- PDF ----


def for_pdf(
    question: str,
    lang: str,
    hound: HoundResult,
    *,
    pages_with_text: int | None,
    writer_found_nothing: bool,
) -> NotAnswerable:
    """`writer_found_nothing`: Hound had passages but the writer said they do not answer."""
    searched: list[int] = []
    for passage in hound.passages:  # best first
        if passage.page not in searched:
            searched.append(passage.page)
    asked = asked_page_beyond(question, hound.page_count) if hound.page_count > 0 else None
    if asked is not None:
        reason = NotAnswerableReason.PDF_PAGE_RANGE
    elif writer_found_nothing and hound.passages:
        reason = NotAnswerableReason.PDF_NOT_IN_PASSAGES
    else:
        reason = NotAnswerableReason.PDF_NO_MATCH
    facts = NotAnswerableFacts(
        page_count=hound.page_count or None,
        pages_with_text=pages_with_text,
        searched_pages=searched[:MAX_FACT_PAGES]
        if reason is NotAnswerableReason.PDF_NOT_IN_PASSAGES
        else [],
        asked_page=asked,
    )
    top = hound.passages[0].page if hound.passages else None
    ko = lang == "ko"
    suggestions = [
        Suggestion(
            text="이 문서는 무엇에 관한 내용인가요?" if ko else "What is this document about?",
            kind=SuggestionKind.PDF_ABOUT,
        )
    ]
    if top is not None:
        text = f"{top}쪽에는 어떤 수치가 있나요?" if ko else f"What figures does page {top} give?"
        suggestions.append(Suggestion(text=text, kind=SuggestionKind.PDF_PAGE))
    return NotAnswerable(reason=reason, facts=facts, suggestions=suggestions[:MAX_SUGGESTIONS])


# ---- CSV ----


def for_csv(
    question: str,
    lang: str,
    *,
    row_count: int | None,
    profile: CsvProfile | None,
    span: TimeSpan | None,
) -> NotAnswerable:
    columns: list[str] = []
    if profile is not None:
        columns = [s for s in (_label(c.name) for c in profile.columns) if s][:MAX_FACT_COLUMNS]
    asked = None
    if span is not None:
        asked = next(
            (y for y in years_in(question) if not span.year_min <= y <= span.year_max), None
        )
    time_label = _label(span.column) if span is not None else None
    if asked is not None and time_label is not None and span is not None:
        reason = NotAnswerableReason.CSV_PERIOD
        facts = NotAnswerableFacts(
            row_count=row_count, columns=columns, time_column=time_label,
            year_min=span.year_min, year_max=span.year_max, asked_year=asked,
        )  # fmt: skip
    else:
        reason = NotAnswerableReason.CSV_NO_ROWS
        facts = NotAnswerableFacts(row_count=row_count, columns=columns)
    return NotAnswerable(
        reason=reason, facts=facts, suggestions=_csv_suggestions(lang, profile, time_label)
    )


def _csv_suggestions(
    lang: str, profile: CsvProfile | None, time_label: str | None
) -> list[Suggestion]:
    if profile is None:
        return []
    numeric = next(
        (
            s
            for c in profile.columns
            if c.dtype in ("integer", "float")
            and c.name.strip().casefold() not in YEAR_NAMES  # a year is not a quantity
            and (s := _label(c.name))
            and s != time_label
        ),
        None,
    )
    text = next((s for c in profile.columns if c.dtype == "text" and (s := _label(c.name))), None)
    ko = lang == "ko"
    found: list[Suggestion] = []
    if numeric and time_label:
        found.append(
            Suggestion(
                text=f"{time_label}별 {numeric} 추이 보여 주세요"
                if ko
                else f"Show {numeric} by {time_label}",
                kind=SuggestionKind.CSV_TREND,
            )
        )
    if numeric and text:
        found.append(
            Suggestion(
                text=f"{text}별 {numeric} 순위 알려 주세요" if ko else f"Rank {text} by {numeric}",
                kind=SuggestionKind.CSV_RANK,
            )
        )
    return found[:MAX_SUGGESTIONS]


# ---- reading it back ----


def read_for_run(db: Session, run_id: uuid.UUID) -> NotAnswerable | None:
    """The object stored on the run's closing Cat line, or None (a payload that does not validate is
    treated as absent: the reader never sees raw stored JSON). The caller has already decided the
    run belongs to the caller and ended not_answerable."""
    payload = db.scalar(
        select(AgentStep.payload)
        .where(
            AgentStep.run_id == run_id,
            AgentStep.agent == AgentKey.CRITIC,
            AgentStep.payload.is_not(None),
        )
        .order_by(AgentStep.seq.desc())
        .limit(1)
    )
    stored = payload.get(PAYLOAD_KEY) if isinstance(payload, dict) else None
    if stored is None:
        return None
    try:
        return NotAnswerable.model_validate(stored)
    except ValidationError:
        return None
