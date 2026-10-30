"""Chunk size against the embedding model's input cap, and the visible keyword-only fallback
(P14b). Fake client only; the 8,192-token cap is Google's model page, not measured here."""

import pytest
from pydantic import ValidationError
from sqlalchemy import Connection, select

from app.ai.caps import SessionFactory
from app.ai.client import estimate_embed_tokens, estimate_tokens
from app.core.config import MAX_CHUNK_CHARS, MAX_EMBED_CHUNK_TOKENS, Limits, load_limits
from app.db.models import Chunk
from app.runs.executor import run_job
from tests.ai_helpers import factory_for
from tests.fake_model_client import server_error
from tests.pdf_run_helpers import GOOD_QUOTE, PAGES, make_pdf_world, pdf_rig, writer_answer
from tests.runs_helpers import World, run_row, step_rows


@pytest.fixture
def factory(db_connection: Connection) -> SessionFactory:
    return factory_for(db_connection)


def keys(factory: SessionFactory, run_id: object) -> list[str]:
    return [s.key for s in step_rows(factory, run_id)]  # type: ignore[arg-type]


# ---- the startup check ----


def test_the_shipped_chunk_size_is_under_the_ceiling() -> None:
    limits = load_limits()
    assert limits.chunk_chars <= MAX_CHUNK_CHARS == 3000
    assert limits.embed_chunk_max_tokens <= MAX_EMBED_CHUNK_TOKENS == 6000


def test_a_chunk_size_over_3000_stops_the_server_at_startup() -> None:
    base = load_limits().model_dump()
    Limits.model_validate({**base, "chunk_chars": 3000})
    with pytest.raises(ValidationError, match="chunk_chars must be at most 3000"):
        Limits.model_validate({**base, "chunk_chars": 3001})


def test_the_token_guard_cannot_be_set_above_6000() -> None:
    base = load_limits().model_dump()
    Limits.model_validate({**base, "embed_chunk_max_tokens": 6000})
    with pytest.raises(ValidationError, match="embed_chunk_max_tokens"):
        Limits.model_validate({**base, "embed_chunk_max_tokens": 6001})


# ---- the estimate ----


def test_the_embedding_estimate_follows_the_measured_ratios() -> None:
    assert estimate_embed_tokens(["a" * 1000]) == 375  # 0.375 a character (measured 0.36)
    assert estimate_embed_tokens(["가" * 1000]) == 1150  # 1.15 a character (measured about 1.1)
    assert estimate_embed_tokens(["a" * 8, "가" * 20]) == 3 + 23
    assert estimate_embed_tokens([]) == 0


def test_the_old_estimate_is_untouched() -> None:
    assert estimate_tokens(["abcd" * 10]) == 10
    assert estimate_tokens(["가" * 10]) == 10


def test_a_full_chunk_of_dense_korean_is_far_under_the_model_cap() -> None:
    worst = estimate_embed_tokens(["가" * MAX_CHUNK_CHARS])
    assert worst == 3450 < MAX_EMBED_CHUNK_TOKENS < 8192


# ---- a chunk over the guard is skipped, never cut ----

KOREAN_PAGE = "서울 지하철 승차 인원은 해마다 늘었다. " * 6
KOREAN_QUOTE = "서울 지하철 승차 인원은 해마다 늘었다"
KOREAN_QUESTION = "서울 지하철 승차 인원은 어떻게 변했나?"


def test_a_chunk_over_the_token_guard_is_not_embedded_but_found_by_words(
    factory: SessionFactory,
) -> None:
    world = make_pdf_world(factory, [*PAGES, KOREAN_PAGE], question=KOREAN_QUESTION)
    answer = writer_answer(
        [KOREAN_QUOTE], [4], texts=["서울 지하철 승차 인원이 해마다 늘었다."], answer="늘었다."
    )
    rig, client = pdf_rig(factory, world, answer, embed_chunk_max_tokens=60)
    run_job(world.run_id, rig.deps)

    assert run_row(factory, world.run_id).outcome == "answered"
    # Said in the trace, with the count and nothing else.
    skipped = [s for s in step_rows(factory, world.run_id) if s.key == "chunksSkipped"]
    assert [s.args for s in skipped] == [{"count": 1}]
    with factory() as db:
        rows = list(db.scalars(select(Chunk).order_by(Chunk.ord)))
    assert [c.embedding is not None for c in rows] == [True, True, True, False]
    # Nothing was cut: every text that was sent is a whole chunk, and the big one was not sent.
    sent = [t for call in client.embed_calls if "DOCUMENT" in call.task_type for t in call.texts]
    assert sorted(sent) == sorted(c.text for c in rows[:3])
    assert not any("서울" in text for text in sent)
    # The word search still found it; the question was embedded, so the search is hybrid.
    best = next(s for s in step_rows(factory, world.run_id) if s.key == "bestPassage")
    assert best.payload is not None
    assert 4 in best.payload["pages"] and best.payload["mode"] == "hybrid"


def test_no_chunk_is_skipped_with_the_shipped_guard(factory: SessionFactory) -> None:
    world = make_pdf_world(factory)
    rig, _ = pdf_rig(factory, world, writer_answer([GOOD_QUOTE], [2]))
    run_job(world.run_id, rig.deps)
    assert "chunksSkipped" not in keys(factory, world.run_id)


# ---- the keyword-only fallback is visible ----


def test_a_document_over_the_embedding_budget_says_so_in_the_trace(
    factory: SessionFactory,
) -> None:
    world = make_pdf_world(factory)
    rig, client = pdf_rig(
        factory, world, writer_answer([GOOD_QUOTE], [2]), max_embed_tokens_per_run=5
    )  # fmt: skip
    run_job(world.run_id, rig.deps)
    assert client.embed_calls == []
    note = [s for s in step_rows(factory, world.run_id) if s.key == "keywordOnlySize"]
    assert [s.args for s in note] == [{"reason": "document_size"}]
    assert keys(factory, world.run_id).index("keywordOnlySize") < keys(factory, world.run_id).index(
        "bestPassage"
    )


def test_a_failed_embedding_is_not_called_a_size_problem(factory: SessionFactory) -> None:
    world = make_pdf_world(factory)
    rig, _ = pdf_rig(
        factory, world, writer_answer([GOOD_QUOTE], [2]),
        embed_steps=[server_error(), server_error()],
    )  # fmt: skip
    run_job(world.run_id, rig.deps)
    assert "keywordOnlySize" not in keys(factory, world.run_id)


def test_a_normal_document_has_no_such_line(factory: SessionFactory) -> None:
    world = make_pdf_world(factory)
    rig, _ = pdf_rig(factory, world, writer_answer([GOOD_QUOTE], [2]))
    run_job(world.run_id, rig.deps)
    assert "keywordOnlySize" not in keys(factory, world.run_id)


HANGUL = "가나다라마바사아자차"


def _add_korean_chunks(factory: SessionFactory, world: World, count: int) -> list[str]:
    """`count` whole 1,000-character Hangul chunks stored directly (no PDF, no chunker) beside the
    world's own chunks. Returns the text of every chunk of the upload."""
    with factory() as db, db.begin():
        db.add_all(
            Chunk(
                upload_id=world.upload_ids[0], owner_id=world.user_id, page=1, ord=1000 + n,
                char_start=0, char_end=1000, text=chr(0xAC00 + n) + HANGUL * 99 + HANGUL[:9],
            )  # fmt: skip
            for n in range(count)
        )
    with factory() as db:
        return [c.text for c in db.scalars(select(Chunk).order_by(Chunk.ord))]


def test_dense_korean_just_over_250000_tokens_goes_keyword_only_but_english_fits(
    factory: SessionFactory,
) -> None:
    """With the real 250,000 budget: dense Hangul chunks that estimate to just over 250,000 tokens
    (the same size of English is about 85,000) are searched by keywords only."""
    world = make_pdf_world(factory, PAGES)
    texts = _add_korean_chunks(factory, world, 218)
    assert estimate_embed_tokens(texts) > 250_000
    rig, client = pdf_rig(factory, world, writer_answer([GOOD_QUOTE], [2]))
    run_job(world.run_id, rig.deps)
    assert client.embed_calls == []
    assert "keywordOnlySize" in keys(factory, world.run_id)

    english = ["alpha bravo charlie delta echo " * 500] * 6  # 6 pages of 15,500 characters
    world = make_pdf_world(factory, english)
    rig, client = pdf_rig(factory, world, writer_answer([GOOD_QUOTE], [2]))
    run_job(world.run_id, rig.deps)
    assert client.embed_calls != []
    assert "keywordOnlySize" not in keys(factory, world.run_id)


def test_a_150000_character_korean_pdf_is_embedded_not_keyword_only(
    factory: SessionFactory,
) -> None:
    """The largest accepted PDF, dense Korean, chunked as the upload route chunks it (1,000
    characters, 150 overlap): about 176,000 characters of chunks, about 203,000 tokens."""
    pages = ["가나다라마바사아자차" * 1500] * 10  # 10 pages of 15,000 characters
    assert sum(len(p) for p in pages) == 150_000
    world = make_pdf_world(factory, pages)
    with factory() as db:
        texts = [c.text for c in db.scalars(select(Chunk).order_by(Chunk.ord))]
    assert 200_000 < estimate_embed_tokens(texts) <= 250_000
    rig, client = pdf_rig(factory, world, writer_answer([GOOD_QUOTE], [2]))
    run_job(world.run_id, rig.deps)
    assert client.embed_calls != []
    assert "keywordOnlySize" not in keys(factory, world.run_id)
    with factory() as db:
        assert all(c.embedding is not None for c in db.scalars(select(Chunk)))


def test_chunks_just_over_the_embedding_budget_fall_back_with_document_size(
    factory: SessionFactory,
) -> None:
    world = make_pdf_world(factory, PAGES)
    texts = _add_korean_chunks(factory, world, 218)
    total = estimate_embed_tokens(texts)
    assert 250_000 < total <= 250_000 + 2_000  # just over
    rig, client = pdf_rig(factory, world, writer_answer([GOOD_QUOTE], [2]))
    run_job(world.run_id, rig.deps)
    assert client.embed_calls == []
    note = [s for s in step_rows(factory, world.run_id) if s.key == "keywordOnlySize"]
    assert [s.args for s in note] == [{"reason": "document_size"}]
