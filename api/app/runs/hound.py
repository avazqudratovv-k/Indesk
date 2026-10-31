"""Hound, the searcher (PDF). Finds the passages of the run's own PDF that bear on the question:
hybrid search (app.services.retrieval), the embedding through the gateway. A failed embedding is
not a failed step: the search runs on words alone (trace arg mode=keyword). Only a daily cap stops
the run here. No passage passing the floor is an honest empty result, not an error.

NOT VERIFIED against real Gemini: tested with the fake client."""

from app.core.config import Limits
from app.core.enums import AgentKey, RunReason, StepKind, StepState, TraceKey
from app.runs.agents import AgentContext, AgentDone, AgentFailed, AgentResult
from app.runs.mapping import failure_from_gateway
from app.runs.pdf_schemas import HoundPassage, HoundPayload, HoundResult
from app.runs.trace import TraceLine
from app.services import retrieval


class HoundAgent:
    key = AgentKey.RETRIEVAL

    def __init__(self, limits: Limits) -> None:
        self._limits = limits

    def run(self, ctx: AgentContext) -> AgentResult:
        if not ctx.gateway.is_configured():
            return AgentFailed(RunReason.MODEL_UNAVAILABLE)
        factory = ctx.session_factory
        if factory is None:
            return AgentFailed(RunReason.INTERNAL_ERROR)
        with factory() as db:
            docs = retrieval.run_documents(db, ctx.run_id, ctx.user_id)
        if len(docs) != 1:
            return AgentFailed(RunReason.INPUT_UNUSABLE)
        doc = docs[0]
        ctx.emit(
            TraceLine(AgentKey.RETRIEVAL, StepKind.TOOL, StepState.RUNNING, TraceKey.SEARCH,
                      {"pages": doc.page_count})
        )  # fmt: skip
        found = retrieval.search(
            factory, ctx.gateway, run_id=ctx.run_id, user_id=ctx.user_id, question=ctx.question,
            model=ctx.gateway.embed_model(), limits=self._limits, now=ctx.monotonic,
            deadline=ctx.deadline,
        )  # fmt: skip
        if found.cap is not None:
            return failure_from_gateway(found.cap)
        passages = [
            HoundPassage(page=p.page, text=p.text, score=p.score, cosine=p.cosine)
            for p in found.passages
        ]
        payload = HoundPayload(
            mode=found.mode, matched=len(passages), pages=[p.page for p in passages],
            scores=[p.score for p in passages], cosines=[p.cosine for p in passages],
            top_cosine=found.top_cosine, embed_tokens=found.embed_tokens,
        )  # fmt: skip
        if passages:
            best = passages[0]
            args: dict[str, int | float] = {"page": best.page, "score": best.score}
            if best.cosine is not None:
                args["similarity"] = best.cosine
            closing = TraceLine(
                AgentKey.RETRIEVAL, StepKind.SAY, StepState.DONE, TraceKey.BEST_PASSAGE,
                args, tok=found.embed_tokens,
            )  # fmt: skip
        else:
            closing = TraceLine(
                AgentKey.RETRIEVAL, StepKind.SAY, StepState.DONE, TraceKey.SEARCH,
                {"pages": doc.page_count, "matched": 0, "mode": found.mode},
                tok=found.embed_tokens,
            )  # fmt: skip
        if found.size_limited:  # not a silent fallback: the reader sees why there were no vectors
            ctx.emit(
                TraceLine(AgentKey.RETRIEVAL, StepKind.SAY, StepState.RUNNING,
                          TraceKey.KEYWORD_ONLY_SIZE, {"reason": "document_size"})
            )  # fmt: skip
        if found.skipped_chunks:
            ctx.emit(
                TraceLine(AgentKey.RETRIEVAL, StepKind.SAY, StepState.RUNNING,
                          TraceKey.CHUNKS_SKIPPED, {"count": found.skipped_chunks})
            )  # fmt: skip
        ctx.emit(closing, payload)
        result = HoundResult(
            upload_id=doc.upload_id, filename=doc.filename, page_count=doc.page_count,
            mode=found.mode, passages=passages,
        )  # fmt: skip
        return AgentDone(tokens_in=found.embed_tokens, data=result)
