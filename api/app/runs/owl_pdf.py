"""Owl for a PDF: the route is decided in CODE from the upload type, so there is no model call and
no cap slot. It says what it will do (two trace lines) and hands the upload to Hound."""

from app.core.enums import AgentKey, Bubble, StepKind, StepState, TraceKey
from app.runs.agents import AgentContext, AgentDone, AgentResult
from app.runs.pdf_schemas import OwlPdfPlan
from app.runs.trace import TraceLine


class OwlPdfAgent:
    key = AgentKey.MANAGER

    def run(self, ctx: AgentContext) -> AgentResult:
        ctx.emit(
            TraceLine(
                AgentKey.MANAGER,
                StepKind.SAY,
                StepState.RUNNING,
                TraceKey.PLAN,
                {"files": len(ctx.upload_ids)},
                bubble=Bubble.OWL_SPLIT,
            )  # fmt: skip
        )
        ctx.emit(
            TraceLine(
                AgentKey.MANAGER,
                StepKind.SAY,
                StepState.RUNNING,
                TraceKey.DISPATCH,
                {"agents": 1},
                bubble=Bubble.OWL_SPLIT,
            )  # fmt: skip
        )
        return AgentDone(data=OwlPdfPlan(upload_id=ctx.upload_ids[0]))
