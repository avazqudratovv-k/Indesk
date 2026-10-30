import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AiCallStatus, AiPurpose, FailureKind, UsageKind
from app.db.base import Base, created_at_col, enum_check, uuid_pk


class AiCall(Base):
    """One row per Gemini request. Metadata only: never a prompt, a question or file text."""

    __tablename__ = "ai_calls"

    id: Mapped[uuid_pk]
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), index=True
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_steps.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    attempt: Mapped[int]  # 1 = first model in the chain, 2 and 3 = fallbacks
    status: Mapped[str] = mapped_column(Text)
    tokens_in: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    tokens_out: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    est_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal(0), server_default=text("0")
    )
    latency_ms: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    # A closed code (FailureKind) for a failed request, so the cause of a fallback is not hidden.
    failure_kind: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[created_at_col]

    __table_args__ = (
        Index("ix_ai_calls_created_at", "created_at"),  # daily purge (ai_calls_retention_days)
        CheckConstraint("char_length(model) BETWEEN 1 AND 100", name="model"),
        CheckConstraint("attempt BETWEEN 1 AND 3", name="attempt"),
        CheckConstraint("tokens_in >= 0 AND tokens_out >= 0 AND latency_ms >= 0", name="counters"),
        CheckConstraint("est_cost_usd >= 0", name="est_cost_usd"),
        enum_check("purpose", AiPurpose, "purpose"),
        enum_check("status", AiCallStatus, "status"),
        enum_check("failure_kind", FailureKind, "failure_kind"),  # NULL passes a CHECK
    )


class UsageDaily(Base):
    """Daily counters that feed the caps. One row per (day, scope): 'global' or 'user:<uuid>'.
    The unique key lets the later cap check be one atomic INSERT ... ON CONFLICT DO UPDATE ... WHERE
    count < cap."""

    __tablename__ = "usage_daily"

    id: Mapped[uuid_pk]
    day: Mapped[date]
    scope: Mapped[str] = mapped_column(Text)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    runs: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    model_calls: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    est_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal(0), server_default=text("0")
    )

    __table_args__ = (
        UniqueConstraint("day", "scope", name="uq_usage_daily_day_scope"),
        CheckConstraint(
            "(scope = 'global' AND user_id IS NULL)"
            " OR (user_id IS NOT NULL AND scope = 'user:' || user_id::text)",
            name="scope",
        ),
        CheckConstraint("runs >= 0 AND model_calls >= 0 AND est_cost_usd >= 0", name="counters"),
    )


class UsageEvent(Base):
    """Plan quota is computed from these rows. Kept: the source of truth for the free-run count."""

    __tablename__ = "usage_events"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(Text)
    amount: Mapped[int]
    created_at: Mapped[created_at_col]

    __table_args__ = (
        Index("ix_usage_events_user_id_created_at", "user_id", "created_at"),
        Index("ix_usage_events_created_at", "created_at"),
        Index("ix_usage_events_run_id", "run_id"),
        # One quota row per run: finishing twice cannot count a run twice. NULL run ids (a deleted
        # run) are distinct, so they never collide.
        Index(
            "uq_usage_events_run_id_run",
            "run_id",
            unique=True,
            postgresql_where=text("kind = 'run'"),
        ),
        CheckConstraint("amount > 0", name="amount"),
        enum_check("kind", UsageKind, "kind"),
    )


class AuditLog(Base):
    """Action, target and a hashed IP. Kept, never purged. Survives user deletion (user_id null)."""

    __tablename__ = "audit_log"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(Text)
    target: Mapped[str | None] = mapped_column(Text)
    ip_hash: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[created_at_col]

    __table_args__ = (
        Index("ix_audit_log_created_at", "created_at"),
        CheckConstraint("char_length(action) BETWEEN 1 AND 64", name="action"),
    )
