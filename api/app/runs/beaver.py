"""Beaver, the analyst (Ask). One main-chain model call writes pandas code for Owl's plan; the code
runs ONLY in the sandbox (AST check on, no network, CPU and memory limits); the result is checked
against ComputedResult and stored, with the code, on the final line's payload for Cat (P9).

The model's code is untrusted. This module never executes it: `ast.parse` below only reads it, so a
syntax slip is a bad model output (retried once) and not the sandbox's `bad_input` (which the
mapping treats as the user's fault).

The one retry (made by the executor, which calls run() again on the same object) adds to the prompt
only a fixed hint chosen from the failure KIND (prompts.HINT_TEXT). The sandbox returns no
traceback, and neither the earlier code nor any model text is sent back.

NOT VERIFIED against real Gemini: tested with the fake gateway and a fake sandbox."""

import ast
import json
from collections.abc import Callable

from pydantic import ValidationError

from app.ai.gateway import GatewayError
from app.core.config import Limits
from app.core.enums import (
    AgentKey,
    AiPurpose,
    JobClass,
    RunReason,
    SandboxErrorCode,
    StepKind,
    StepState,
    TraceKey,
)
from app.runs.agents import AgentContext, AgentDone, AgentFailed, AgentResult
from app.runs.ask_schemas import BeaverCode, BeaverPayload, ComputedResult, OwlPlan
from app.runs.mapping import failure_from_gateway, failure_from_sandbox
from app.runs.profile import ProfileFailed, build_profile
from app.runs.prompts import (
    BEAVER_PROMPT_VERSION,
    OWL_PROMPT_VERSION,
    RetryHint,
    build_beaver_prompt,
    new_nonce,
)
from app.runs.trace import TraceLine
from app.sandbox_client import SandboxError

# A ranking can only be checked by Cat against other rows (cat_checks: at least 2 rows), so a rank
# plan always asks Beaver for at least this many, even for "which station has the most" (found in
# the first P9 live run, where top_n=1 left a correct "most" claim unverified).
MIN_RANK_ROWS = 5

_SANDBOX_HINTS = {
    SandboxErrorCode.FORBIDDEN: RetryHint.FORBIDDEN,
    SandboxErrorCode.RUNTIME: RetryHint.RUNTIME,
    SandboxErrorCode.TIMEOUT: RetryHint.TIMEOUT,
}


def _line(state: StepState, key: TraceKey, tok: int = 0, **args: int) -> TraceLine:
    kind = StepKind.SAY if state is StepState.DONE else StepKind.TOOL
    return TraceLine(AgentKey.DATA, kind, state, key, args, tok=tok)


class BeaverAgent:
    key = AgentKey.DATA

    def __init__(self, limits: Limits, plan: OwlPlan, nonce: Callable[[], str] = new_nonce) -> None:
        self._limits = limits
        self._plan = plan
        self._nonce = nonce
        self._hint: RetryHint | None = None  # why the last attempt failed, for the retry only

    def run(self, ctx: AgentContext) -> AgentResult:
        if not ctx.gateway.is_configured():
            return AgentFailed(RunReason.MODEL_UNAVAILABLE)
        data = ctx.read_upload(ctx.upload_ids[0])
        if data is None:
            return AgentFailed(RunReason.INPUT_UNUSABLE)
        profile = build_profile(data, self._limits)
        if isinstance(profile, ProfileFailed):
            return AgentFailed(RunReason.INPUT_UNUSABLE)
        ctx.emit(
            _line(
                StepState.RUNNING,
                TraceKey.READ_CSV,
                rows=profile.row_count,
                cols=len(profile.columns),
            )  # fmt: skip
        )
        hint = self._hint if ctx.attempt > 1 else None
        plan = self._plan
        if plan.task == "rank" and plan.top_n < MIN_RANK_ROWS:
            plan = plan.model_copy(update={"top_n": MIN_RANK_ROWS})
        pair = build_beaver_prompt(ctx.question, plan, profile, nonce=self._nonce(), hint=hint)
        asked = ctx.gateway.ask(
            pair.prompt, system=pair.system, purpose=AiPurpose.COMPUTE, user_id=ctx.user_id,
            run_id=ctx.run_id, response_model=BeaverCode, job_class=JobClass.MAIN,
        )  # fmt: skip
        if isinstance(asked, GatewayError):
            return failure_from_gateway(asked)
        if not isinstance(asked.parsed, BeaverCode):
            return AgentFailed(RunReason.BAD_MODEL_OUTPUT, retryable=True)
        code = asked.parsed.code
        try:
            ast.parse(code)  # reads only; nothing here runs the code
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            self._hint = RetryHint.BAD_SYNTAX
            return AgentFailed(RunReason.BAD_MODEL_OUTPUT, retryable=True)
        ctx.emit(_line(StepState.RUNNING, TraceKey.RUN_PYTHON, attempt=ctx.attempt))
        ran = ctx.sandbox(code, data)
        if isinstance(ran, SandboxError):
            self._hint = _SANDBOX_HINTS.get(ran.code)
            return failure_from_sandbox(ran)
        try:
            result = ComputedResult.model_validate(ran.result)
        except ValidationError:
            self._hint = RetryHint.BAD_RESULT
            return AgentFailed(RunReason.BAD_MODEL_OUTPUT, retryable=True)
        payload = BeaverPayload(
            owl_prompt_version=OWL_PROMPT_VERSION,
            beaver_prompt_version=BEAVER_PROMPT_VERSION,
            attempt=ctx.attempt,
            method=self._plan.task,
            row_count=profile.row_count,
            rows_used=result.rows_used,
            result=result,
            code=code,
        )
        stored = len(json.dumps(result.model_dump(mode="json")).encode())
        if stored > self._limits.max_stored_result_bytes:
            # Never cut: Cat cannot verify a cut value. Same code, same size, so no retry.
            return AgentFailed(RunReason.ANALYSIS_FAILED)
        ctx.emit(
            _line(StepState.DONE, TraceKey.TOP3, tok=asked.tokens_in + asked.tokens_out,
                  rows=len(result.rows)),
            payload,
        )  # fmt: skip
        return AgentDone(asked.tokens_in, asked.tokens_out, asked.model, data=payload)
