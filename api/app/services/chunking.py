"""Page text to chunks (P14). Pure functions: no database, no model.

A chunk is a slice of ONE page: it never crosses a page boundary, so its page number is exact, and
`page_text[start:end]` is the chunk text. Offsets count characters of the stored (cleaned, NFC) page
text. Chunks aim for `size` characters, break at a paragraph, line, sentence or word end when one
sits in the last 40% of the window, and share about `overlap` characters with the next chunk."""

import re
import unicodedata
from dataclasses import dataclass

_KEEP_CONTROLS = frozenset("\n\t")
_SENTENCE_END = re.compile(r"[.!?。！？][\"')\]」』”’]?\s")
MIN_FILL = 0.6  # a break is looked for from 60% of the window onward


@dataclass(frozen=True)
class Span:
    start: int
    end: int  # exclusive


@dataclass(frozen=True)
class PageChunk:
    page: int  # 1-based
    ord: int  # position in the whole document, from 0
    start: int
    end: int
    text: str


def clean_page_text(raw: str) -> str:
    """What is stored for a page: NFC, newlines as \\n, and no NUL, control or surrogate characters
    (Postgres text cannot hold NUL, and a lone surrogate cannot be written as UTF-8)."""
    text = unicodedata.normalize("NFC", raw).replace("\r\n", "\n").replace("\r", "\n")
    return "".join(
        ch for ch in text if ch in _KEEP_CONTROLS or unicodedata.category(ch) not in ("Cc", "Cs")
    )


def _break_point(text: str, start: int, hard: int, size: int) -> int:
    """Where a chunk that would run to `hard` should end instead: the latest paragraph, line,
    sentence or word end in the last 40% of the window. `hard` itself when there is none."""
    low = start + int(size * MIN_FILL)
    for separator in ("\n\n", "\n"):
        index = text.rfind(separator, low, hard)
        if index != -1:
            return index + len(separator)
    ends = [m.end() for m in _SENTENCE_END.finditer(text, low, hard)]
    if ends:
        return ends[-1]
    index = text.rfind(" ", low, hard)
    return index + 1 if index != -1 else hard


def _snap_forward(text: str, position: int, limit: int) -> int:
    """Move a chunk start that fell inside a word to the start of the next word, if one begins
    before `limit`. Text without spaces (Chinese, Japanese) keeps the exact position."""
    if position <= 0 or text[position - 1].isspace():
        return position
    for index in range(position, limit):
        if text[index].isspace():
            return index + 1
    return position


def split_page(text: str, size: int, overlap: int) -> list[Span]:
    """Spans of `text`, in order, each at most `size` characters, never empty, never starting or
    ending in whitespace. Every non-blank character is in at least one span."""
    if size < 1 or overlap < 0 or overlap * 5 > size * 2:
        raise ValueError("overlap must be at most 40% of the chunk size")
    spans: list[Span] = []
    length = len(text)
    start = 0
    while True:
        while start < length and text[start].isspace():
            start += 1
        if start >= length:
            return spans
        hard = min(start + size, length)
        end = hard if hard == length else _break_point(text, start, hard, size)
        stop = end
        while stop > start and text[stop - 1].isspace():
            stop -= 1
        spans.append(Span(start, stop))
        if end >= length:
            return spans
        start = max(_snap_forward(text, end - overlap, end), start + 1)


def chunk_document(pages: list[str], size: int, overlap: int) -> list[PageChunk]:
    """Chunks of every page, numbered across the document. A page with no text gives none."""
    chunks: list[PageChunk] = []
    for number, text in enumerate(pages, start=1):
        for span in split_page(text, size, overlap):
            chunks.append(
                PageChunk(number, len(chunks), span.start, span.end, text[span.start : span.end])
            )
    return chunks
