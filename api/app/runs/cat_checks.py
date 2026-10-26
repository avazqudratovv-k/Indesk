"""Cat's checks, all in code (P9). No model decides whether a claim is verified.

What "verified" means: the numbers and the row label in the sentence match the cells it cites in
the COMPUTED TABLE that Beaver produced, and that calculation used every row of the file. It does
not mean the sentence's wording is true in some wider sense; the ranking-word rule below is the one
wording check, and it is relative to the computed table, not to the whole file.

Text that comes from a CSV cell (labels, column names, scalar names) is UNTRUSTED DATA. It is
cleaned before it reaches a prompt, a check or the stored evidence (`clean_label`), and the
writer's own sentences are scrubbed of markup and links (`scrub_text`)."""

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from app.core.enums import ClaimStatus, Confidence, ReportReason
from app.runs.ask_schemas import ComputedResult, Scalar
from app.runs.numbers import (
    NumberToken,
    exact_tokens,
    matches_any,
    normal,
    number_tokens,
)

PLACEHOLDER: Final = "(removed)"
MAX_LABEL_CHARS: Final = 40
MAX_LABEL_WORDS: Final = 6

# Markup and link characters are dropped from every untrusted string.
_TAG: Final = re.compile(r"<[^<>]*>")
_MARKUP: Final = re.compile(r"[<>`{}\[\]\\|]")
_SPACES: Final = re.compile(r"\s+")
_URLISH: Final = re.compile(r"\S*(?:://|www\.)\S*", re.IGNORECASE)
# A label that reads like an instruction to a model is replaced, not cleaned. A closed list.
_INSTRUCTION_WORDS: Final = (
    "ignore", "disregard", "instruction", "system prompt", "assistant", "previous", "override",
    "무시", "지시", "명령",
)  # fmt: skip
_PARENTHETICAL: Final = re.compile(r"\s*[(（][^()（）]*[)）]\s*$")


def _drop_controls(text: str) -> str:
    return "".join(c if c in " \t" or unicodedata.category(c)[0] != "C" else " " for c in text)


def _strip(text: str) -> str:
    """No control characters, tags, markup characters or links; spaces collapsed."""
    plain = _MARKUP.sub("", _TAG.sub("", _drop_controls(text)))
    return _SPACES.sub(" ", _URLISH.sub(" ", plain)).strip()


def _instruction_like(text: str) -> bool:
    low = unicodedata.normalize("NFKC", text).casefold()
    return any(word in low for word in _INSTRUCTION_WORDS) or len(low.split()) > MAX_LABEL_WORDS


def clean_label(text: str) -> str:
    """A string that came from the file, made safe to show and to put in a prompt: no markup, no
    links, no control characters, at most 40 characters, and a placeholder if it reads like an
    instruction. Station names such as 잠실(송파구청) pass unchanged."""
    if _instruction_like(text):
        return PLACEHOLDER
    cleaned = _strip(text)
    return cleaned[:MAX_LABEL_CHARS].strip()


_CAMEL: Final = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def humanize(name: str) -> str:
    """A column name as words: snake_case, kebab-case and camelCase are split at their joints and
    plain ASCII is lowercased (mean_daily_boardings -> mean daily boardings). Other scripts, such
    as 승차총승객수, pass unchanged. Nothing is translated."""
    spaced = _SPACES.sub(" ", _CAMEL.sub(" ", name.replace("_", " ").replace("-", " "))).strip()
    return spaced.lower() if spaced.isascii() else spaced


def scrub_text(text: str) -> str:
    """The writer's sentence without markup, links or control characters (never reworded)."""
    return _strip(text)


def norm(text: str) -> str:
    return _SPACES.sub(" ", unicodedata.normalize("NFKC", text)).strip().casefold()


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def format_cell(value: Scalar) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return value


@dataclass(frozen=True)
class ResultView:
    """Beaver's stored result with every string cleaned. The only form Cat ever uses."""

    columns: list[str]
    headers: list[str]  # the columns as words (humanize); what a reader sees
    rows: list[list[Scalar]]
    scalars: list[tuple[str, int | float]]
    rows_used: int
    row_count: int

    @classmethod
    def of(cls, result: ComputedResult, row_count: int) -> "ResultView":
        rows: list[list[Scalar]] = [
            [clean_label(c) if isinstance(c, str) else c for c in row] for row in result.rows
        ]
        columns = [clean_label(c) or PLACEHOLDER for c in result.columns]
        return cls(
            columns=columns,
            headers=[humanize(c) for c in columns],
            rows=rows,
            scalars=[(clean_label(k) or PLACEHOLDER, v) for k, v in result.scalars.items()],
            rows_used=result.rows_used,
            row_count=row_count,
        )

    @property
    def rows_ok(self) -> bool:
        """Owner rule: the calculation must have used every row of the file. An honest filtered
        answer (one line only) therefore comes out unverified."""
        return self.rows_used == self.row_count

    def prompt_table(self) -> dict[str, object]:
        """What the writer sees. Rows and columns count from 1; scalars are s1, s2..."""
        return {
            "columns": self.headers,
            "rows": self.rows,
            "scalars": [
                {"ref": f"s{i}", "name": n, "value": v} for i, (n, v) in enumerate(self.scalars, 1)
            ],
            "numbering": "rN is row N and cM is column M, both from 1: r2c3 is row 2, column 3",
        }

    def all_numbers(self) -> list[float]:
        found: list[float] = [float(self.rows_used), float(self.row_count), float(len(self.rows))]
        found += [float(c) for row in self.rows for c in row if is_number(c)]  # type: ignore[arg-type]
        found += [float(v) for _, v in self.scalars]
        return found

    def label_numbers(self) -> set[Decimal]:
        out: set[Decimal] = set()
        for row in self.rows:
            for cell in row:
                if isinstance(cell, str):
                    out |= exact_tokens(cell)
        return out


# ---- plain text: column names as words, numbers with thousands separators ----

# YYYYMMDD, or a year (1900-2100): never regrouped.
_DATE8: Final = re.compile(r"^(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])$")
# A run of 4+ digits with no separator. Not after a letter, digit, decimal point, comma, dash,
# underscore or #; not before a letter, digit, dash, slash or colon. Hangul after it is fine
# (2450051명). The optional decimals are kept as written.
_BARE_NUMBER: Final = re.compile(r"(?<![A-Za-z0-9_.,#\-])(\d{4,})(\.\d+)?(?![A-Za-z0-9\-/:])")


def _regroup(hit: re.Match[str], protected: set[Decimal]) -> str:
    digits_only, decimals = hit.group(1), hit.group(2) or ""
    if len(digits_only) == 4 and 1900 <= int(digits_only) <= 2100:
        return hit.group(0)
    if _DATE8.match(digits_only) or normal(Decimal(digits_only)) in protected:
        return hit.group(0)
    return f"{int(digits_only):,}{decimals}"


def group_thousands(text: str, protected: set[Decimal]) -> str:
    """2450051 -> 2,450,051. The value never changes, so a wrong number stays wrong. Dates, years,
    ids and any number already in the question or a label (`protected`) are left alone."""
    return _BARE_NUMBER.sub(lambda hit: _regroup(hit, protected), text)


def plain_columns(text: str, view: "ResultView") -> str:
    """A column name written in its raw form becomes its words (mean_daily_boardings -> mean daily
    boardings). Only a whole token is replaced, and not when the same text is part of a label of the
    table."""
    cells = [norm(c) for row in view.rows for c in row if isinstance(c, str)]
    for raw, words in zip(view.columns, view.headers, strict=True):
        if raw == words or raw == PLACEHOLDER or any(norm(raw) in cell for cell in cells):
            continue
        text = re.sub(rf"(?<!\w){re.escape(raw)}(?!\w)", words, text)
    return text


def tidy(text: str, view: "ResultView", protected: set[Decimal]) -> str:
    """The writer's text, scrubbed, with columns in words and numbers grouped."""
    return group_thousands(plain_columns(scrub_text(text), view), protected)


# ---- cells ----

_CELL: Final = re.compile(r"^r(\d{1,2})c(\d{1,2})$")
_SCALAR: Final = re.compile(r"^s(\d{1,2})$")


@dataclass(frozen=True)
class Cell:
    row: int | None  # 0-based; None for a scalar
    col: int | None
    value: Scalar


def resolve(ref: str, view: ResultView) -> Cell | None:
    hit = _CELL.match(ref)
    if hit:
        r, c = int(hit.group(1)) - 1, int(hit.group(2)) - 1
        if 0 <= r < len(view.rows) and 0 <= c < len(view.columns) and c < len(view.rows[r]):
            return Cell(r, c, view.rows[r][c])
        return None
    hit = _SCALAR.match(ref)
    if hit:
        i = int(hit.group(1)) - 1
        if 0 <= i < len(view.scalars):
            return Cell(None, None, view.scalars[i][1])
    return None


# ---- ranking words (closed lists) ----

# RELATIVE TO THE COMPUTED TABLE, NOT TO THE WHOLE FILE: a claim with one of these words is
# verified only if the number it cites is the largest (or smallest) in its column of the stored
# result, and the result has at least two rows. A result that was filtered to a few rows can
# therefore "confirm" a ranking that only holds inside those rows.
_RANK_MAX_EN: Final = re.compile(r"\b(most|highest|largest|top|fastest|busiest)\b", re.IGNORECASE)
_RANK_MIN_EN: Final = re.compile(r"\b(least|lowest|smallest)\b", re.IGNORECASE)
_RANK_MAX_KO: Final = ("가장", "최대", "최고")
_RANK_MIN_KO: Final = ("최소", "최저")
_KO_LESS: Final = ("적은", "낮은", "작은")  # 가장 적은 / 낮은 / 작은 = the least


def ranking_directions(text: str) -> set[str]:
    out: set[str] = set()
    if _RANK_MAX_EN.search(text):
        out.add("max")
    if _RANK_MIN_EN.search(text):
        out.add("min")
    if any(w in text for w in _RANK_MAX_KO):
        out.add("min" if "가장" in text and any(w in text for w in _KO_LESS) else "max")
    if any(w in text for w in _RANK_MIN_KO):
        out.add("min")
    return out


def _is_extreme(cell: Cell, direction: str, view: ResultView) -> bool:
    if cell.row is None or cell.col is None or not is_number(cell.value) or len(view.rows) < 2:
        return False
    column = [
        float(r[cell.col])  # type: ignore[arg-type]
        for r in view.rows
        if cell.col < len(r) and is_number(r[cell.col])
    ]
    target = max(column) if direction == "max" else min(column)
    return float(cell.value) == target  # type: ignore[arg-type]


# ---- one claim ----


@dataclass(frozen=True)
class Verdict:
    status: ClaimStatus
    reason: ReportReason | None
    computed_value: str | None


def _unverified(reason: ReportReason, value: str | None = None) -> Verdict:
    return Verdict(ClaimStatus.UNVERIFIED, reason, value)


def _label_variants(label: str) -> list[str]:
    full = norm(label)
    short = norm(_PARENTHETICAL.sub("", label))
    return [v for v in dict.fromkeys([full, short]) if v]


def _row_labels(row: list[Scalar]) -> list[str]:
    return [c for c in row if isinstance(c, str) and c and c != PLACEHOLDER]


def check_claim(
    text: str, refs: list[str], view: ResultView, question_numbers: set[Decimal]
) -> Verdict:
    if not view.rows_ok:
        return _unverified(ReportReason.ROWS_MISMATCH)
    cells = [resolve(ref, view) for ref in refs]
    if not refs or any(c is None for c in cells):
        return _unverified(ReportReason.BAD_REFERENCE)
    cited = [c for c in cells if c is not None]
    numeric = [c for c in cited if is_number(c.value)]
    if not numeric:
        return _unverified(ReportReason.NO_NUMERIC_EVIDENCE)
    shown = format_cell(numeric[0].value)

    flat = norm(text)
    row_ids = sorted({c.row for c in numeric if c.row is not None})
    exact = set(question_numbers)
    for r in row_ids:
        for label in _row_labels(view.rows[r]):
            exact |= exact_tokens(label)
        row_has_text = any(isinstance(c, str) and c for c in view.rows[r])
        if row_has_text and not any(
            v in flat for label in _row_labels(view.rows[r]) for v in _label_variants(label)
        ):
            return _unverified(ReportReason.LABEL_MISSING, shown)

    values = [float(c.value) for c in numeric]  # type: ignore[arg-type]
    for token in number_tokens(text):
        if not _token_ok(token, values, exact, len(view.rows)):
            return _unverified(ReportReason.NUMBER_MISMATCH, shown)

    directions = ranking_directions(text)
    if directions:
        if len(directions) > 1 or not all(
            _is_extreme(c, next(iter(directions)), view) for c in numeric
        ):
            return _unverified(ReportReason.RANKING_UNCHECKED, shown)
    return Verdict(ClaimStatus.VERIFIED, None, shown)


def _token_ok(token: NumberToken, values: list[float], exact: set[Decimal], rows: int) -> bool:
    if token.plain:
        value = normal(token.value)
        if value in exact:
            return True
        if token.places == 0 and 1 <= value <= rows:  # an ordinal: "the 2nd row"
            return True
    return matches_any(token, values)


# ---- prose ----


def prose_ok(text: str, view: ResultView, question_numbers: set[Decimal]) -> bool:
    """Every number in a title, answer or meaning is in the computed table (any cell), the question,
    a label of the file, or is an ordinal."""
    exact = question_numbers | view.label_numbers()
    values = view.all_numbers()
    return all(_token_ok(t, values, exact, len(view.rows)) for t in number_tokens(text))


def has_number(text: str) -> bool:
    return bool(number_tokens(text))


# ---- confidence ----


def confidence_of(verified: int, total: int) -> Confidence | None:
    """High: at least 0.8 verified and at most one not verified. Medium: at least 0.5. Else low.
    None when there is nothing to judge (Cat checked no claims)."""
    if total <= 0:
        return None
    share = verified / total
    if share >= 0.8 and total - verified <= 1:
        return Confidence.HIGH
    return Confidence.MEDIUM if share >= 0.5 else Confidence.LOW
