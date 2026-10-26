"""Cat turns the writer's claims into a report draft: every claim checked in code (cat_checks),
the prose checked for numbers, the evidence rows and the summary built from computed values.
Nothing here calls a model."""

from app.core.enums import (
    ClaimStatus,
    EvidenceMethod,
    EvidenceType,
    ReportReason,
)
from app.runs.ask_schemas import BeaverPayload
from app.runs.cat_checks import (
    ResultView,
    Verdict,
    check_claim,
    confidence_of,
    format_cell,
    has_number,
    is_number,
    prose_ok,
    resolve,
    scrub_text,
    tidy,
)
from app.runs.cat_schemas import (
    ClaimRow,
    ClaimsOut,
    EvidenceRow,
    ReportDraft,
    VerdictRecord,
)
from app.runs.numbers import exact_tokens
from app.schemas.reports import (
    EvidencePayload,
    EvidenceTable,
    InShort,
    ReportSummary,
    TopRow,
)

TABLE_TOOL = "run_python"
MAX_TOP_ROWS = 5


MAX_LABEL = 60
MAX_HEADER = 24
SEP = " · "


def _numeric_columns(view: ResultView) -> int:
    width = len(view.columns)
    return sum(any(c < len(r) and is_number(r[c]) for r in view.rows) for c in range(width))


def _row_label(refs: list[str], view: ResultView) -> str:
    """All text cells of the cited row (a line and a station: "1호선 서울역"), plus " · header" of
    the cited column when the table has two or more number columns (one row can then be cited for
    different columns)."""
    for ref in refs:
        cell = resolve(ref, view)
        if cell is None or not is_number(cell.value):
            continue
        if cell.row is None:
            return view.scalars[int(ref[1:]) - 1][0][:MAX_LABEL]
        row = " ".join(item for item in view.rows[cell.row] if isinstance(item, str) and item)
        if row:
            if cell.col is None or _numeric_columns(view) < 2:
                return row[:MAX_LABEL]
            head = view.headers[cell.col][:MAX_HEADER]
            return row[: MAX_LABEL - len(SEP) - len(head)] + SEP + head
    return ""


def _unique(label: str, taken: set[str]) -> str:
    """The label itself, or with " (2)", " (3)"... when an earlier claim already has it."""
    candidate, n = label, 1
    while candidate in taken:
        n += 1
        suffix = f" ({n})"
        candidate = label[: MAX_LABEL - len(suffix)] + suffix
    taken.add(candidate)
    return candidate


def _prose(text: str, view: ResultView, qnums: set, protected: set) -> str | None:  # type: ignore[type-arg]
    clean = tidy(text, view, protected)
    return clean if clean and prose_ok(clean, view, qnums) else None


def build_report(
    out: ClaimsOut, view: ResultView, beaver: BeaverPayload, question: str
) -> tuple[ReportDraft, list[VerdictRecord]] | None:
    """None when no claim survives scrubbing (the writer's output was not usable)."""
    qnums = exact_tokens(question)
    protected = qnums | view.label_numbers()
    kept: list[tuple[str, list[str], Verdict]] = []
    for raw, cells in zip(out.claim_texts, out.claim_cells, strict=True):
        text = tidy(raw, view, protected)
        if not text:
            continue
        refs = cells.split(",")
        kept.append((text, refs, check_claim(text, refs, view, qnums)))
    if not kept:
        return None

    reasons: list[ReportReason] = []
    for _, _, verdict in kept:
        if verdict.reason is not None and verdict.reason not in reasons:
            reasons.append(verdict.reason)
    note_ref = {reason: f"U{i}" for i, reason in enumerate(reasons, 1)}

    claims: list[ClaimRow] = []
    records: list[VerdictRecord] = []
    for n, (text, _refs, verdict) in enumerate(kept, 1):
        evidence_refs = ["D1"] + ([note_ref[verdict.reason]] if verdict.reason else [])
        claims.append(
            ClaimRow(n=n, text=text, status=verdict.status,
                     computed_value=verdict.computed_value, evidence_refs=evidence_refs)
        )  # fmt: skip
        records.append(VerdictRecord(n=n, status=verdict.status, reason=verdict.reason))
    verified = sum(c.status is ClaimStatus.VERIFIED for c in claims)

    d1 = EvidenceRow(
        ref="D1", type=EvidenceType.TABLE.value, source="beaver",
        location=f"rows 1–{view.row_count}",
        payload=EvidencePayload(
            columns=view.columns, rows_used=view.rows_used, tool=TABLE_TOOL,
            method=EvidenceMethod(beaver.method),
            table=EvidenceTable(
                headers=view.headers, rows=[[format_cell(c) for c in row] for row in view.rows]
            ),
        ),
    )  # fmt: skip
    notes = [
        EvidenceRow(ref=note_ref[r], type=EvidenceType.CRITIC_NOTE.value, location=None,
                    payload=EvidencePayload(reason=r), source="cat")
        for r in reasons
    ]  # fmt: skip

    first_verified = next((c.text for c in claims if c.status is ClaimStatus.VERIFIED), None)
    title = (
        _prose(out.title, view, qnums, protected) or scrub_text(question)[:100].strip() or "Report"
    )
    answer = _prose(out.answer, view, qnums, protected) or first_verified or claims[0].text
    meaning = _prose(out.meaning, view, qnums, protected) if out.meaning.strip() else None
    steps = [
        s for s in (tidy(x, view, protected) for x in out.next_steps) if s and not has_number(s)
    ]

    taken: set[str] = set()
    summary = ReportSummary(
        answer=answer,
        top_rows=[
            TopRow(
                label=_unique(_row_label(refs, view) or f"#{c.n}", taken),
                value=c.computed_value or "",
                status=c.status,
            )
            for c, (_, refs, _v) in zip(claims, kept, strict=True)
        ][:MAX_TOP_ROWS],
        in_short=[InShort(status=c.status, text=c.text) for c in claims],
        meaning=meaning,
        next_steps=steps,
    )  # fmt: skip
    draft = ReportDraft(
        title=title, summary=summary, confidence=confidence_of(verified, len(claims)),
        verified_count=verified, total_claims=len(claims), claims=claims, evidence=[d1, *notes],
    )  # fmt: skip
    return draft, records
