"""Numbers in text, and the rule for when a number written in a sentence matches a computed value.

`digits` and `same_numbers` are a port of web/scripts/check-report-numbers.mjs (the digit sequences
of two texts must be the same multiset). P9 does not translate yet; they are kept and tested so the
translation step (DECISIONS #98) can reuse them. The live check is `matches_any`.

A written number matches a computed value when it is that value rounded to the decimals the text
shows: "2,450,051", "2.45 million" and "245만" all match 2450051. The scale words are closed lists
and count only when they directly follow the number. Nothing here is a model call."""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final

# The .mjs pattern: 14.1, 2,410, 2019.
_DIGIT_RUN: Final = re.compile(r"\d+(?:[.,]\d+)*")
# A number as written: with thousands separators or without, optional decimals.
_TOKEN: Final = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)")
_SCALE: Final = re.compile(r"\s?(thousand|million|billion|trillion|천|만|억|조)", re.IGNORECASE)
_SCALES: Final[dict[str, int]] = {
    "thousand": 10**3, "million": 10**6, "billion": 10**9, "trillion": 10**12,
    "천": 10**3, "만": 10**4, "억": 10**8, "조": 10**12,
}  # fmt: skip
_PERCENT: Final = re.compile(r"\s?(%|percent\b|퍼센트)", re.IGNORECASE)


def digits(text: object) -> list[str]:
    """Every digit sequence of `text`, sorted (check-report-numbers.mjs `digits`)."""
    return sorted(_DIGIT_RUN.findall(str(text)))


def same_numbers(a: object, b: object) -> bool:
    return digits(a) == digits(b)


@dataclass(frozen=True)
class NumberToken:
    value: Decimal  # as written, commas removed
    places: int  # decimals written
    scale: int  # 1, or the scale word that follows
    percent: bool

    @property
    def plain(self) -> bool:
        return self.scale == 1 and not self.percent


def _decimal(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation:
        return None


def number_tokens(text: str) -> list[NumberToken]:
    found: list[NumberToken] = []
    for hit in _TOKEN.finditer(text):
        raw = hit.group(1)
        value = _decimal(raw)
        if value is None:
            continue
        places = len(raw.split(".")[1]) if "." in raw else 0
        tail = text[hit.end() :]
        scale_hit = _SCALE.match(tail)
        scale = _SCALES[scale_hit.group(1).lower()] if scale_hit else 1
        if scale_hit:
            tail = tail[scale_hit.end() :]
        found.append(NumberToken(value, places, scale, bool(_PERCENT.match(tail))))
    return found


def _within(candidate: float, token: NumberToken, *, ratio: bool = False) -> bool:
    """candidate rounded to the token's decimals (at its scale) equals the token."""
    written = float(token.value) * token.scale
    half = 0.5 * 10 ** (-token.places) * token.scale
    shown = candidate * 100 if ratio else candidate
    return bool(abs(shown - written) <= half + 1e-9 * max(1.0, abs(written)))


def matches_any(token: NumberToken, values: list[float]) -> bool:
    """Does the written number match one of the computed values (rounding as written)?
    A percent also matches a ratio (0.182 is "18.2%")."""
    for value in values:
        if _within(value, token):
            return True
        if token.percent and _within(value, token, ratio=True):
            return True
    return False


def normal(raw: Decimal) -> Decimal:
    """09 and 9 are the same number."""
    return raw.normalize()


def exact_tokens(text: str) -> set[Decimal]:
    """The plain numbers of a text (years, dates, ids), for 'this number was already given'."""
    return {normal(t.value) for t in number_tokens(text) if t.plain}
