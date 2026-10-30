"""Search the text of the PDF a run is about (P14a part 2).

Hybrid search: the nearest chunks by meaning (pgvector cosine distance, exact scan: a 30-page PDF
has a few hundred chunks, so no ANN index) and the best chunks by words (Postgres full text),
fused with reciprocal rank fusion. A chunk found by meaning counts only above a similarity floor, a
chunk found by words only if it holds enough of the question's words; nothing passing means no
passages, and the run ends `not_answerable` without a writer call.

If the embedding fails (or would pass the run's embedding budget), the same search runs on words
alone. Stored vectors are reused: a later question on the same upload embeds the question only.

Ownership: no function here takes an upload id from the caller. Every query selects the uploads
from THIS run's `run_files`, owned by the run's user, still ready and not deleted, and also filters
`chunks.owner_id`. Nothing here logs a question, a passage or a vector."""

import re
import unicodedata
import uuid
from dataclasses import dataclass
from typing import Final, Literal, Protocol

from pgvector.sqlalchemy import Vector
from sqlalchemy import Select, Table, bindparam, func, select, update
from sqlalchemy.orm import Session

from app.ai.caps import SessionFactory
from app.ai.client import estimate_embed_tokens
from app.ai.gateway import EmbedGatewayResult, GatewayError
from app.core.config import Limits
from app.core.enums import EmbedTask, UploadStatus
from app.db.models import Chunk, DocumentPage, RunFile, Upload
from app.db.models.documents import EMBEDDING_DIM
from app.runs import store

MAX_TERMS: Final = 12
EMBED_GROUP: Final = 32  # texts per gateway call: a failure keeps the groups stored before it
_WORD: Final = re.compile(r"[^\W_]+")
# English words that say nothing about a document; a closed list, kept short on purpose.
_STOPWORDS: Final = frozenset(
    """the and for are was were that this with from have has had not but what which who whom whose
    when where why how does did can could would should will shall about into over under than then
    them they their there these those been being its your you our out any all per via""".split()
)


class Clock(Protocol):
    def __call__(self) -> float: ...


class Embedder(Protocol):
    """The part of the gateway this module needs."""

    def embed(
        self,
        texts: list[str],
        *,
        task: EmbedTask,
        user_id: uuid.UUID,
        run_id: uuid.UUID | None = ...,
    ) -> EmbedGatewayResult: ...


@dataclass(frozen=True)
class Passage:
    chunk_id: uuid.UUID
    upload_id: uuid.UUID
    page: int  # 1-based
    ord: int
    text: str
    # 0 to 1: the fused score relative to the best possible one (first in both lists).
    score: float
    # The raw cosine similarity of the chunk to the question (0 to 1), apart from the fused score;
    # None when the chunk came from the word search alone, or the search had no embedding.
    cosine: float | None = None


@dataclass(frozen=True)
class SearchOutcome:
    passages: list[Passage]
    mode: Literal["hybrid", "keyword"]
    embed_tokens: int = 0  # embedding tokens this search used (the gateway's own count)
    cap: GatewayError | None = None  # set when a daily cap stopped the embedding: the run stops
    # The best cosine of any chunk, before the similarity floor (None without an embedding): what
    # the floor is tuned against.
    top_cosine: float | None = None
    # The search ran on words alone because the document needs more embedding tokens than the run's
    # budget (max_embed_tokens_per_run); Hound says so in the trace.
    size_limited: bool = False
    # Chunks too big for the embedding model (embed_chunk_max_tokens): not embedded, found by words.
    skipped_chunks: int = 0


@dataclass(frozen=True)
class DocumentInfo:
    upload_id: uuid.UUID
    filename: str
    page_count: int


# ---- the run's own documents ----


def _own_uploads(run_id: uuid.UUID, user_id: uuid.UUID) -> Select[tuple[uuid.UUID]]:
    return (
        select(RunFile.upload_id)
        .join(Upload, Upload.id == RunFile.upload_id)
        .where(
            RunFile.run_id == run_id,
            RunFile.owner_id == user_id,
            Upload.user_id == user_id,
            Upload.status == UploadStatus.READY,
            Upload.deleted_at.is_(None),
        )
    )


def run_documents(db: Session, run_id: uuid.UUID, user_id: uuid.UUID) -> list[DocumentInfo]:
    rows = db.execute(
        select(Upload.id, Upload.filename, func.coalesce(Upload.page_count, 0)).where(
            Upload.id.in_(_own_uploads(run_id, user_id))
        )
    ).all()
    return [DocumentInfo(r[0], r[1], r[2]) for r in rows]


def load_pages(
    db: Session, run_id: uuid.UUID, user_id: uuid.UUID, upload_id: uuid.UUID
) -> dict[int, str]:
    """The stored text of each page of one of the run's own uploads (empty for any other)."""
    rows = db.execute(
        select(DocumentPage.page, DocumentPage.text).where(
            DocumentPage.upload_id == upload_id,
            DocumentPage.owner_id == user_id,
            DocumentPage.upload_id.in_(_own_uploads(run_id, user_id)),
        )
    ).all()
    return {page: text for page, text in rows}


# ---- the question as search words ----


def query_terms(question: str) -> list[str]:
    """Words of the question worth searching for: lowercase, no stopwords, ASCII words of 3+
    letters, other scripts (Hangul, kana, han) of 2+. At most MAX_TERMS, in order, no repeats."""
    terms: list[str] = []
    for word in _WORD.findall(unicodedata.normalize("NFKC", question).lower()):
        long_enough = len(word) >= 3 if word.isascii() else len(word) >= 2
        if long_enough and word not in _STOPWORDS and word not in terms:
            terms.append(word)
    return terms[:MAX_TERMS]


def _term_hits(text: str, terms: list[str]) -> int:
    flat = unicodedata.normalize("NFKC", text).lower()
    return sum(1 for term in terms if term in flat)


# ---- vectors ----


def split_embeddable(
    pending: list[tuple[uuid.UUID, str]], limits: Limits
) -> tuple[list[tuple[uuid.UUID, str]], int]:
    """(the chunks small enough to embed, how many are not). A big chunk is never cut."""
    cap = limits.embed_chunk_max_tokens
    fits = [item for item in pending if estimate_embed_tokens([item[1]]) <= cap]
    return fits, len(pending) - len(fits)


def pending_chunks(
    db: Session, run_id: uuid.UUID, user_id: uuid.UUID, model: str
) -> list[tuple[uuid.UUID, str]]:
    """Chunks of the run's documents with no vector, or one made by another model."""
    rows = db.execute(
        select(Chunk.id, Chunk.text)
        .where(
            Chunk.upload_id.in_(_own_uploads(run_id, user_id)),
            Chunk.owner_id == user_id,
            (Chunk.embedding.is_(None)) | (Chunk.embedding_model != model),
        )
        .order_by(Chunk.upload_id, Chunk.ord)
    ).all()
    return [(r[0], r[1]) for r in rows]


def store_vectors(
    db: Session,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    model: str,
    pairs: list[tuple[uuid.UUID, list[float]]],
) -> None:
    """Write the vectors of chunks the run owns and commit. Any other chunk id changes nothing."""
    table = Chunk.__table__
    assert isinstance(table, Table)  # noqa: S101  # narrows the type for mypy
    statement = (
        update(table)
        .where(
            table.c.id == bindparam("b_id"),
            table.c.owner_id == user_id,
            table.c.upload_id.in_(_own_uploads(run_id, user_id)),
        )
        .values(embedding=bindparam("b_vec", type_=Vector(EMBEDDING_DIM)), embedding_model=model)
    )
    db.execute(statement, [{"b_id": cid, "b_vec": vec} for cid, vec in pairs])
    db.commit()


def _vector_hits(
    db: Session, run_id: uuid.UUID, user_id: uuid.UUID, model: str, query: list[float], k: int
) -> list[tuple[uuid.UUID, float]]:
    """(chunk id, cosine similarity) of the k nearest chunks made by `model`, best first."""
    distance = Chunk.embedding.cosine_distance(query)
    rows = db.execute(
        select(Chunk.id, distance)
        .where(
            Chunk.upload_id.in_(_own_uploads(run_id, user_id)),
            Chunk.owner_id == user_id,
            Chunk.embedding.is_not(None),
            Chunk.embedding_model == model,
        )
        .order_by(distance, Chunk.ord)
        .limit(k)
    ).all()
    return [(r[0], 1.0 - float(r[1])) for r in rows]


def _text_hits(
    db: Session, run_id: uuid.UUID, user_id: uuid.UUID, terms: list[str], k: int
) -> list[tuple[uuid.UUID, str]]:
    """(chunk id, text) of the k best chunks by full-text rank. Each term also matches longer
    words that start with it (rider -> riders, 서울역 -> 서울역에서)."""
    if not terms:
        return []
    # Terms hold letters and digits only (see query_terms), so quoting them is enough.
    tsquery = func.to_tsquery("simple", " | ".join(f"'{term}':*" for term in terms))
    rank = func.ts_rank_cd(Chunk.tsv, tsquery)
    rows = db.execute(
        select(Chunk.id, Chunk.text)
        .where(
            Chunk.upload_id.in_(_own_uploads(run_id, user_id)),
            Chunk.owner_id == user_id,
            Chunk.tsv.op("@@")(tsquery),
        )
        .order_by(rank.desc(), Chunk.ord)
        .limit(k)
    ).all()
    return [(r[0], r[1]) for r in rows]


def fuse(
    vector_ids: list[uuid.UUID], text_ids: list[uuid.UUID], rrf_k: int
) -> list[tuple[uuid.UUID, float]]:
    """Reciprocal rank fusion of two best-first lists. The score is relative to the best possible
    one (first in both lists), so it runs from 0 to 1. Ties keep the vector list's order."""
    best = 2.0 / (rrf_k + 1)
    scores: dict[uuid.UUID, float] = {}
    for ids in (vector_ids, text_ids):
        for rank, chunk_id in enumerate(ids, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    order = {cid: i for i, cid in enumerate([*vector_ids, *text_ids])}
    ranked = sorted(scores.items(), key=lambda item: (-item[1], order[item[0]]))
    return [(cid, round(min(1.0, score / best), 3)) for cid, score in ranked]


def _fetch(
    db: Session,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    scored: list[tuple[uuid.UUID, float]],
    cosines: dict[uuid.UUID, float],
) -> list[Passage]:
    if not scored:
        return []
    rows = db.execute(
        select(Chunk.id, Chunk.upload_id, Chunk.page, Chunk.ord, Chunk.text).where(
            Chunk.id.in_([cid for cid, _ in scored]),
            Chunk.owner_id == user_id,
            Chunk.upload_id.in_(_own_uploads(run_id, user_id)),
        )
    ).all()
    by_id = {r[0]: r for r in rows}
    return [
        Passage(
            cid, by_id[cid][1], by_id[cid][2], by_id[cid][3], by_id[cid][4], score, cosines.get(cid)
        )
        for cid, score in scored
        if cid in by_id
    ]


# ---- the search ----


@dataclass(frozen=True)
class EmbedProgress:
    tokens: int = 0  # embedding tokens this pass used
    stopped: GatewayError | None = None  # the gateway error that stopped it
    over_budget: bool = False  # the document needs more than the run's embedding budget
    skipped: int = 0  # chunks too big for the embedding model, left to the word search


def _embed_chunks(
    session_factory: SessionFactory,
    embedder: Embedder,
    *,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    model: str,
    limits: Limits,
    now: Clock,
    deadline: float,
) -> EmbedProgress:
    """Embed the chunks that have no vector yet, EMBED_GROUP at a time, storing each group at once.
    A chunk over embed_chunk_max_tokens is skipped (never cut). Stops before the run's embedding
    budget is passed or its deadline is reached."""
    with session_factory() as db:
        every = pending_chunks(db, run_id, user_id, model)
        used = store.run_embed_tokens(db, run_id)
    pending, skipped = split_embeddable(every, limits)
    if not pending:
        return EmbedProgress(skipped=skipped)
    need = estimate_embed_tokens([text for _, text in pending])
    if used + need > limits.max_embed_tokens_per_run:
        return EmbedProgress(over_budget=True, skipped=skipped)  # words only, nothing spent
    tokens = 0
    for first in range(0, len(pending), EMBED_GROUP):
        if now() >= deadline:
            return EmbedProgress(tokens, skipped=skipped)
        group = pending[first : first + EMBED_GROUP]
        done = embedder.embed(
            [text for _, text in group], task=EmbedTask.DOCUMENT, user_id=user_id, run_id=run_id
        )
        if isinstance(done, GatewayError):
            return EmbedProgress(tokens, done, skipped=skipped)
        tokens += done.tokens_in
        with session_factory() as db:
            store_vectors(
                db,
                run_id,
                user_id,
                model,
                [(cid, vec) for (cid, _), vec in zip(group, done.vectors, strict=True)],
            )
    return EmbedProgress(tokens, skipped=skipped)


def search(
    session_factory: SessionFactory,
    embedder: Embedder,
    *,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    question: str,
    model: str | None,
    limits: Limits,
    now: Clock,
    deadline: float,
) -> SearchOutcome:
    """The passages that answer `question` in the run's own PDF, best first (at most
    retrieval_keep). `model` is the configured embedding model, or None when there is none (then
    the search is by words only)."""
    terms = query_terms(question)
    vector_hits: list[tuple[uuid.UUID, float]] = []
    cosines: dict[uuid.UUID, float] = {}  # every hit, before the floor
    tokens = 0
    mode: Literal["hybrid", "keyword"] = "keyword"
    size_limited = False
    skipped = 0
    if model is not None:
        progress = _embed_chunks(
            session_factory, embedder, run_id=run_id, user_id=user_id, model=model,
            limits=limits, now=now, deadline=deadline,
        )  # fmt: skip
        tokens += progress.tokens
        skipped = progress.skipped
        stopped = progress.stopped
        if stopped is not None and stopped.cap_scope is not None:
            return SearchOutcome([], "keyword", tokens, cap=stopped, skipped_chunks=skipped)
        with session_factory() as db:
            left, _ = split_embeddable(pending_chunks(db, run_id, user_id, model), limits)
            pending_left = bool(left)
            used = store.run_embed_tokens(db, run_id)
        query_cost = estimate_embed_tokens([question])
        question_fits = used + query_cost <= limits.max_embed_tokens_per_run
        size_limited = progress.over_budget or (not pending_left and not question_fits)
        if not pending_left and question_fits:
            asked = embedder.embed([question], task=EmbedTask.QUERY, user_id=user_id, run_id=run_id)
            if isinstance(asked, GatewayError):
                if asked.cap_scope is not None:
                    return SearchOutcome([], "keyword", tokens, cap=asked, skipped_chunks=skipped)
            else:
                tokens += asked.tokens_in
                with session_factory() as db:
                    hits = _vector_hits(
                        db, run_id, user_id, model, asked.vectors[0], limits.retrieval_vector_k
                    )
                cosines = {cid: round(sim, 4) for cid, sim in hits}
                vector_hits = [h for h in hits if h[1] >= limits.retrieval_min_similarity]
                mode = "hybrid"
    with session_factory() as db:
        text_rows = _text_hits(db, run_id, user_id, terms, limits.retrieval_text_k)
    need = min(limits.retrieval_min_terms, len(terms))
    text_ids = [cid for cid, text in text_rows if _term_hits(text, terms) >= need]
    fused = fuse([cid for cid, _ in vector_hits], text_ids, limits.retrieval_rrf_k)
    with session_factory() as db:
        passages = _fetch(db, run_id, user_id, fused[: limits.retrieval_keep], cosines)
    top = max(cosines.values()) if cosines else None
    return SearchOutcome(
        passages, mode, tokens, top_cosine=top, size_limited=size_limited, skipped_chunks=skipped
    )
