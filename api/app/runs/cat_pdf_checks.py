"""Cat's checks for claims about a PDF, all in CODE (P14a part 2). No model decides whether a claim
is verified.

"Verified" here means: the quote the writer gave is on the page it cited (word for word, after the
match key of app.runs.quotes), it is long enough to mean something, and every number in the claim
is a number of the quote. It does NOT mean the claim's wording follows from the quote, or that the
document is right; the quote is shown next to the claim so a reader can judge.

Order of the checks: no_quote, bad_page, quote_too_short, quote_not_found / page_mismatch,
number_not_in_quote. The first that fails is the reason.

quote_too_short: every piece of a quote (between ellipses) must have 12 characters once spaces are
ignored. In English that is about two words. In Korean, Japanese and Chinese 12 characters is a long
phrase, so the floor is loose for them: a short Korean quote of 12 characters can still be a
fragment of a sentence. The floor is a guard against a quote that matches by accident, not a
measure of meaning."""

import re
from dataclasses import dataclass
from typing import Final

from app.core.enums import ClaimStatus, ReportReason
from app.runs.numbers import matches_any, number_tokens
from app.runs.quotes import MIN_QUOTE_CHARS, check_quote, match_key, quote_segments

_SPACES: Final = re.compile(r"\s+")


@dataclass(frozen=True)
class PdfVerdict:
    status: ClaimStatus
    reason: ReportReason | None
    quote_found: bool  # the quote is on the cited page, so it may be shown as evidence
    quote: str | None  # the quote as written, spaces tidied, when quote_found
    value: str | None  # the writer's figure, when it is in the quote


def _unverified(reason: ReportReason, *, found: bool = False, quote: str | None = None,
                value: str | None = None) -> PdfVerdict:  # fmt: skip
    return PdfVerdict(ClaimStatus.UNVERIFIED, reason, found, quote, value)


def quote_numbers(quote: str) -> list[float]:
    return [float(t.value) * t.scale for t in number_tokens(quote)]


def check_pdf_claim(
    text: str, quote: str, page: int, value: str, pages: dict[int, str], page_count: int
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
    if not all(matches_any(token, values) for token in number_tokens(text)):
        return _unverified(
            ReportReason.NUMBER_NOT_IN_QUOTE, found=True, quote=tidy_quote, value=shown
        )
    return PdfVerdict(ClaimStatus.VERIFIED, None, True, tidy_quote, shown)
