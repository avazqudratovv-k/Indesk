"""Report quality (P9 follow-up): column names as words, unique row labels, thousands separators
in claim text, and the combined-total plan field. No database except the Owl flow tests; no model."""

# ruff: noqa: E501  # one assertion per line reads better than wrapped ones

from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import Connection

from app.ai.caps import SessionFactory
from app.core.enums import ClaimStatus, ReportReason, RunReason
from app.runs.ask_schemas import BeaverPayload, ComputedResult, OwlPlan
from app.runs.cat_checks import (
    ResultView,
    check_claim,
    group_thousands,
    humanize,
    plain_columns,
    tidy,
)
from app.runs.cat_report import build_report
from app.runs.cat_schemas import ClaimsOut
from app.runs.executor import run_job
from app.runs.numbers import exact_tokens
from tests.ai_helpers import factory_for
from tests.ask_helpers import PLAN, ask_rig, plan_answer
from tests.runs_helpers import make_world
from tests.test_ask_flow import failed_with


@pytest.fixture
def factory(db_connection: Connection) -> SessionFactory:
    return factory_for(db_connection)


# ---- column names as words ----


@pytest.mark.parametrize(
    ("raw", "words"),
    [
        ("mean_daily_boardings", "mean daily boardings"),
        ("days_count", "days count"),
        ("dayType", "day type"),
        ("total-boardings", "total boardings"),
        ("Line", "line"),
        ("승차총승객수", "승차총승객수"),
        ("노선_명", "노선 명"),
    ],
)
def test_a_column_name_becomes_words(raw: str, words: str) -> None:
    assert humanize(raw) == words


def test_the_writer_sees_headers_not_raw_names() -> None:
    result = ComputedResult(
        columns=["day_type", "mean_daily_boardings"], rows=[["Weekday", 3045814.32]], rows_used=30
    )
    view = ResultView.of(result, 30)
    assert view.prompt_table()["columns"] == ["day type", "mean daily boardings"]
    assert view.columns == ["day_type", "mean_daily_boardings"]  # the cleaned raw names stay


# ---- raw column names left in prose ----

WEEK = ResultView.of(
    ComputedResult(
        columns=["day_type", "mean_daily_boardings", "days_count"],
        rows=[["Weekday", 3045814.32, 22], ["Weekend", 2072052.25, 8]],
        rows_used=30,
    ),
    30,
)


def test_a_raw_column_name_in_a_claim_is_replaced_by_words() -> None:
    text = plain_columns("Weekday mean_daily_boardings was 3,045,814.32.", WEEK)
    assert text == "Weekday mean daily boardings was 3,045,814.32."
    assert plain_columns("days_count_total stays", WEEK) == "days_count_total stays"  # not a token


def test_a_korean_column_name_written_as_normal_text_is_untouched() -> None:
    seoul = ResultView.of(
        ComputedResult(columns=["노선명", "승차총승객수"], rows=[["2호선", 41527060]], rows_used=1),
        1,
    )
    text = "2호선의 승차총승객수는 41,527,060명입니다."
    assert plain_columns(text, seoul) == text


def test_a_label_that_contains_the_column_word_is_not_rewritten() -> None:
    view = ResultView.of(
        ComputedResult(
            columns=["name", "days_count"], rows=[["days_count", 22], ["x", 1]], rows_used=2
        ),
        2,
    )
    assert plain_columns("days_count had 22.", view) == "days_count had 22."


# ---- thousands separators ----


@pytest.mark.parametrize(
    ("text", "grouped"),
    [
        ("서울역 2450051명", "서울역 2,450,051명"),
        ("riders: 2450051.", "riders: 2,450,051."),
        ("mean 3045814.32 a day", "mean 3,045,814.32 a day"),
        ("on 20260901 it was", "on 20260901 it was"),  # a date
        ("in 2026 it was", "in 2026 it was"),  # a year
        ("id A2450051 and x_2450051", "id A2450051 and x_2450051"),  # next to letters
        ("v1.2450051", "v1.2450051"),  # after a decimal point
        ("2026-09-01", "2026-09-01"),
        ("already 2,450,051", "already 2,450,051"),
        ("only 999 and 12", "only 999 and 12"),
    ],
)
def test_bare_numbers_get_thousands_separators(text: str, grouped: str) -> None:
    assert group_thousands(text, set()) == grouped


def test_a_number_from_the_question_or_a_label_is_not_regrouped() -> None:
    assert group_thousands("code 123456 here", exact_tokens("ticket 123456")) == "code 123456 here"


SEOUL = ResultView.of(
    ComputedResult(
        columns=["노선명", "역명", "승차총승객수"],
        rows=[["1호선", "서울역", 2450051]],
        rows_used=4079,
    ),
    4079,
)


def test_a_regrouped_number_still_verifies_and_a_wrong_one_still_fails() -> None:
    good = tidy("서울역 승차 2450051명", SEOUL, set())
    assert good == "서울역 승차 2,450,051명"
    assert check_claim(good, ["r1c3"], SEOUL, set()).status is ClaimStatus.VERIFIED
    bad = tidy("서울역 승차 2450052명", SEOUL, set())
    assert bad == "서울역 승차 2,450,052명"
    got = check_claim(bad, ["r1c3"], SEOUL, set())
    assert (got.status, got.reason) == (ClaimStatus.UNVERIFIED, ReportReason.NUMBER_MISMATCH)


# ---- unique row labels ----

LINES = ResultView.of(
    ComputedResult(
        columns=["노선명", "boardings", "alightings"],
        rows=[["2호선", 41527060, 42098204], ["7호선", 17000000, 18018664]],
        rows_used=4079,
    ),
    4079,
)


def beaver_of(view_result: ComputedResult, row_count: int) -> BeaverPayload:
    return BeaverPayload(
        owl_prompt_version="owl-2", beaver_prompt_version="beaver-2", attempt=1, method="rank",
        row_count=row_count, rows_used=view_result.rows_used, result=view_result, code="x = 1",
    )  # fmt: skip


def report_for(view: ResultView, texts: list[str], cells: list[str], question: str = "q") -> Any:
    out = ClaimsOut(
        title="t", answer="a", claim_texts=texts, claim_cells=cells, meaning="", next_steps=[]
    )
    result = ComputedResult(
        columns=view.columns, rows=view.rows, rows_used=view.rows_used, scalars={}
    )
    built = build_report(out, view, beaver_of(result, view.row_count), question)
    assert built is not None
    return built[0]


def test_two_columns_of_one_row_get_different_labels() -> None:
    draft = report_for(
        LINES,
        ["2호선 boardings were 41,527,060.", "2호선 alightings were 42,098,204."],
        ["r1c2", "r1c3"],
    )
    assert [r.label for r in draft.summary.top_rows] == ["2호선 · boardings", "2호선 · alightings"]


def test_one_number_column_labels_the_row_with_all_its_text_cells() -> None:
    draft = report_for(SEOUL, ["서울역 had 2,450,051 boardings."], ["r1c3"])
    assert [r.label for r in draft.summary.top_rows] == ["1호선 서울역"]  # no " · header"


def test_two_stations_of_one_line_do_not_share_a_label() -> None:
    view = ResultView.of(
        ComputedResult(
            columns=["노선명", "역명", "승차총승객수"],
            rows=[["2호선", "잠실", 2273958], ["2호선", "강남", 2243659]],
            rows_used=4079,
        ),
        4079,
    )
    draft = report_for(view, ["잠실 had 2,273,958.", "강남 had 2,243,659."], ["r1c3", "r2c3"])
    assert [r.label for r in draft.summary.top_rows] == ["2호선 잠실", "2호선 강남"]


def test_the_same_cell_cited_twice_gets_a_number_and_labels_stay_under_60() -> None:
    draft = report_for(
        LINES,
        ["2호선 boardings were 41,527,060.", "2호선 boardings again: 41,527,060."],
        ["r1c2", "r1c2"],
    )
    assert [r.label for r in draft.summary.top_rows] == [
        "2호선 · boardings",
        "2호선 · boardings (2)",
    ]
    long_header = ResultView.of(
        ComputedResult(columns=["name", "a" * 40, "b" * 40], rows=[["x" * 40, 1, 2]], rows_used=1),
        1,
    )
    draft = report_for(long_header, ["x" * 40 + " has 1."], ["r1c2"])
    assert len(draft.summary.top_rows[0].label) <= 60


def test_the_raw_names_in_a_claim_are_replaced_in_the_saved_report() -> None:
    draft = report_for(
        WEEK,
        ["Weekday mean_daily_boardings was 3045814.32.", "Weekday days_count was 22."],
        ["r1c2", "r1c3"],
    )
    assert [c.text for c in draft.claims] == [
        "Weekday mean daily boardings was 3,045,814.32.",
        "Weekday days count was 22.",
    ]
    assert [r.label for r in draft.summary.top_rows] == [
        "Weekday · mean daily boardings", "Weekday · days count",
    ]  # fmt: skip
    assert draft.evidence[0].payload.table is not None
    assert draft.evidence[0].payload.table.headers == [
        "day type",
        "mean daily boardings",
        "days count",
    ]


# ---- the combined-total plan field ----


def plan(**over: Any) -> dict[str, Any]:
    return {**PLAN, **over}


def test_add_metrics_defaults_to_empty_and_counts_as_named_columns() -> None:
    assert OwlPlan.model_validate(PLAN).add_metrics == []
    both = OwlPlan.model_validate(plan(metric=None, add_metrics=["year", "riders"]))
    assert {"year", "riders"} <= set(both.named_columns())


@pytest.mark.parametrize(
    "bad",
    [
        {"add_metrics": ["riders", "riders"], "metric": None},  # duplicate
        {"add_metrics": ["riders"], "metric": None},  # one column is not a sum
        {"add_metrics": ["year", "riders"]},  # a metric as well
        {"add_metrics": ["a", "b", "c", "d", "e"], "metric": None},  # too many
    ],
)
def test_a_contradictory_add_metrics_is_rejected(bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        OwlPlan.model_validate(plan(**bad))


def test_add_metrics_naming_a_missing_or_text_column_fails_after_one_retry(
    factory: SessionFactory,
) -> None:
    for bad in (["year", "no_such_column"], ["station", "riders"]):  # the 2nd is text
        world = make_world(factory)
        step = plan_answer(metric=None, add_metrics=bad)
        rig, client, _ = ask_rig(factory, world, step, step)
        run_job(world.run_id, rig.deps)
        failed_with(factory, world, RunReason.BAD_MODEL_OUTPUT)
        assert len(client.calls) == 2 and rig.sandbox.calls == 0


def test_the_prompts_carry_the_combined_total_rules(factory: SessionFactory) -> None:
    from tests.ask_helpers import code_answer, sandbox_ok

    world = make_world(factory)
    rig, client, _ = ask_rig(
        factory, world, plan_answer(metric=None, add_metrics=["year", "riders"]), code_answer(),
        sandbox=[sandbox_ok()],
    )  # fmt: skip
    run_job(world.run_id, rig.deps)
    assert "Fill add_metrics only when" in client.systems[0]
    assert (
        "row-wise sum" in client.systems[1]
        and '"add_metrics": ["year", "riders"]' in client.prompts[1]
    )
    assert "thousands separators" in client.systems[2]
