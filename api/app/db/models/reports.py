import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, Text, UniqueConstraint
from sqlalchemy import text as sql_text  # the Claim.text column shadows text() inside that class
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    ClaimOrigin,
    ClaimStatus,
    Confidence,
    EvidenceType,
    ReportTemplate,
    ReportTypeface,
    RunMode,
    TextSize,
)
from app.db.base import Base, Timestamp, created_at_col, enum_check, uuid_pk


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid_pk]
    run_id: Mapped[uuid.UUID] = mapped_column(unique=True)  # one report per run
    owner_id: Mapped[uuid.UUID] = mapped_column(index=True)
    mode: Mapped[str] = mapped_column(Text)  # copied from the run
    title: Mapped[str] = mapped_column(Text)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB)  # shape per mode, see DATA.md
    # Computed in code from the claim statuses; null when the critic did not run.
    confidence: Mapped[str | None] = mapped_column(Text)
    verified_count: Mapped[int] = mapped_column(default=0, server_default=sql_text("0"))
    total_claims: Mapped[int] = mapped_column(default=0, server_default=sql_text("0"))
    pdf_key: Mapped[str | None] = mapped_column(Text)
    template: Mapped[str] = mapped_column(
        Text, default=ReportTemplate.PLAIN, server_default=ReportTemplate.PLAIN.value
    )
    typeface: Mapped[str] = mapped_column(
        Text, default=ReportTypeface.CLEAN, server_default=ReportTypeface.CLEAN.value
    )
    text_size: Mapped[str] = mapped_column(
        Text, default=TextSize.M, server_default=TextSize.M.value
    )
    # Prose in other site languages, for example {"ko": {...}}; generated, never edited by hand.
    translations: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[created_at_col]
    expires_at: Mapped[Timestamp]
    deleted_at: Mapped[Timestamp | None]
    purge_at: Mapped[Timestamp | None]

    claims: Mapped[list["Claim"]] = relationship(order_by="Claim.n", viewonly=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "owner_id"], ["runs.id", "runs.user_id"], ondelete="CASCADE"
        ),
        # (id, owner_id) lets claims prove they have the same owner as their report.
        UniqueConstraint("id", "owner_id", name="uq_reports_id_owner_id"),
        Index("ix_reports_expires_at", "expires_at"),
        Index("ix_reports_purge_at", "purge_at"),
        Index("ix_reports_owner_id_created_at", "owner_id", "created_at"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 300", name="title"),
        CheckConstraint(
            "verified_count >= 0 AND total_claims >= verified_count", name="claim_counts"
        ),
        CheckConstraint("total_claims > 0 OR confidence IS NULL", name="confidence_needs_claims"),
        enum_check("mode", RunMode, "mode"),
        enum_check("confidence", Confidence, "confidence"),
        enum_check("template", ReportTemplate, "template"),
        enum_check("typeface", ReportTypeface, "typeface"),
        enum_check("text_size", TextSize, "text_size"),
    )


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[uuid_pk]
    report_id: Mapped[uuid.UUID]
    owner_id: Mapped[uuid.UUID] = mapped_column(index=True)
    n: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(Text)
    doc_quote: Mapped[str | None] = mapped_column(Text)
    doc_location: Mapped[str | None] = mapped_column(Text)
    doc_value: Mapped[str | None] = mapped_column(Text)
    computed_value: Mapped[str | None] = mapped_column(Text)
    # The `ref` values of the evidence that backs the claim; empty when nothing was found.
    evidence_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=sql_text("'{}'::text[]")
    )
    ko: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # {"text": ...}, DATA.md claims.ko

    __table_args__ = (
        ForeignKeyConstraint(
            ["report_id", "owner_id"], ["reports.id", "reports.owner_id"], ondelete="CASCADE"
        ),
        UniqueConstraint("report_id", "n", name="uq_claims_report_id_n"),
        CheckConstraint("n >= 1", name="n"),
        enum_check("status", ClaimStatus, "status"),
        enum_check("origin", ClaimOrigin, "origin"),
    )


class Evidence(Base):
    """Snapshot of what backs a claim, so the report still works after the file is deleted."""

    __tablename__ = "evidence"

    id: Mapped[uuid_pk]
    run_id: Mapped[uuid.UUID]
    owner_id: Mapped[uuid.UUID] = mapped_column(index=True)
    step_id: Mapped[uuid.UUID]
    ref: Mapped[str] = mapped_column(Text)  # D1, R1, U1 ...
    type: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)

    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "owner_id"], ["runs.id", "runs.user_id"], ondelete="CASCADE"
        ),
        # The step must belong to the same run.
        ForeignKeyConstraint(
            ["step_id", "run_id"], ["agent_steps.id", "agent_steps.run_id"], ondelete="CASCADE"
        ),
        UniqueConstraint("run_id", "ref", name="uq_evidence_run_id_ref"),
        Index("ix_evidence_step_id", "step_id"),
        CheckConstraint("char_length(ref) BETWEEN 1 AND 16", name="ref"),
        enum_check("type", EvidenceType, "type"),
    )
