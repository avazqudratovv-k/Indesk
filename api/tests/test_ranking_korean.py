"""Korean most/least wording in the ranking-word rule: 가장 alone decides nothing, the word after
it does; a mixed or unknown wording is never guessed. The real Seoul shape: line, boardings,
alightings. No database, no model."""

import pytest

from app.core.enums import ClaimStatus, ReportReason
from app.runs.ask_schemas import ComputedResult
from app.runs.cat_checks import ResultView, check_claim, ranking_directions

LINES = ResultView.of(
    ComputedResult(
        columns=["노선명", "승차총승객수", "하차총승객수"],
        rows=[
            ["2호선", 41527060, 42098204],
            ["7호선", 17000000, 18018664],
            ["1호선", 8321795, 8133134],
        ],
        rows_used=4079,
    ),
    4079,
)


def verdict(text: str, *refs: str):  # type: ignore[no-untyped-def]
    return check_claim(text, list(refs), LINES, set())


@pytest.mark.parametrize(
    "text",
    [
        "1호선의 승차총승객수는 8,321,795명으로 가장 적습니다.",
        "1호선의 승차총승객수는 8,321,795명으로 가장 적은 수입니다.",
        "1호선의 승차총승객수는 8,321,795명으로 가장 낮습니다.",
        "1호선의 승차총승객수는 8,321,795명으로 가장 낮은 값입니다.",
        "1호선의 승차총승객수는 8,321,795명으로 가장 작습니다.",
        "1호선의 승차총승객수는 8,321,795명으로 가장 작은 값입니다.",
        "1호선의 승차총승객수는 8,321,795명으로 최소입니다.",
        "1호선의 승차총승객수는 8,321,795명으로 최저입니다.",
    ],
)
def test_a_korean_least_claim_is_verified_for_the_minimum(text: str) -> None:
    assert ranking_directions(text) == {"min"}
    assert verdict(text, "r3c2").status is ClaimStatus.VERIFIED


def test_a_korean_least_claim_is_not_verified_when_it_is_not_the_minimum() -> None:
    got = verdict("7호선의 승차총승객수는 17,000,000명으로 가장 적습니다.", "r2c2")
    assert (got.status, got.reason) == (ClaimStatus.UNVERIFIED, ReportReason.RANKING_UNCHECKED)
    # the minimum of ANOTHER column does not count: 1호선 is also the minimum of alightings, but
    # this claim cites the boardings of 2호선
    got = verdict("2호선의 승차총승객수는 41,527,060명으로 최소입니다.", "r1c2")
    assert got.reason is ReportReason.RANKING_UNCHECKED


@pytest.mark.parametrize(
    "text",
    [
        "2호선의 승차총승객수는 41,527,060명으로 가장 많습니다.",
        "2호선의 승차총승객수는 41,527,060명으로 가장 높은 값입니다.",
        "2호선의 승차총승객수는 41,527,060명으로 가장 큰 값입니다.",
        "2호선의 승차총승객수는 41,527,060명으로 최대입니다.",
        "2호선의 승차총승객수는 41,527,060명으로 최고입니다.",
    ],
)
def test_korean_most_claims_still_work(text: str) -> None:
    assert ranking_directions(text) == {"max"}
    assert verdict(text, "r1c2").status is ClaimStatus.VERIFIED
    wrong = verdict(text.replace("2호선", "1호선").replace("41,527,060", "8,321,795"), "r3c2")
    assert wrong.reason is ReportReason.RANKING_UNCHECKED


def test_a_claim_with_a_most_and_a_least_word_is_unverified() -> None:
    text = "2호선은 가장 많습니다. 1호선은 가장 적습니다: 41,527,060, 8,321,795."
    assert ranking_directions(text) == {"max", "min"}
    got = verdict(text, "r1c2", "r3c2")
    assert (got.status, got.reason) == (ClaimStatus.UNVERIFIED, ReportReason.RANKING_UNCHECKED)
    mixed = verdict("1호선은 최대가 아니라 가장 적습니다: 8,321,795.", "r3c2")
    assert mixed.reason is ReportReason.RANKING_UNCHECKED


@pytest.mark.parametrize(
    "text",
    [
        "1호선의 승차총승객수는 8,321,795명으로 가장 적합합니다.",  # begins with 적, not "few"
        "1호선의 승차총승객수는 8,321,795명으로 가장 붐비지 않습니다.",
        "1호선의 승차총승객수는 8,321,795명으로 가장",
    ],
)
def test_an_unknown_word_after_gajang_is_unverified(text: str) -> None:
    assert ranking_directions(text) == {"unknown"}
    got = verdict(text, "r3c2")
    assert (got.status, got.reason) == (ClaimStatus.UNVERIFIED, ReportReason.RANKING_UNCHECKED)


def test_the_two_row_minimum_still_applies() -> None:
    one = ResultView.of(
        ComputedResult(columns=["노선명", "승차"], rows=[["1호선", 5]], rows_used=1), 1
    )
    got = check_claim("1호선은 승차 5명으로 가장 적습니다.", ["r1c2"], one, set())
    assert got.reason is ReportReason.RANKING_UNCHECKED


def test_english_least_words_are_unchanged() -> None:
    assert ranking_directions("the least, lowest and smallest") == {"min"}
    assert ranking_directions("the most and the top") == {"max"}
    assert verdict("1호선 had the lowest boardings: 8,321,795.", "r3c2").status is (
        ClaimStatus.VERIFIED
    )
