"""Report, Claim and Evidence exactly as the web mock contract (web/lib/types.ts, ROADMAP 2.7).

Optional keys stay absent when unset, so serialize with exclude_unset=True to get the stored
shape back.
"""

from pydantic import AwareDatetime, Field

from app.core.enums import (
    ClaimOrigin,
    ClaimStatus,
    Confidence,
    EvidenceMethod,
    EvidenceType,
    ReportReason,
    ReportTemplate,
    ReportTypeface,
    RunMode,
    TextSize,
)
from app.schemas.common import ApiModel, Id

# ---- summary_json (shape per mode, DATA.md "summary_json shapes") ----


class TopRow(ApiModel):
    label: str
    value: str
    status: ClaimStatus


class InShort(ApiModel):
    status: ClaimStatus
    text: str


class Total(ApiModel):
    label: str
    a: str
    b: str
    change: str


class Mover(ApiModel):
    label: str
    change_pct: float


class ReportSummary(ApiModel):
    """Every mode has `answer`; the other keys belong to one mode each (Ask, Check, Compare)."""

    answer: str
    # Ask
    top_rows: list[TopRow] | None = None
    in_short: list[InShort] | None = None
    meaning: str | None = None
    next_steps: list[str] | None = None
    # Check
    not_checked: list[str] | None = None
    # Compare
    totals: list[Total] | None = None
    movers: list[Mover] | None = None
    could_not_compare: list[str] | None = None


# ---- translations (reports.translations, claims.ko, evidence.payload.ko) ----


class TopRowTranslation(ApiModel):
    label: str
    value: str


class InShortTranslation(ApiModel):
    text: str


class SummaryTranslation(ApiModel):
    answer: str | None = None
    top_rows: list[TopRowTranslation] | None = None
    in_short: list[InShortTranslation] | None = None
    meaning: str | None = None
    next_steps: list[str] | None = None


class ReportTranslation(ApiModel):
    title: str
    summary_json: SummaryTranslation


class ReportTranslations(ApiModel):
    ko: ReportTranslation | None = None


class ClaimTranslation(ApiModel):
    text: str


# ---- evidence ----


class EvidenceTable(ApiModel):
    headers: list[str]
    rows: list[list[str]]


class ChartPoint(ApiModel):
    label: str
    value: float  # computed in code, never by the model
    photo_value: float


class EvidenceChart(ApiModel):
    title: str
    unit: str
    series: list[ChartPoint]


class ChartPointTranslation(ApiModel):
    label: str


class ChartTranslation(ApiModel):
    title: str
    series: list[ChartPointTranslation]


class EvidencePayloadTranslation(ApiModel):
    title: str | None = None
    body: str | None = None
    table: EvidenceTable | None = None
    chart: ChartTranslation | None = None


class EvidencePayload(ApiModel):
    """The snapshot behind a claim. Every key is optional: which keys exist depends on the type."""

    title: str | None = None
    body: str | None = None
    tool: str | None = None
    code: str | None = None
    quote: str | None = None
    text: str | None = None
    columns: list[str] | None = None
    rows_used: int | None = None
    table: EvidenceTable | None = None
    chart: EvidenceChart | None = None  # rides on the payload of the D1 table evidence
    # Closed codes (P9), translated in the browser; never a sentence.
    reason: ReportReason | None = None  # on a critic_note: why a claim is not verified
    method: EvidenceMethod | None = None  # on a table: how its numbers were computed
    ko: EvidencePayloadTranslation | None = None


class Evidence(ApiModel):
    id: Id
    run_id: Id
    step_id: Id
    ref: str
    type: EvidenceType
    file_name: str
    location: str | None
    payload: EvidencePayload


# ---- claims and report ----


class Claim(ApiModel):
    id: Id
    report_id: Id
    n: int
    text: str
    status: ClaimStatus
    origin: ClaimOrigin
    doc_quote: str | None
    doc_location: str | None
    doc_value: str | None
    computed_value: str | None
    evidence_refs: list[str]
    ko: ClaimTranslation | None = None


class Report(ApiModel):
    id: Id
    run_id: Id
    owner_id: Id
    mode: RunMode
    title: str
    summary_json: ReportSummary
    confidence: Confidence | None
    verified_count: int
    total_claims: int
    pdf_key: str | None
    template: ReportTemplate
    typeface: ReportTypeface
    text_size: TextSize
    created_at: AwareDatetime
    expires_at: AwareDatetime
    deleted_at: AwareDatetime | None
    purge_at: AwareDatetime | None
    translations: ReportTranslations | None = None


class ReportDetail(ApiModel):
    """GET /api/reports/{id}: the report with its claims and evidence."""

    report: Report
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
