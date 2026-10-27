"""Cat turns the writer's claims about a PDF into a report draft: every claim checked in code
(cat_pdf_checks), a passage evidence row for each quote that was found, a critic note for each
reason a claim is not verified, the summary built from the checked claims. No model is called."""

import re
from decimal import Decimal
from typing import Final

from app.core.enums import ClaimOrigin, ClaimStatus, EvidenceType, ReportReason
from app.runs.cat_checks import confidence_of, has_number, scrub_text
from app.runs.cat_pdf_checks import PdfVerdict, check_pdf_claim, quote_numbers
from app.runs.cat_schemas import (
    ClaimRow,
    EvidenceRow,
    PdfClaimsOut,
    ReportDraft,
    VerdictRecord,
)
from app.runs.numbers import exact_tokens, matches_any, number_tokens
from app.schemas.reports import EvidencePayload, InShort, ReportSummary

_SPACES: Final = re.compile(r"\s+")


def _prose(text: str, allowed: list[float], question_numbers: set[Decimal]) -> str | None:
    """Title, answer or meaning: scrubbed, and every number in it is a number of a quote found in
    the document or of the question."""
    clean = scrub_text(text)
    if not clean:
        return None
    for token in number_tokens(clean):
        if token.plain and token.value.normalize() in question_numbers:
            continue
        if not matches_any(token, allowed):
            return None
    return clean


def build_pdf_report(
    out: PdfClaimsOut, pages: dict[int, str], page_count: int, question: str
) -> tuple[ReportDraft, list[VerdictRecord]] | None:
    """None when no claim survives scrubbing (the writer's output was not usable)."""
    kept: list[tuple[str, int, PdfVerdict]] = []
    for raw, quote, page, value in zip(
        out.claim_texts, out.claim_quotes, out.claim_pages, out.claim_values, strict=True
    ):
        text = scrub_text(raw)
        if not text:
            continue
        kept.append(
            (text, page, check_pdf_claim(text, quote, page, value, pages, page_count, question))
        )
    if not kept:
        return None

    reasons: list[ReportReason] = []
    for _, _, verdict in kept:
        if verdict.reason is not None and verdict.reason not in reasons:
            reasons.append(verdict.reason)
    note_ref = {reason: f"U{i}" for i, reason in enumerate(reasons, 1)}

    claims: list[ClaimRow] = []
    records: list[VerdictRecord] = []
    passages: list[EvidenceRow] = []
    for n, (text, page, verdict) in enumerate(kept, 1):
        refs: list[str] = []
        if verdict.quote_found and verdict.quote:
            ref = f"R{len(passages) + 1}"
            refs.append(ref)
            passages.append(
                EvidenceRow(ref=ref, type=EvidenceType.PASSAGE.value, source="hound",
                            location=f"page {page}", payload=EvidencePayload(quote=verdict.quote))
            )  # fmt: skip
        if verdict.reason is not None:
            refs.append(note_ref[verdict.reason])
        claims.append(
            ClaimRow(
                n=n, text=text, status=verdict.status, computed_value=None, evidence_refs=refs,
                origin=ClaimOrigin.DOCUMENT,
                doc_quote=verdict.quote if verdict.quote_found else None,
                doc_location=f"p{page}" if verdict.quote_found else None,
                doc_value=verdict.value,
            )
        )  # fmt: skip
        records.append(VerdictRecord(n=n, status=verdict.status, reason=verdict.reason))
    verified = sum(c.status is ClaimStatus.VERIFIED for c in claims)

    notes = [
        EvidenceRow(ref=note_ref[r], type=EvidenceType.CRITIC_NOTE.value, location=None,
                    payload=EvidencePayload(reason=r), source="cat")
        for r in reasons
    ]  # fmt: skip

    qnums = exact_tokens(question)
    allowed = [v for row in passages for v in quote_numbers(row.payload.quote or "")]
    first_verified = next((c.text for c in claims if c.status is ClaimStatus.VERIFIED), None)
    title = _prose(out.title, allowed, qnums) or scrub_text(question)[:100].strip() or "Report"
    answer = _prose(out.answer, allowed, qnums) or first_verified or claims[0].text
    meaning = _prose(out.meaning, allowed, qnums) if out.meaning.strip() else None
    steps = [s for s in (scrub_text(x) for x in out.next_steps) if s and not has_number(s)]
    summary = ReportSummary(
        answer=answer,
        in_short=[InShort(status=c.status, text=c.text) for c in claims],
        meaning=meaning,
        next_steps=steps,
    )  # fmt: skip
    draft = ReportDraft(
        title=title, summary=summary, confidence=confidence_of(verified, len(claims)),
        verified_count=verified, total_claims=len(claims), claims=claims,
        evidence=[*passages, *notes],
    )  # fmt: skip
    return draft, records
