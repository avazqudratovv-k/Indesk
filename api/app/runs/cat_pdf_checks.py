"""Cat's checks for claims about a PDF, all in CODE (P14a part 2). No model decides whether a claim
is verified.

"Verified" here means: the quote the writer gave is on the page it cited (word for word, after the
match key of app.runs.quotes), it is long enough to mean something, and every number in the claim
is a number of the quote (with two narrow allowances below). It does NOT mean the claim's
wording follows from the quote, or that the
document is right; the quote is shown next to the claim so a reader can judge.

Order of the checks: no_quote, bad_page, quote_too_short, quote_not_found / page_mismatch,
number_not_in_quote. The first that fails is the reason.

Allowances for a number of the claim that is not written in the quote: it is context the user gave
(the same whole number is in the question, and it is a year 1900 to 2100 or a number up to 31:
"2026년 9월"), or it is a whole number 0 to 12 that the quote spells as a word ("four", "네 개").
A number of 3 digits or more, a decimal, a percent or a number with a scale word must be in the
quote as written; a year or a day in the question is the only big number that may come from there.

quote_too_short: every piece of a quote (between ellipses) must have 12 characters once spaces are
ignored. In English that is about two words. In Korean, Japanese and Chinese 12 characters is a long
phrase, so the floor is loose for them: a short Korean quote of 12 characters can still be a
fragment of a sentence. The floor is a guard against a quote that matches by accident, not a
measure of meaning."""

import re
from dataclasses import dataclass
from typing import Final

from app.core.enums import ClaimStatus, ReportReason
from app.runs.numbers import (
    NumberToken,
    exact_tokens,
    matches_any,
    normal,
    number_tokens,
    unsupported_quantity_words,
)
from app.runs.quotes import MIN_QUOTE_CHARS, check_quote, match_key, quote_segments
from app.runs.spelled_numbers import MAX_SPELLED, spelled_in

_SPACES: Final = re.compile(r"\s+")


@dataclass(frozen=True)
class PdfVerdict:
    status: ClaimStatus
    reason: ReportReason | None
    quote_found: bool  # the quote is on the cited page, so it may be shown as evidence
    quote: str | None  # the quote as written, spaces tidied, when quote_found
    value: str | None  # the writer's figure, when it is in the quote
    quantity: bool = False  # demoted only because of a quantity word with no support


def _unverified(reason: ReportReason, *, found: bool = False, quote: str | None = None,
                value: str | None = None) -> PdfVerdict:  # fmt: skip
    return PdfVerdict(ClaimStatus.UNVERIFIED, reason, found, quote, value)


def quote_numbers(quote: str) -> list[float]:
    return [float(t.value) * t.scale for t in number_tokens(quote)]


def _whole(token: NumberToken) -> int | None:
    """The token as a whole number when it is a plain one (no decimals, scale word or percent)."""
    if not token.plain or token.places != 0:
        return None
    return int(normal(token.value))


def _from_context(token: NumberToken, question_numbers: set[int], quote: str) -> bool:
    number = _whole(token)
    if number is None:
        return False
    restated = number in question_numbers and (number <= 31 or 1900 <= number <= 2100)
    return restated or (number <= MAX_SPELLED and spelled_in(number, quote))


def check_pdf_claim(
    text: str,
    quote: str,
    page: int,
    value: str,
    pages: dict[int, str],
    page_count: int,
    question: str = "",
) -> PdfVerdict:
    tidy_quote = _SPACES.sub(" ", quote).strip()
    segments = quote_segments(tidy_quote)
    if not segments:
        return _unverified(ReportReason.NO_QUOTE)
    if page < 1 or page > page_count:
        return _unverified(ReportReason.BAD_PAGE)
    if any(len(segment) < MIN_QUOTE_CHARS for segment in segments):
        return _unverified(ReportReason.QUOTE_TOO_SHORT)
    found = check_quote(segments, pages, page)
    if not found.ok:
        reason = ReportReason.PAGE_MISMATCH if found.other_page else ReportReason.QUOTE_NOT_FOUND
        return _unverified(reason)
    shown = value.strip() if value.strip() and match_key(value) in "".join(segments) else None
    values = quote_numbers(tidy_quote)
    asked = {int(n) for n in exact_tokens(question) if n == n.to_integral_value()}
    if not all(
        matches_any(token, values) or _from_context(token, asked, tidy_quote)
        for token in number_tokens(text)
    ):
        return _unverified(
            ReportReason.NUMBER_NOT_IN_QUOTE, found=True, quote=tidy_quote, value=shown
        )
    if unsupported_quantity_words(text, tidy_quote, question):  # "a million": no digit to compare
        return PdfVerdict(
            ClaimStatus.UNVERIFIED, ReportReason.NUMBER_NOT_IN_QUOTE, True, tidy_quote, shown,
            quantity=True,
        )  # fmt: skip
    return PdfVerdict(ClaimStatus.VERIFIED, None, True, tidy_quote, shown)
