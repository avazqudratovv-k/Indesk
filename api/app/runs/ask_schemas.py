"""Shapes the Ask agents produce and store. The two model-facing ones (OwlPlan, BeaverCode) are
FLAT on purpose: no nested models, no enum classes, so the JSON schema has no $ref or $defs (the
Gemini response schema support for those is unverified). Model output that does not fit is
rejected, never repaired or rendered.

OwlPlan has NO free text: only closed words, numbers and column names that the code checks against
the real columns. So nothing a CSV cell could have steered into prose travels from Owl to Beaver."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

MAX_CODE_CHARS = 6000  # also the cap on the code stored in the payload (owner decision, P8a)
MAX_RESULT_ROWS = 50
MAX_RESULT_COLUMNS = 20

ColumnRef = Annotated[str, StringConstraints(min_length=1, max_length=120)]
ShortString = Annotated[str, StringConstraints(max_length=200)]
Scalar = ShortString | int | float | bool | None


class OwlPlan(BaseModel):
    """What to compute, in closed words. Which columns it names is checked in code."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task: Literal["rank", "aggregate", "trend", "compare_groups", "count", "describe"]
    columns: list[ColumnRef] = Field(max_length=8)
    group_by: list[ColumnRef] = Field(max_length=3)
    metric: ColumnRef | None
    aggregation: Literal["sum", "mean", "median", "min", "max", "count", "none"]
    time_column: ColumnRef | None
    order: Literal["asc", "desc"]
    top_n: int = Field(ge=1, le=50)
    # Columns added row by row to form the metric ("boardings plus alightings"). Empty when the
    # question asks for no combined total. Checked against the real columns in code.
    add_metrics: list[ColumnRef] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def _combined_metric(self) -> "OwlPlan":
        if self.add_metrics and (
            self.metric is not None
            or len(self.add_metrics) < 2
            or len(set(self.add_metrics)) != len(self.add_metrics)
        ):
            raise ValueError("add_metrics: 2 to 4 different columns, and no single metric")
        return self

    def named_columns(self) -> list[str]:
        named = [*self.columns, *self.group_by, *self.add_metrics]
        for single in (self.metric, self.time_column):
            if single is not None:
                named.append(single)
        return named


class BeaverCode(BaseModel):
    """The pandas code. UNTRUSTED: it runs only in the sandbox."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(min_length=1, max_length=MAX_CODE_CHARS)


class ComputedResult(BaseModel):
    """The `result` the sandbox returns, checked before it is stored. Numbers are computed by the
    code in the sandbox; strings are cut-down labels (they can come from CSV cells), capped, and
    must still be treated as untrusted data by whoever reads them (Cat, in P9)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    columns: list[Annotated[str, StringConstraints(min_length=1, max_length=60)]] = Field(
        min_length=1, max_length=MAX_RESULT_COLUMNS
    )
    rows: list[list[Scalar]] = Field(max_length=MAX_RESULT_ROWS)
    rows_used: int = Field(ge=0)
    scalars: dict[Annotated[str, StringConstraints(max_length=60)], int | float] = Field(
        default_factory=dict, max_length=MAX_RESULT_COLUMNS
    )

    @model_validator(mode="after")
    def _rectangular(self) -> "ComputedResult":
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("every row must have one cell per column")
        return self


class OwlPayload(BaseModel):
    """Stored on Owl's `dispatch` line (agent_steps.payload). Never sent to the browser."""

    model_config = ConfigDict(frozen=True)

    prompt_version: str
    attempt: int
    plan: OwlPlan


class BeaverPayload(BaseModel):
    """Stored on Beaver's final line (agent_steps.payload). Never sent to the browser. Holds only
    values the code computed, the plan's closed words, the code and version tags: no prompt text,
    no model prose, no raw sandbox error."""

    model_config = ConfigDict(frozen=True)

    owl_prompt_version: str
    beaver_prompt_version: str
    attempt: int
    method: str  # the plan's task word, e.g. "rank"
    row_count: int  # data rows in the CSV
    rows_used: int
    result: ComputedResult
    code: str = Field(max_length=MAX_CODE_CHARS)
