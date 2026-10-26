"""Cat, the critic (Ask). The verdicts are CODE (cat_checks); the one model call here only writes
the sentences, from Beaver's computed table, and cites the cells they rely on.

Budget: exactly ONE gateway call, with NO executor retry (a deliberate exception to DECISIONS #42,
owner decision P9). A failure ends the run with the mapped reason and no report.

An empty result table has nothing to write about: no model call, the run ends `not_answerable`.

NOT VERIFIED against real Gemini until the P9 live runs: tested with the fake gateway."""

import dataclasses
from collections.abc import Callable

from app.ai.gateway import GatewayError
from app.core.config import Limits
from app.core.enums import (
    AgentKey,
    AiPurpose,
    JobClass,
    RunOutcome,
    RunReason,
    StepKind,
    StepState,
    TraceKey,
)
from app.runs.agents import AgentContext, AgentDone, AgentFailed, AgentResult
from app.runs.ask_schemas import BeaverPayload
from app.runs.cat_checks import ResultView
from app.runs.cat_report import build_report
from app.runs.cat_schemas import CatPayload, CatResult, ClaimsOut, VerdictRecord
from app.runs.mapping import failure_from_gateway
from app.runs.prompts import CAT_PROMPT_VERSION, build_cat_prompt, new_nonce
from app.runs.trace import TraceLine


def _line(state: StepState, tok: int = 0, **args: int) -> TraceLine:
    kind = StepKind.SAY if state is StepState.DONE else StepKind.TOOL
    return TraceLine(AgentKey.CRITIC, kind, state, TraceKey.VERIFY, args, tok=tok)


class CatAgent:
    key = AgentKey.CRITIC

    def __init__(
        self, limits: Limits, beaver: BeaverPayload, nonce: Callable[[], str] = new_nonce
    ) -> None:
        self._limits = limits
        self._beaver = beaver
        self._nonce = nonce

    def run(self, ctx: AgentContext) -> AgentResult:
        view = ResultView.of(self._beaver.result, self._beaver.row_count)
        if not view.rows:
            ctx.emit(_line(StepState.RUNNING))
            ctx.emit(_line(StepState.DONE, claims=0, verified=0), self._payload(view, []))
            return AgentDone(data=CatResult(outcome=RunOutcome.NOT_ANSWERABLE, report=None))
        if not ctx.gateway.is_configured():
            return AgentFailed(RunReason.MODEL_UNAVAILABLE)
        ctx.emit(_line(StepState.RUNNING))
        language = "Korean" if ctx.lang == "ko" else "English"
        pair = build_cat_prompt(ctx.question, language, view.prompt_table(), nonce=self._nonce())
        asked = ctx.gateway.ask(
            pair.prompt, system=pair.system, purpose=AiPurpose.EXTRACT_CLAIMS, user_id=ctx.user_id,
            run_id=ctx.run_id, response_model=ClaimsOut, job_class=JobClass.MAIN,
        )  # fmt: skip
        if isinstance(asked, GatewayError):
            return dataclasses.replace(failure_from_gateway(asked), retryable=False)
        if not isinstance(asked.parsed, ClaimsOut):
            return AgentFailed(RunReason.BAD_MODEL_OUTPUT)
        built = build_report(asked.parsed, view, self._beaver, ctx.question)
        if built is None:
            return AgentFailed(RunReason.BAD_MODEL_OUTPUT)
        draft, records = built
        tokens = asked.tokens_in + asked.tokens_out
        ctx.emit(
            _line(
                StepState.DONE, tok=tokens, claims=draft.total_claims,
                verified=draft.verified_count,
            ),
            self._payload(view, records),
        )  # fmt: skip
        all_verified = draft.verified_count == draft.total_claims
        outcome = RunOutcome.ANSWERED if all_verified else RunOutcome.PARTIAL
        return AgentDone(
            asked.tokens_in, asked.tokens_out, asked.model,
            data=CatResult(outcome=outcome, report=draft),
        )  # fmt: skip

    def _payload(self, view: ResultView, records: list[VerdictRecord]) -> CatPayload:
        return CatPayload(
            prompt_version=CAT_PROMPT_VERSION, rows_mismatch=not view.rows_ok, verdicts=records
        )
