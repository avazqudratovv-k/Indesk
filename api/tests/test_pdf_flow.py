"""A run on a PDF (P14a part 2), end to end with the fake model client: Owl (code) -> Hound ->
the writer -> Cat's checks, the report with quotes and pages, the fallbacks and the safety rules.
No network, no real Gemini."""

import uuid
from typing import Any

import pytest
from sqlalchemy import Connection, func, select

from app.ai.caps import SessionFactory
from app.core.enums import ReportReason, TraceKey
from app.db.models import Chunk, Claim, Evidence, Report
from app.runs.executor import run_job
from app.runs.trace import ALLOWED_ARGS
from tests.ai_helpers import ai_rows, factory_for
from tests.ask_helpers import NONCE
from tests.factories import make_run, make_run_file
from tests.fake_model_client import server_error
from tests.pdf_run_helpers import (
    GOOD_QUOTE,
    INJECTION,
    PAGES,
    make_pdf_world,
    pdf_rig,
    writer_answer,
)
from tests.runs_helpers import World, run_row, step_rows


@pytest.fixture
def factory(db_connection: Connection) -> SessionFactory:
    return factory_for(db_connection)


def keys(factory: SessionFactory, world: World) -> list[str]:
    return [s.key for s in step_rows(factory, world.run_id)]


def report_of(factory: SessionFactory, world: World) -> tuple[Report, list[Claim], list[Evidence]]:
    with factory() as db:
        report = db.scalar(select(Report).where(Report.run_id == world.run_id))
        assert report is not None
        claims = list(
            db.scalars(select(Claim).where(Claim.report_id == report.id).order_by(Claim.n))
        )
        evidence = list(
            db.scalars(
                select(Evidence).where(Evidence.run_id == world.run_id).order_by(Evidence.ref)
            )
        )
        db.expunge_all()
        return report, claims, evidence


# ---- the good run ----


def test_a_pdf_run_ends_in_a_report_with_quotes_and_pages(factory: SessionFactory) -> None:
    world = make_pdf_world(factory)
    rig, client = pdf_rig(factory, world, writer_answer([GOOD_QUOTE], [2], values=["18 percent"]))
    run_job(world.run_id, rig.deps)

    run = run_row(factory, world.run_id)
    assert (run.status, run.outcome, run.outcome_reason, run.counted) == (
        "finished", "answered", None, True,
    )  # fmt: skip
    assert keys(factory, world) == [
        "plan", "dispatch", "search", "bestPassage", "verify", "verify", "ready",
    ]  # fmt: skip
    report, claims, evidence = report_of(factory, world)
    assert (report.verified_count, report.total_claims, report.confidence) == (1, 1, "high")
    (claim,) = claims
    assert (claim.status, claim.origin) == ("verified", "document")
    assert (claim.doc_quote, claim.doc_location, claim.doc_value) == (
        GOOD_QUOTE,
        "p2",
        "18 percent",
    )
    assert claim.computed_value is None and claim.evidence_refs == ["R1"]
    (passage,) = evidence
    assert (passage.type, passage.ref, passage.location) == ("passage", "R1", "page 2")
    assert passage.payload == {"quote": GOOD_QUOTE} and passage.file_name == "report.pdf"
    # Owl made no model call; the only text-model call is the writer, on the main chain.
    assert [r.purpose for r in ai_rows(factory)] == ["embed", "embed", "extract_claims"]
    assert len(client.calls) == 1


def test_hound_trace_lines_match_the_web_mock(factory: SessionFactory) -> None:
    world = make_pdf_world(factory)
    rig, _ = pdf_rig(factory, world, writer_answer([GOOD_QUOTE], [2]))
    run_job(world.run_id, rig.deps)
    steps = step_rows(factory, world.run_id)
    for step in steps:
        assert set(step.args) <= ALLOWED_ARGS[TraceKey(step.key)]
    search = next(s for s in steps if s.key == "search")
    assert (search.agent, search.kind, search.state) == ("retrieval", "tool", "running")
    assert search.args == {"pages": 3}
    best = next(s for s in steps if s.key == "bestPassage")
    assert (best.agent, best.kind, best.state) == ("retrieval", "say", "done")
    assert best.args["page"] == 2 and 0 < best.args["score"] <= 1
    assert best.payload is not None and best.payload["mode"] == "hybrid"
    assert "text" not in best.payload and best.payload["matched"] >= 1


def test_the_last_trace_line_of_every_agent_is_legal_and_owl_made_no_call(
    factory: SessionFactory,
) -> None:
    world = make_pdf_world(factory)
    rig, client = pdf_rig(factory, world, writer_answer([GOOD_QUOTE], [2]))
    run_job(world.run_id, rig.deps)
    assert all(c.max_output_tokens == 8192 for c in client.calls)  # main chain only
    assert {r.purpose for r in ai_rows(factory)} <= {"embed", "extract_claims"}


# ---- no passages ----


def test_no_passage_means_not_answerable_and_no_writer_call(factory: SessionFactory) -> None:
    world = make_pdf_world(factory, question="Quarterly revenue of the zebra division?")
    rig, client = pdf_rig(factory, world, retrieval_min_similarity=0.95)
    run_job(world.run_id, rig.deps)
    run = run_row(factory, world.run_id)
    assert (run.status, run.outcome, run.counted) == ("finished", "not_answerable", False)
    assert client.calls == []  # no writer call
    assert keys(factory, world) == [
        "plan",
        "dispatch",
        "search",
        "search",
        "verify",
        "verify",
        "ready",
    ]
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Report)) == 0


# ---- the embedding fails ----


def test_a_failed_embedding_falls_back_to_keywords(factory: SessionFactory) -> None:
    world = make_pdf_world(factory)
    rig, client = pdf_rig(
        factory, world, writer_answer([GOOD_QUOTE], [2]),
        embed_steps=[server_error(), server_error()],
    )  # fmt: skip
    run_job(world.run_id, rig.deps)
    run = run_row(factory, world.run_id)
    assert (run.status, run.outcome) == ("finished", "answered")
    best = next(s for s in step_rows(factory, world.run_id) if s.key == "bestPassage")
    assert best.payload is not None and best.payload["mode"] == "keyword"
    with factory() as db:  # nothing half-stored
        assert (
            db.scalar(select(func.count()).select_from(Chunk).where(Chunk.embedding.is_not(None)))
            == 0
        )
    assert [r.status for r in ai_rows(factory) if r.purpose == "embed"] == ["error", "error"]


def test_the_embedding_budget_keeps_a_big_document_to_keywords(factory: SessionFactory) -> None:
    world = make_pdf_world(factory)
    rig, client = pdf_rig(
        factory, world, writer_answer([GOOD_QUOTE], [2]), max_embed_tokens_per_run=5
    )  # fmt: skip
    run_job(world.run_id, rig.deps)
    assert run_row(factory, world.run_id).outcome == "answered"
    assert client.embed_calls == []  # nothing was spent
    best = next(s for s in step_rows(factory, world.run_id) if s.key == "bestPassage")
    assert best.payload is not None and best.payload["mode"] == "keyword"


def test_embedding_tokens_do_not_use_the_run_token_budget(factory: SessionFactory) -> None:
    world = make_pdf_world(factory)
    rig, client = pdf_rig(
        factory, world, writer_answer([GOOD_QUOTE], [2]), max_tokens_per_run=20
    )  # fmt: skip
    run_job(world.run_id, rig.deps)  # the writer uses 15 tokens; the embeddings use many more
    assert run_row(factory, world.run_id).outcome == "answered"
    assert sum(r.tokens_in for r in ai_rows(factory) if r.purpose == "embed") > 20


def test_a_daily_cap_on_the_embedding_rejects_the_run(factory: SessionFactory) -> None:
    world = make_pdf_world(factory)
    rig, client = pdf_rig(factory, world, writer_answer([GOOD_QUOTE], [2]), daily_calls_per_user=1)
    run_job(world.run_id, rig.deps)
    run = run_row(factory, world.run_id)
    # The document embedding took the one slot; the query embedding was refused.
    assert (run.outcome, run.outcome_reason) == ("rejected", "daily_cap_user")
    assert client.calls == []


# ---- the writer's quote is checked in code ----


@pytest.mark.parametrize(
    ("quote", "page", "text", "reason"),
    [
        ("Hapjeong station fell 18 percent between 2019 and 2025", 2, None, "quote_not_found"),
        (GOOD_QUOTE, 3, None, "page_mismatch"),
        (GOOD_QUOTE, 9, None, "bad_page"),
        (GOOD_QUOTE, 0, None, "bad_page"),
        ("Hapjeong", 2, None, "quote_too_short"),
        ("", 2, None, "no_quote"),
        (" ... ... ", 2, None, "no_quote"),
        (GOOD_QUOTE, 2, "Hapjeong station rose 19 percent.", "number_not_in_quote"),
    ],
    ids=["not-found", "page-mismatch", "page-too-high", "page-zero", "too-short", "empty",
         "only-ellipses", "number-not-in-quote"],
)  # fmt: skip
def test_a_bad_quote_leaves_the_claim_unverified_with_a_reason(
    factory: SessionFactory, quote: str, page: int, text: str | None, reason: str
) -> None:
    world = make_pdf_world(factory)
    answer = writer_answer([quote], [page], texts=[text] if text else None)
    rig, _ = pdf_rig(factory, world, answer)
    run_job(world.run_id, rig.deps)
    run = run_row(factory, world.run_id)
    assert (run.outcome, run.counted) == ("partial", True)
    report, (claim,), evidence = report_of(factory, world)
    assert (claim.status, report.verified_count, report.confidence) == ("unverified", 0, "low")
    notes = [e for e in evidence if e.type == "critic_note"]
    assert [n.payload["reason"] for n in notes] == [ReportReason(reason).value]
    shown = reason == "number_not_in_quote"  # only a quote that IS on the page is shown
    assert (claim.doc_quote is not None) is shown
    assert any(e.type == "passage" for e in evidence) is shown


def test_ellipsis_segments_must_come_in_order(factory: SessionFactory) -> None:
    quotes = [
        "Hapjeong station rose 18 percent ... the largest ridership rise of any station",
        "the largest ridership rise of any station ... Hapjeong station rose 18 percent",
    ]
    world = make_pdf_world(factory)
    answer = writer_answer(
        quotes, [2, 2], texts=["Hapjeong rose 18 percent.", "It rose 18 percent."]
    )
    rig, _ = pdf_rig(factory, world, answer)
    run_job(world.run_id, rig.deps)
    _, claims, _ = report_of(factory, world)
    assert [c.status for c in claims] == ["verified", "unverified"]


def test_one_good_and_one_bad_claim_give_a_partial_report(factory: SessionFactory) -> None:
    world = make_pdf_world(factory)
    answer = writer_answer([GOOD_QUOTE, GOOD_QUOTE], [2, 3])
    rig, _ = pdf_rig(factory, world, answer)
    run_job(world.run_id, rig.deps)
    report, claims, _ = report_of(factory, world)
    assert [c.status for c in claims] == ["verified", "unverified"]
    assert (run_row(factory, world.run_id).outcome, report.confidence) == ("partial", "medium")


def test_a_number_in_the_summary_that_is_in_no_quote_is_dropped(factory: SessionFactory) -> None:
    world = make_pdf_world(factory)
    answer = writer_answer([GOOD_QUOTE], [2], answer="Hapjeong rose 99 percent.")
    rig, _ = pdf_rig(factory, world, answer)
    run_job(world.run_id, rig.deps)
    report, claims, _ = report_of(factory, world)
    assert "99" not in report.summary_json["answer"]
    assert report.summary_json["answer"] == claims[0].text


def test_an_unusable_writer_answer_fails_the_run_without_a_report(factory: SessionFactory) -> None:
    world = make_pdf_world(factory)
    answer = writer_answer([GOOD_QUOTE], [2], claim_texts=["<b></b>"])
    rig, _ = pdf_rig(factory, world, answer)
    run_job(world.run_id, rig.deps)
    run = run_row(factory, world.run_id)
    assert (run.outcome, run.outcome_reason) == ("failed", "bad_model_output")


# ---- vectors are reused ----


def test_a_second_question_on_the_same_upload_embeds_only_the_question(
    factory: SessionFactory,
) -> None:
    world = make_pdf_world(factory)
    rig, client = pdf_rig(
        factory, world, writer_answer([GOOD_QUOTE], [2]), writer_answer([GOOD_QUOTE], [2])
    )
    run_job(world.run_id, rig.deps)
    first = [(c.task_type, len(c.texts)) for c in client.embed_calls]
    assert first == [("RETRIEVAL_DOCUMENT", 3), ("RETRIEVAL_QUERY", 1)]

    with factory() as db, db.begin():
        from app.db.models import Run, Upload, User  # noqa: PLC0415

        old = db.get(Run, world.run_id)
        assert old is not None
        upload = db.get(Upload, world.upload_ids[0])
        owner = db.get(User, world.user_id)
        assert upload is not None and owner is not None
        run2 = make_run(db, owner, question="Which station rose the most in ridership?")
        make_run_file(db, run2, upload, role="subject")
        second_id = run2.id
    client.embed_calls.clear()
    run_job(second_id, rig.deps)
    assert [(c.task_type, len(c.texts)) for c in client.embed_calls] == [("RETRIEVAL_QUERY", 1)]
    assert run_row(factory, second_id).outcome == "answered"


def test_a_vector_made_by_another_model_is_made_again(factory: SessionFactory) -> None:
    world = make_pdf_world(factory)
    rig, client = pdf_rig(factory, world, writer_answer([GOOD_QUOTE], [2]))
    with factory() as db, db.begin():
        for chunk in db.scalars(select(Chunk)):
            chunk.embedding = [0.1] * 768
            chunk.embedding_model = "an-older-model"
    run_job(world.run_id, rig.deps)
    assert client.embed_calls[0].task_type == "RETRIEVAL_DOCUMENT"
    with factory() as db:
        models = set(db.scalars(select(Chunk.embedding_model)))
    assert models == {"gemini-embedding-2"}


# ---- other people's chunks ----


def test_another_users_chunks_are_never_read_or_written(factory: SessionFactory) -> None:
    mine = make_pdf_world(factory)
    theirs = make_pdf_world(factory)  # the same text, another user
    rig, client = pdf_rig(factory, mine, writer_answer([GOOD_QUOTE], [2]))
    run_job(mine.run_id, rig.deps)
    assert run_row(factory, mine.run_id).outcome == "answered"
    with factory() as db:
        theirs_rows = list(db.scalars(select(Chunk).where(Chunk.upload_id == theirs.upload_ids[0])))
        mine_rows = list(db.scalars(select(Chunk).where(Chunk.upload_id == mine.upload_ids[0])))
    assert theirs_rows and all(c.embedding is None for c in theirs_rows)
    assert all(c.embedding is not None for c in mine_rows)
    # Only my chunks were sent to the model.
    sent = {t for call in client.embed_calls for t in call.texts}
    assert {c.text for c in mine_rows} <= sent


def test_the_search_ignores_uploads_that_are_not_attached_to_the_run(
    factory: SessionFactory,
) -> None:
    from app.services import retrieval  # noqa: PLC0415

    mine = make_pdf_world(factory)
    theirs = make_pdf_world(factory)
    rig, client = pdf_rig(factory, mine)
    found = retrieval.search(
        factory, rig.deps.gateway, run_id=mine.run_id, user_id=mine.user_id,
        question="Hapjeong station ridership", model="gemini-embedding-2",
        limits=rig.deps.limits, now=lambda: 0.0, deadline=1e9,
    )  # fmt: skip
    assert found.passages and {p.upload_id for p in found.passages} == {mine.upload_ids[0]}
    # Asking with the other user's id against my run finds nothing at all.
    stolen = retrieval.search(
        factory, rig.deps.gateway, run_id=mine.run_id, user_id=theirs.user_id,
        question="Hapjeong station ridership", model=None,
        limits=rig.deps.limits, now=lambda: 0.0, deadline=1e9,
    )  # fmt: skip
    assert stolen.passages == []
    with factory() as db:
        assert retrieval.load_pages(db, mine.run_id, theirs.user_id, mine.upload_ids[0]) == {}
        assert retrieval.load_pages(db, mine.run_id, mine.user_id, theirs.upload_ids[0]) == {}
        assert len(retrieval.load_pages(db, mine.run_id, mine.user_id, mine.upload_ids[0])) == 3


# ---- prompt injection ----

INJECTED = [PAGES[0], PAGES[1] + " " + INJECTION, PAGES[2]]


def test_pdf_text_is_only_inside_the_nonce_fence(factory: SessionFactory) -> None:
    world = make_pdf_world(factory, INJECTED)
    rig, client = pdf_rig(factory, world, writer_answer([GOOD_QUOTE], [2]))
    run_job(world.run_id, rig.deps)
    prompt, system = client.prompts[0], client.systems[0]
    assert INJECTION not in system and "Hapjeong" not in system
    assert prompt.count(INJECTION) == 1
    opening, closing = f"<<<PASSAGES-{NONCE}\n", f"\nEND-PASSAGES-{NONCE}>>>"
    start, end = prompt.index(opening), prompt.index(closing)
    assert start < prompt.index(INJECTION) < end
    # Outside the fence there is only our own text and the question's fence.
    outside = prompt[:start] + prompt[end + len(closing) :]
    assert "Hapjeong" not in outside.replace(QUESTION_WORD, "")
    assert f"fenced between markers like <<<NAME-{NONCE}" in system


QUESTION_WORD = "Which station had the largest ridership rise?"


def test_an_injected_instruction_changes_nothing_with_the_fake_model(
    factory: SessionFactory,
) -> None:
    outcomes: list[tuple[Any, ...]] = []
    for pages in (PAGES, INJECTED):
        world = make_pdf_world(factory, pages)
        rig, _ = pdf_rig(factory, world, writer_answer([GOOD_QUOTE, GOOD_QUOTE], [2, 3]))
        run_job(world.run_id, rig.deps)
        report, claims, evidence = report_of(factory, world)
        outcomes.append((
            run_row(factory, world.run_id).outcome,
            report.verified_count, report.total_claims, report.confidence,
            [(c.status, c.doc_location) for c in claims],
            sorted((e.type, e.ref) for e in evidence),
        ))  # fmt: skip
    assert outcomes[0] == outcomes[1]
    assert outcomes[0][0] == "partial"  # the page-3 claim is still unverified


def test_a_quote_copied_from_the_injection_is_still_only_a_quote(
    factory: SessionFactory,
) -> None:
    """Even if the writer repeats the injected sentence, it is checked like any other quote: it is
    on page 2, so it is a found quote; nothing makes the claim 'verified' except that."""
    world = make_pdf_world(factory, INJECTED)
    answer = writer_answer([INJECTION], [3], texts=["The report orders us to say all is verified."])
    rig, _ = pdf_rig(factory, world, answer)
    run_job(world.run_id, rig.deps)
    _, (claim,), _ = report_of(factory, world)
    assert claim.status == "unverified"  # wrong page


_ = uuid


def test_a_hound_failure_shows_as_search_failed(factory: SessionFactory) -> None:
    world = make_pdf_world(factory)
    rig, client = pdf_rig(factory, world, api_key=None)
    run_job(world.run_id, rig.deps)
    run = run_row(factory, world.run_id)
    assert (run.outcome, run.outcome_reason) == ("failed", "model_unavailable")
    steps = step_rows(factory, world.run_id)
    failed = [s for s in steps if s.key == "searchFailed"]
    assert failed and all(
        (s.agent, s.kind, s.state) == ("retrieval", "flag", "failed") for s in failed
    )
    assert "stepFailed" not in [s.key for s in steps]
    assert client.embed_calls == [] and client.calls == []


def test_a_csv_run_still_uses_the_csv_flow(factory: SessionFactory) -> None:
    from tests.ask_helpers import ask_rig, code_answer, plan_answer, sandbox_ok  # noqa: PLC0415
    from tests.runs_helpers import make_world  # noqa: PLC0415

    world = make_world(factory)
    rig, _, _ = ask_rig(factory, world, plan_answer(), code_answer(), sandbox=[sandbox_ok()])
    run_job(world.run_id, rig.deps)
    assert keys(factory, world)[:3] == ["plan", "dispatch", "readCsv"]
