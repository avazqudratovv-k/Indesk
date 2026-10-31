"""A size said in words ("about a million more") in the report text or a claim (P14b), on the CSV
and the PDF path. The sentence is dropped or the claim is not verified, and the run payload keeps
only a counter and a reason code. Fake client only."""

import json
from typing import Any

import pytest
from sqlalchemy import Connection

from app.ai.caps import SessionFactory
from app.core.enums import ClaimStatus, ReportReason
from app.runs.ask_schemas import BeaverPayload, ComputedResult
from app.runs.cat_pdf_report import build_pdf_report
from app.runs.cat_report import build_report
from app.runs.cat_schemas import CatPayload, ClaimsOut, PdfClaimsOut, payload_with_quantity
from app.runs.executor import run_job
from app.runs.numbers import QUANTITY_REASON
from tests.ai_helpers import factory_for
from tests.pdf_run_helpers import GOOD_QUOTE, make_pdf_world, pdf_rig, writer_answer
from tests.runs_helpers import run_row, step_rows

SENTENCE = "Weekdays carry about a million more boardings than weekends."


@pytest.fixture
def factory(db_connection: Connection) -> SessionFactory:
    return factory_for(db_connection)


# ---- CSV ----

RESULT = ComputedResult(
    columns=["day_type", "mean_daily_boardings"],
    rows=[["Weekday", 3045814.32], ["Weekend", 2000000.5]],
    rows_used=30,
)


def csv_report(
    question: str = "Compare weekdays and weekends",
    *,
    claim: str = "Weekday boardings averaged 3,045,814.",
    **fields: Any,
) -> Any:
    from app.runs.cat_checks import ResultView  # noqa: PLC0415

    view = ResultView.of(RESULT, 30)
    out = ClaimsOut.model_validate(
        {
            "title": "Weekdays lead",
            "answer": "Weekday boardings are higher.",
            "claim_texts": [claim],
            "claim_cells": ["r1c2"],
            "meaning": "",
            "next_steps": [],
            **fields,
        }
    )
    beaver = BeaverPayload(
        owl_prompt_version="owl-2", beaver_prompt_version="beaver-2", attempt=1, method="rank",
        row_count=30, rows_used=30, result=RESULT, code="x = 1",
    )  # fmt: skip
    built = build_report(out, view, beaver, question)
    assert built is not None
    return built[0]


def test_csv_a_size_in_words_drops_the_meaning_sentence() -> None:
    draft = csv_report(meaning=SENTENCE)
    assert draft.summary.meaning is None
    assert (draft.quantity_dropped, draft.quantity_demoted) == (1, 0)
    assert draft.claims[0].status is ClaimStatus.VERIFIED  # the claim itself was fine


def test_csv_the_same_sentence_stays_when_the_question_says_it() -> None:
    draft = csv_report("Is it about a million more on weekdays?", meaning=SENTENCE)
    assert draft.summary.meaning == SENTENCE
    assert draft.quantity_dropped == 0


@pytest.mark.parametrize(
    "meaning",
    ["Weekdays average 3.05 million boardings.", "Weekdays average 3,045,814 boardings."],
)
def test_csv_written_numbers_still_pass(meaning: str) -> None:
    draft = csv_report(meaning=meaning)
    assert draft.summary.meaning == meaning
    assert draft.quantity_dropped == 0


def test_csv_a_number_from_the_question_still_passes() -> None:
    draft = csv_report("Do weekdays beat 1,000,000 boardings?", meaning="Weekdays beat 1,000,000.")
    assert draft.summary.meaning == "Weekdays beat 1,000,000."


def test_csv_title_and_answer_are_dropped_too_and_fall_back() -> None:
    draft = csv_report(title="A million more riders", answer="About a million more on weekdays.")
    assert draft.title == "Compare weekdays and weekends"  # the question
    assert (
        draft.summary.answer == "Weekday boardings averaged 3,045,814."
    )  # the first verified claim
    assert draft.quantity_dropped == 2


def test_csv_a_claim_with_an_unsupported_size_is_not_verified() -> None:
    draft = csv_report(claim="Weekday boardings averaged 3,045,814, about twice the weekend.")
    (claim,) = draft.claims
    assert claim.status is ClaimStatus.UNVERIFIED
    assert (draft.quantity_demoted, draft.verified_count) == (1, 0)
    note = next(e for e in draft.evidence if e.type == "critic_note")
    assert note.payload.reason is ReportReason.NUMBER_MISMATCH


def test_csv_the_claim_is_verified_when_the_question_says_the_word() -> None:
    draft = csv_report(
        "Are weekdays twice the weekend?",
        claim="Weekday boardings averaged 3,045,814, about twice the weekend.",
    )
    assert draft.claims[0].status is ClaimStatus.VERIFIED
    assert draft.quantity_demoted == 0


def test_csv_a_next_step_with_a_size_in_words_is_dropped_and_counted() -> None:
    draft = csv_report(next_steps=["Plan for hundreds of extra trains.", "Ask for next month."])
    assert draft.summary.next_steps == ["Ask for next month."]
    assert draft.quantity_dropped == 1


def test_csv_korean_sentence_is_dropped_and_a_plain_word_is_not() -> None:
    dropped = csv_report(meaning="평일이 주말보다 약 백만 명 더 많다.")
    assert dropped.summary.meaning is None
    kept = csv_report(meaning="기억에 남는 조건은 평일이 더 많다는 점이다.")
    assert kept.summary.meaning is not None


# ---- PDF ----

PAGES = {
    1: "The network carried about a million more riders on weekdays than on weekends in 2025. "
    "Station Alpha reported 2.45 million boardings and 1,000,000 transfers last year.",
    2: GOOD_QUOTE + ", the largest ridership rise of any station in the network.",
}
QUOTE_MILLION = "carried about a million more riders on weekdays than on weekends"
QUOTE_DIGITS = "Station Alpha reported 2.45 million boardings and 1,000,000 transfers"


def pdf_report(
    quote: str = GOOD_QUOTE,
    page: int = 2,
    claim: str = "Hapjeong station rose 18 percent between 2019 and 2025.",
    question: str = "Which station rose?",
    **fields: Any,
) -> Any:
    out = PdfClaimsOut.model_validate(
        {
            "found": True,
            "title": "Report",
            "answer": "Hapjeong rose the most.",
            "claim_texts": [claim],
            "claim_quotes": [quote],
            "claim_pages": [page],
            "claim_values": [""],
            "meaning": "",
            "next_steps": [],
            **fields,
        }
    )
    built = build_pdf_report(out, PAGES, 2, question)
    assert built is not None
    return built[0]


def test_pdf_a_size_in_words_drops_the_meaning_sentence() -> None:
    draft = pdf_report(meaning=SENTENCE)
    assert draft.summary.meaning is None
    assert (draft.quantity_dropped, draft.quantity_demoted) == (1, 0)


def test_pdf_the_sentence_is_kept_when_a_verified_quote_says_it() -> None:
    draft = pdf_report(
        QUOTE_MILLION, 1, "Weekdays carried about a million more riders.", meaning=SENTENCE
    )
    assert draft.claims[0].status is ClaimStatus.VERIFIED
    assert draft.summary.meaning == SENTENCE
    assert draft.quantity_dropped == 0


def test_pdf_a_quote_that_did_not_verify_does_not_license_the_sentence() -> None:
    # The quote says "million", but the claim is demoted by another rule (page 2 is cited).
    draft = pdf_report(QUOTE_MILLION, 2, "Weekdays carried about a million more.", meaning=SENTENCE)
    assert draft.claims[0].status is ClaimStatus.UNVERIFIED
    assert draft.summary.meaning is None


def test_pdf_written_numbers_still_pass() -> None:
    draft = pdf_report(
        QUOTE_DIGITS,
        1,
        "Station Alpha reported 2.45 million boardings.",
        meaning="Alpha had 2.45 million boardings and 1,000,000 transfers.",
    )
    assert draft.claims[0].status is ClaimStatus.VERIFIED
    assert draft.summary.meaning == "Alpha had 2.45 million boardings and 1,000,000 transfers."
    assert draft.quantity_dropped == 0


def test_pdf_a_claim_with_a_size_the_quote_does_not_say_is_number_not_in_quote() -> None:
    draft = pdf_report(claim="Hapjeong station rose 18 percent, about a million more trips.")
    (claim,) = draft.claims
    assert claim.status is ClaimStatus.UNVERIFIED
    assert draft.quantity_demoted == 1
    note = next(e for e in draft.evidence if e.type == "critic_note")
    assert note.payload.reason is ReportReason.NUMBER_NOT_IN_QUOTE


def test_pdf_the_claim_is_verified_when_its_quote_says_the_word() -> None:
    draft = pdf_report(QUOTE_MILLION, 1, "Weekdays carried about a million more riders.")
    assert draft.claims[0].status is ClaimStatus.VERIFIED


# ---- the run payload: a counter and a code, never text ----


def test_the_payload_holds_counters_and_a_code_only() -> None:
    draft = csv_report(meaning=SENTENCE)
    payload = payload_with_quantity(
        CatPayload(prompt_version="x", rows_mismatch=False, verdicts=[]), draft
    )
    assert (payload.quantity_dropped, payload.quantity_demoted) == (1, 0)
    assert payload.quantity_reason == QUANTITY_REASON
    assert "million" not in payload.model_dump_json()


def test_a_clean_report_leaves_the_payload_as_it_was() -> None:
    payload = CatPayload(prompt_version="x", rows_mismatch=False, verdicts=[])
    assert payload_with_quantity(payload, csv_report()) == payload


def test_pdf_run_stores_a_counter_and_no_text(factory: SessionFactory) -> None:
    world = make_pdf_world(factory)
    answer = writer_answer([GOOD_QUOTE], [2], meaning=SENTENCE)
    rig, _ = pdf_rig(factory, world, answer)
    run_job(world.run_id, rig.deps)
    assert run_row(factory, world.run_id).outcome == "answered"
    verify = [s for s in step_rows(factory, world.run_id) if s.key == "verify"][-1]
    assert verify.payload is not None
    assert verify.payload["quantity_dropped"] == 1
    assert verify.payload["quantity_reason"] == QUANTITY_REASON
    assert "million" not in json.dumps(verify.payload)
