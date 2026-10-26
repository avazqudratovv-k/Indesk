"""Owl, the planner (Ask). One light-chain model call turns the question and the CSV profile into
an OwlPlan of closed words and real column names. Nothing is computed here.

Order of work, so nothing is wasted: key check (before the file is even read), read the file,
profile it (a non-comma or unreadable CSV ends here as input_unusable, with no model call and no
cap slot), then ONE gateway call. A plan that names a column the file does not have is a bad plan:
bad_model_output, retried once by the executor.

NOT VERIFIED against real Gemini: tested with the fake gateway only."""

from collections.abc import Callable

from app.ai.gateway import GatewayError
from app.core.config import Limits
from app.core.enums import (
    AgentKey,
    AiPurpose,
    Bubble,
    JobClass,
    RunReason,
    StepKind,
    StepState,
    TraceKey,
)
from app.runs.agents import AgentContext, AgentDone, AgentFailed, AgentResult
from app.runs.ask_schemas import OwlPayload, OwlPlan
from app.runs.mapping import failure_from_gateway
from app.runs.profile import ProfileFailed, build_profile
from app.runs.prompts import OWL_PROMPT_VERSION, build_owl_prompt, new_nonce
from app.runs.trace import TraceLine


class OwlAgent:
    key = AgentKey.MANAGER

    def __init__(self, limits: Limits, nonce: Callable[[], str] = new_nonce) -> None:
        self._limits = limits
        self._nonce = nonce

    def run(self, ctx: AgentContext) -> AgentResult:
        if not ctx.gateway.is_configured():
            # No key or no chains: not transient, so no retry. Fails before any file work.
            return AgentFailed(RunReason.MODEL_UNAVAILABLE)
        data = ctx.read_upload(ctx.upload_ids[0])
        if data is None:
            return AgentFailed(RunReason.INPUT_UNUSABLE)
        profile = build_profile(data, self._limits)
        if isinstance(profile, ProfileFailed):
            return AgentFailed(RunReason.INPUT_UNUSABLE)
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
        pair = build_owl_prompt(ctx.question, profile, nonce=self._nonce())
        result = ctx.gateway.ask(
            pair.prompt, system=pair.system, purpose=AiPurpose.PLAN, user_id=ctx.user_id,
            run_id=ctx.run_id, response_model=OwlPlan, job_class=JobClass.LIGHT,
        )  # fmt: skip
        if isinstance(result, GatewayError):
            return failure_from_gateway(result)
        plan = result.parsed
        known = set(profile.column_names)
        if not isinstance(plan, OwlPlan) or any(c not in known for c in plan.named_columns()):
            return AgentFailed(RunReason.BAD_MODEL_OUTPUT, retryable=True)
        ctx.emit(
            TraceLine(
                AgentKey.MANAGER,
                StepKind.SAY,
                StepState.RUNNING,
                TraceKey.DISPATCH,
                {"agents": 1},
                tok=result.tokens_in + result.tokens_out,
                bubble=Bubble.OWL_SPLIT,
            ),  # fmt: skip
            OwlPayload(prompt_version=OWL_PROMPT_VERSION, attempt=ctx.attempt, plan=plan),
        )
        return AgentDone(result.tokens_in, result.tokens_out, result.model, data=plan)
