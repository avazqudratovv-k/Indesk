"""What the models may know about a CSV: column names, a type per column, the row count and a few
cut-down sample rows. Built in plain Python (stdlib csv) over the stored bytes, so the API needs no
pandas, the sandbox is not involved, and `scripts/show_prompts.py` shows exactly what a run sends.

The CSV is UNTRUSTED. Every string that leaves this module is cut to a fixed length and has its
control characters replaced, so a cell cannot carry a long instruction or a line break into a
prompt. The prompt builder then JSON-encodes and fences the result (app.runs.prompts).

Only comma-separated files are supported (the sandbox reads with pandas' default). A file that
csv_check's own detector reads as tab or semicolon is refused: `ProfileError.NOT_COMMA`."""

import csv
import io
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from app.core.config import Limits
from app.core.errors import AppError
from app.services.csv_check import decode_to_text, detect_delimiter

Dtype = Literal["integer", "float", "date", "text", "empty"]

_INT: Final = re.compile(r"^[+-]?\d{1,18}$")
_FLOAT: Final = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
_DATE: Final = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$")
_CONTROL: Final = re.compile(r"[\x00-\x1f\x7f-\x9f  ]")


class ProfileError(StrEnum):
    UNREADABLE = "unreadable"  # not text, not a CSV, no header, or no data rows
    NOT_COMMA = "not_comma"  # tab- or semicolon-separated (not supported yet)


class ColumnProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    dtype: Dtype


class CsvProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    row_count: int
    columns: list[ColumnProfile]
    sample_rows: list[
        list[str]
    ]  # the first profile_sample_rows rows, first profile_sample_columns columns

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


@dataclass(frozen=True)
class ProfileFailed:
    error: ProfileError


def clean(text: str, max_chars: int) -> str:
    """Control characters (line breaks included) become spaces; the text is cut at max_chars."""
    flat = _CONTROL.sub(" ", text).strip()
    return flat if len(flat) <= max_chars else flat[: max_chars - 1] + "…"


def _kind(cell: str) -> Dtype:
    if _INT.match(cell):
        return "integer"
    if _FLOAT.match(cell):
        return "float"
    if _DATE.match(cell):
        return "date"
    return "text"


def _dtype(kinds: set[Dtype]) -> Dtype:
    if not kinds:
        return "empty"
    if kinds == {"integer"}:
        return "integer"
    if kinds <= {"integer", "float"}:
        return "float"
    if kinds == {"date"}:
        return "date"
    return "text"


def _names(header: list[str]) -> list[str]:
    """Column names the way pandas will see them: blank -> 'Unnamed: i', repeats -> 'name.1'."""
    seen: dict[str, int] = {}
    names: list[str] = []
    for index, raw in enumerate(header):
        name = raw.strip() or f"Unnamed: {index}"
        count = seen.get(name, 0)
        seen[name] = count + 1
        names.append(name if count == 0 else f"{name}.{count}")
    return names


def build_profile(csv_bytes: bytes, limits: Limits) -> CsvProfile | ProfileFailed:
    """Never raises. The bytes are what upload storage holds: UTF-8 (csv_check re-encodes)."""
    try:
        text = decode_to_text(csv_bytes)
        if detect_delimiter(text) != ",":
            return ProfileFailed(ProfileError.NOT_COMMA)
        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        if not header:
            return ProfileFailed(ProfileError.UNREADABLE)
        names = _names(header)
        kinds: list[set[Dtype]] = [set() for _ in names]
        sample: list[list[str]] = []
        rows = 0
        for row in reader:
            if not any(cell.strip() for cell in row):
                continue  # pandas skips blank lines too
            rows += 1
            for index in range(min(len(row), len(names))):
                cell = row[index].strip()
                if cell:
                    kinds[index].add(_kind(cell))
            if len(sample) < limits.profile_sample_rows:
                width = min(limits.profile_sample_columns, len(names))  # never past the header
                shown = row[:width]
                sample.append([clean(cell, limits.profile_cell_chars) for cell in shown])
    except (AppError, csv.Error, UnicodeError, ValueError):
        return ProfileFailed(ProfileError.UNREADABLE)
    if rows == 0:
        return ProfileFailed(ProfileError.UNREADABLE)
    columns = [
        ColumnProfile(name=clean(name, limits.profile_name_chars), dtype=_dtype(found))
        for name, found in zip(names, kinds, strict=True)
    ]
    return CsvProfile(row_count=rows, columns=columns, sample_rows=sample)


YEAR_NAMES: Final = frozenset({"year", "yr", "연도", "년도", "기준연도", "연"})
_YEAR_FROM, _YEAR_TO = 1900, 2100


@dataclass(frozen=True)
class TimeSpan:
    column: str
    year_min: int
    year_max: int


def time_span(csv_bytes: bytes, profile: CsvProfile) -> TimeSpan | None:
    """The first and last year of the file's ONE time column, or None when there is no such column
    or it is not clear: a date column, or an integer column named like a year, with every value
    between 1900 and 2100. Two candidates, a stray value or an unreadable file give None (a fact
    that cannot be computed with confidence is left out). Stdlib only, over the whole file."""
    candidates = [
        index
        for index, column in enumerate(profile.columns)
        if column.dtype == "date"
        or (column.dtype == "integer" and column.name.strip().casefold() in YEAR_NAMES)
    ]
    if len(candidates) != 1:
        return None
    index = candidates[0]
    column = profile.columns[index]
    first: int | None = None
    last: int | None = None
    try:
        reader = csv.reader(io.StringIO(decode_to_text(csv_bytes)))
        next(reader, None)
        for row in reader:
            if index >= len(row) or not row[index].strip():
                continue
            cell = row[index].strip()
            year = int(cell[:4]) if column.dtype == "date" else int(cell)
            if not _YEAR_FROM <= year <= _YEAR_TO:
                return None
            first = year if first is None else min(first, year)
            last = year if last is None else max(last, year)
    except (AppError, csv.Error, UnicodeError, ValueError):
        return None
    if first is None or last is None:
        return None
    return TimeSpan(column.name, first, last)
