"""Cat for a PDF. ONE writer call on the main chain (flat parallel lists, PdfClaimsOut), no executor
retry (like Cat on a CSV); then the checks are code (cat_pdf_checks).

No passages from Hound: no model call, the run ends `not_answerable`. The writer also says
`found: false` (no claims) when the passages do not answer the question: same ending, no report.
The answer text is never searched for "not in the document" wording (that would depend on the
language): a found true with claims is trusted; the prompt and the Hound floor carry the rest.

NOT VERIFIED against real Gemini: tested with the fake client."""

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
from app.runs.cat_pdf_report import build_pdf_report
from app.runs.cat_schemas import CatPayload, CatResult, PdfClaimsOut, VerdictRecord
from app.runs.mapping import failure_from_gateway
from app.runs.pdf_schemas import HoundResult
from app.runs.prompts import PDF_WRITER_PROMPT_VERSION, build_pdf_writer_prompt, new_nonce
from app.runs.trace import TraceLine
from app.services import retrieval


def _line(state: StepState, tok: int = 0, **args: int) -> TraceLine:
    kind = StepKind.SAY if state is StepState.DONE else StepKind.TOOL
    return TraceLine(AgentKey.CRITIC, kind, state, TraceKey.VERIFY, args, tok=tok)


class CatPdfAgent:
    key = AgentKey.CRITIC

    def __init__(
        self, limits: Limits, hound: HoundResult, nonce: Callable[[], str] = new_nonce
    ) -> None:
        self._limits = limits
        self._hound = hound
        self._nonce = nonce

    def run(self, ctx: AgentContext) -> AgentResult:
        hound = self._hound
        if not hound.passages:
            ctx.emit(_line(StepState.RUNNING))
            ctx.emit(_line(StepState.DONE, claims=0, verified=0), self._payload([]))
            return AgentDone(data=CatResult(outcome=RunOutcome.NOT_ANSWERABLE, report=None))
        if not ctx.gateway.is_configured():
            return AgentFailed(RunReason.MODEL_UNAVAILABLE)
        factory = ctx.session_factory
        if factory is None:
            return AgentFailed(RunReason.INTERNAL_ERROR)
        ctx.emit(_line(StepState.RUNNING))
        language = "Korean" if ctx.lang == "ko" else "English"
        shown = [{"page": p.page, "text": p.text} for p in hound.passages]
        pair = build_pdf_writer_prompt(ctx.question, language, shown, nonce=self._nonce())
        asked = ctx.gateway.ask(
            pair.prompt, system=pair.system, purpose=AiPurpose.EXTRACT_CLAIMS, user_id=ctx.user_id,
            run_id=ctx.run_id, response_model=PdfClaimsOut, job_class=JobClass.MAIN,
        )  # fmt: skip
        if isinstance(asked, GatewayError):
            return dataclasses.replace(failure_from_gateway(asked), retryable=False)
        if not isinstance(asked.parsed, PdfClaimsOut):
            return AgentFailed(RunReason.BAD_MODEL_OUTPUT)
        tokens = asked.tokens_in + asked.tokens_out
        if not asked.parsed.found or not asked.parsed.claim_texts:  # does not answer: no report
            ctx.emit(_line(StepState.DONE, tok=tokens, claims=0, verified=0), self._payload([]))
            return AgentDone(
                asked.tokens_in, asked.tokens_out, asked.model,
                data=CatResult(outcome=RunOutcome.NOT_ANSWERABLE, report=None),
            )  # fmt: skip
        with factory() as db:
            pages = retrieval.load_pages(db, ctx.run_id, ctx.user_id, hound.upload_id)
        built = build_pdf_report(asked.parsed, pages, hound.page_count, ctx.question)
        if built is None:
            return AgentFailed(RunReason.BAD_MODEL_OUTPUT)
        draft, records = built
        ctx.emit(
            _line(
                StepState.DONE, tok=tokens, claims=draft.total_claims,
                verified=draft.verified_count,
            ),
            self._payload(records),
        )  # fmt: skip
        outcome = (
            RunOutcome.ANSWERED
            if draft.verified_count == draft.total_claims
            else RunOutcome.PARTIAL
        )
        return AgentDone(
            asked.tokens_in, asked.tokens_out, asked.model,
            data=CatResult(outcome=outcome, report=draft),
        )  # fmt: skip

    @staticmethod
    def _payload(records: list[VerdictRecord]) -> CatPayload:
        return CatPayload(
            prompt_version=PDF_WRITER_PROMPT_VERSION, rows_mismatch=False, verdicts=records
        )
