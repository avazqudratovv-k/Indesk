"""Matching a quote against the stored text of a PDF (P14a part 2). Pure functions, no model.

The match key of a text: NFKC, soft hyphens and zero-width characters removed, a hyphen at a line
end rejoined to the next word when that word starts in lowercase ("inter-\\nnational"), then ALL
whitespace removed. Case is NOT folded, so "US" and "us" stay different. The stored page text stays
NFC; only the key is NFKC. A quote and a page are compared as keys."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Final

MIN_QUOTE_CHARS: Final = 12  # per segment, in key characters (whitespace does not count)
MAX_QUOTE_CHARS: Final = 300  # the quote as the writer wrote it
# Characters that are not text: soft hyphen, zero-width space/joiners, word joiner, BOM.
_INVISIBLE: Final = dict.fromkeys(map(ord, "­​‌‍⁠﻿"))
_LINE_HYPHEN: Final = re.compile(r"[-‐]\s*\n\s*(\S)")
_ELLIPSIS: Final = re.compile(r"\.{3,}|…")


def _rejoin(hit: re.Match[str]) -> str:
    following = hit.group(1)
    return following if following.islower() else hit.group(0)


def match_key(text: str) -> str:
    plain = unicodedata.normalize("NFKC", text).translate(_INVISIBLE)
    plain = _LINE_HYPHEN.sub(_rejoin, plain.replace("\r\n", "\n").replace("\r", "\n"))
    return "".join(plain.split())


def quote_segments(quote: str) -> list[str]:
    """The pieces of a quote between ellipses ("..." or "…"), as match keys, empty ones dropped."""
    return [key for key in (match_key(part) for part in _ELLIPSIS.split(quote)) if key]


def find_in_order(page_key: str, segments: list[str]) -> bool:
    """Every segment is on the page, each one after the end of the one before."""
    position = 0
    for segment in segments:
        found = page_key.find(segment, position)
        if found == -1:
            return False
        position = found + len(segment)
    return True


@dataclass(frozen=True)
class QuoteCheck:
    ok: bool
    other_page: int | None = None  # the quote was found on this other page (page_mismatch)


def check_quote(segments: list[str], pages: dict[int, str], page: int) -> QuoteCheck:
    """On the cited page, or else say which other page holds it."""
    keys = {number: match_key(text) for number, text in pages.items()}
    if page in keys and find_in_order(keys[page], segments):
        return QuoteCheck(True)
    for number in sorted(keys):
        if number != page and find_in_order(keys[number], segments):
            return QuoteCheck(False, number)
    return QuoteCheck(False)
