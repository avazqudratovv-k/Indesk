import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    AgentKey,
    Bubble,
    FileRole,
    Lang,
    QuestionType,
    RunMode,
    RunOutcome,
    RunStatus,
    StepKind,
    StepState,
)
from app.db.base import Base, Timestamp, created_at_col, enum_check, uuid_pk
from app.db.models.reports import Report


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, default=RunStatus.QUEUED, server_default=RunStatus.QUEUED.value
    )
    outcome: Mapped[str | None] = mapped_column(Text)
    outcome_reason: Mapped[str | None] = mapped_column(Text)
    counted: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    lang: Mapped[str] = mapped_column(Text)
    tokens_in: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    tokens_out: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    tool_calls: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal(0), server_default=text("0")
    )
    created_at: Mapped[created_at_col]
    started_at: Mapped[Timestamp | None]
    finished_at: Mapped[Timestamp | None]
    error: Mapped[str | None] = mapped_column(Text)

    steps: Mapped[list["AgentStep"]] = relationship(order_by="AgentStep.seq", viewonly=True)
    report: Mapped[Report | None] = relationship(viewonly=True)

    @property
    def report_id(self) -> uuid.UUID | None:
        return self.report.id if self.report else None

    __table_args__ = (
        # (id, user_id) lets child rows prove they have the same owner as the run.
        UniqueConstraint("id", "user_id", name="uq_runs_id_user_id"),
        Index("ix_runs_user_id_created_at", "user_id", "created_at"),
        CheckConstraint("char_length(question) BETWEEN 1 AND 1000", name="question"),
        CheckConstraint("tokens_in >= 0 AND tokens_out >= 0 AND tool_calls >= 0", name="counters"),
        CheckConstraint("cost_usd >= 0", name="cost_usd"),
        CheckConstraint("status <> 'finished' OR outcome IS NOT NULL", name="finished_has_outcome"),
        enum_check("mode", RunMode, "mode"),
        enum_check("question_type", QuestionType, "question_type"),
        enum_check("status", RunStatus, "status"),
        enum_check("outcome", RunOutcome, "outcome"),
        enum_check("lang", Lang, "lang"),
    )


class RunFile(Base):
    """Which upload a run used, and in which role. Both composite foreign keys carry the owner, so a
    run cannot use another user's upload: the database rejects it."""

    __tablename__ = "run_files"

    run_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    upload_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(index=True)
    role: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "owner_id"], ["runs.id", "runs.user_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["upload_id", "owner_id"], ["uploads.id", "uploads.user_id"], ondelete="CASCADE"
        ),
        # One subject / a / b per run; "source" may repeat (Check allows up to 4 sources).
        Index(
            "uq_run_files_run_id_role_single",
            "run_id",
            "role",
            unique=True,
            postgresql_where=text("role <> 'source'"),
        ),
        enum_check("role", FileRole, "role"),
    )


class AgentStep(Base):
    """One row per trace event. `seq` is monotonic per run and becomes the SSE event id, so a client
    can resume after a dropped connection. `key` is a message key and `args` its values: never free
    model text."""

    __tablename__ = "agent_steps"

    id: Mapped[uuid_pk]
    run_id: Mapped[uuid.UUID]
    owner_id: Mapped[uuid.UUID] = mapped_column(index=True)
    seq: Mapped[int]
    agent: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    key: Mapped[str] = mapped_column(Text)
    args: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    tok: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    bubble: Mapped[str | None] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # validated structured result
    started_at: Mapped[Timestamp | None]
    finished_at: Mapped[Timestamp | None]
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal(0), server_default=text("0")
    )
    model: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "owner_id"], ["runs.id", "runs.user_id"], ondelete="CASCADE"
        ),
        UniqueConstraint("run_id", "seq", name="uq_agent_steps_run_id_seq"),
        UniqueConstraint("id", "run_id", name="uq_agent_steps_id_run_id"),
        CheckConstraint("seq >= 1", name="seq"),
        CheckConstraint("char_length(key) BETWEEN 1 AND 64", name="key"),
        CheckConstraint("tok >= 0", name="tok"),
        CheckConstraint("attempt IN (1, 2)", name="attempt"),
        CheckConstraint("cost_usd >= 0", name="cost_usd"),
        enum_check("agent", AgentKey, "agent"),
        enum_check("kind", StepKind, "kind"),
        enum_check("state", StepState, "state"),
        enum_check("bubble", Bubble, "bubble"),
    )
