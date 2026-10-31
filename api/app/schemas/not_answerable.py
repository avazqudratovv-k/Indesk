"""What a not_answerable run tells its owner: a closed reason, facts computed in code from the
file or the stored search, and up to two suggested questions. Never model text, passage text, a
prompt or a score. Stored on Cat's closing payload and sent on RunView and the SSE done event."""

from typing import Any, Final

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
)

from app.core.enums import NotAnswerableReason, SuggestionKind

MAX_FACT_PAGES: Final = 8
MAX_FACT_COLUMNS: Final = 8
MAX_SUGGESTIONS: Final = 2
MAX_ASKED_COLUMN_CHARS: Final = 80


class NotAnswerableFacts(BaseModel):
    """Every field is optional: a fact that could not be computed with confidence is left out."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    page_count: int | None = None
    pages_with_text: int | None = None
    searched_pages: list[int] = Field(default_factory=list, max_length=MAX_FACT_PAGES)
    asked_page: int | None = None
    row_count: int | None = None
    columns: list[str] = Field(default_factory=list, max_length=MAX_FACT_COLUMNS)
    time_column: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    asked_year: int | None = None
    # A column name taken from the user's own question, never from model text (runs.not_answerable).
    asked_column: str | None = Field(default=None, max_length=MAX_ASKED_COLUMN_CHARS)

    @model_serializer(mode="wrap")
    def _leave_out_empty(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        return {key: value for key, value in data.items() if value not in (None, [])}


class Suggestion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(max_length=200)
    kind: SuggestionKind


class NotAnswerable(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: NotAnswerableReason
    facts: NotAnswerableFacts
    suggestions: list[Suggestion] = Field(default_factory=list, max_length=MAX_SUGGESTIONS)
