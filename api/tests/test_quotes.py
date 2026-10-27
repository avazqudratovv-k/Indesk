"""The match key and the quote rules (P14a part 2). Pure functions."""

import pytest

from app.runs.cat_pdf_checks import check_pdf_claim
from app.runs.quotes import check_quote, find_in_order, match_key, quote_segments


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("  a b\tc\n d  ", "abcd"),  # all whitespace goes
        ("ｆｕｌｌ　ｗｉｄｔｈ", "fullwidth"),  # NFKC
        ("ﬁnal", "final"),  # a ligature
        ("soft­hyphen", "softhyphen"),
        ("zero​width‌‍⁠﻿", "zerowidth"),
        ("inter-\nnational", "international"),  # hyphen + line break + lowercase: rejoined
        ("inter-\n  national", "international"),
        ("inter‐\nnational", "international"),
        ("Covid-\nNineteen", "Covid-Nineteen"),  # an uppercase next word keeps its hyphen
        ("well-known", "well-known"),  # no line break: untouched
        ("Case", "Case"),  # no case folding
        ("서울역\n승하차", "서울역승하차"),
    ],
)
def test_match_key(raw: str, key: str) -> None:
    assert match_key(raw) == key


def test_case_is_not_folded() -> None:
    assert match_key("US") != match_key("us")


def test_the_stored_text_stays_nfc_and_only_the_key_is_nfkc() -> None:
    from app.services.chunking import clean_page_text  # noqa: PLC0415

    assert clean_page_text("ｆｕｌｌ") == "ｆｕｌｌ"  # not folded in storage
    assert match_key(clean_page_text("ｆｕｌｌ")) == "full"


def test_segments_split_on_ellipses() -> None:
    assert quote_segments("alpha beta ... gamma delta") == ["alphabeta", "gammadelta"]
    assert quote_segments("alpha…beta....gamma") == ["alpha", "beta", "gamma"]
    assert quote_segments(" ... ") == [] and quote_segments("") == []


def test_segments_must_follow_each_other() -> None:
    page = match_key("one two three four five")
    assert find_in_order(page, ["onetwo", "fourfive"])
    assert not find_in_order(page, ["fourfive", "onetwo"])
    assert not find_in_order(page, ["twothree", "threefour", "twothree"])  # no reuse of a place


def test_check_quote_names_the_page_that_holds_it() -> None:
    pages = {1: "first page text here", 2: "second page text here"}
    assert check_quote(quote_segments("second page text"), pages, 2).ok
    wrong = check_quote(quote_segments("second page text"), pages, 1)
    assert (wrong.ok, wrong.other_page) == (False, 2)
    missing = check_quote(quote_segments("nowhere to be found"), pages, 1)
    assert (missing.ok, missing.other_page) == (False, None)


def verdict(text: str, quote: str, page: int, pages: dict[int, str]) -> str:
    got = check_pdf_claim(text, quote, page, "", pages, len(pages))
    return got.reason.value if got.reason else "verified"


def test_twelve_characters_without_spaces_is_the_floor() -> None:
    pages = {1: "the quick brown fox jumps over the lazy dog"}
    assert verdict("x", "quick brown fox", 1, pages) == "verified"  # 13 characters
    assert verdict("x", "quick brown fo", 1, pages) == "verified"  # 12 exactly
    assert verdict("x", "quick brown", 1, pages) == "quote_too_short"  # 10
    assert verdict("x", "quick brown fox ... lazy", 1, pages) == "quote_too_short"  # per piece


def test_a_korean_quote_is_counted_in_characters_too() -> None:
    pages = {1: "합정역의 이용객은 2019년부터 2025년까지 18퍼센트 늘었습니다."}
    assert verdict("x", "합정역의 이용객은 2019년부터", 1, pages) == "verified"
    assert verdict("x", "합정역의 이용객", 1, pages) == "quote_too_short"  # 7 characters
    assert verdict(
        "합정역은 19퍼센트 늘었다", "합정역의 이용객은 2019년부터 2025년까지 18퍼센트", 1, pages
    ) == ("number_not_in_quote")


def test_every_number_in_the_claim_must_be_in_the_quote() -> None:
    pages = {1: "Daily trips grew by an estimated 41,000 between 2019 and 2025 in the area."}
    quote = "an estimated 41,000 between 2019 and 2025"
    assert verdict("Trips grew by 41,000.", quote, 1, pages) == "verified"
    assert verdict("Trips grew by 41000.", quote, 1, pages) == "verified"
    assert verdict("Trips grew by 41,000 from 2019 to 2025.", quote, 1, pages) == "verified"
    assert verdict("Trips grew by 42,000.", quote, 1, pages) == "number_not_in_quote"
    assert verdict("Trips grew in 2024.", quote, 1, pages) == "number_not_in_quote"
    assert (
        verdict("Trips grew a lot.", quote, 1, pages) == "verified"
    )  # no number, nothing to check


def test_a_hyphenated_line_break_in_the_page_still_matches() -> None:
    pages = {1: "The inter-\nnational airport opened in\n2019 after long delays."}
    assert verdict("x", "The international airport opened in 2019", 1, pages) == "verified"


# ---- numbers that come from the question or are spelled out ----

LIVE_PAGE = (
    "Totals. Across all four lines there were 83,584,333 boardings and 83,508,679 alightings in "
    "the month. Line 2 had the most."
)
LIVE_QUOTE = (
    "Across all four lines there were 83,584,333 boardings and 83,508,679 alightings in the month."
)
LIVE_QUESTION = "2026년 9월 전체 승차 인원은 몇 명인가요?"
LIVE_CLAIM = "2026년 9월 한 달 동안 4개 노선 전체에서 83,584,333건의 승차가 발생했습니다."


def claim_verdict(text: str, quote: str, page_text: str, question: str = "") -> str:
    got = check_pdf_claim(text, quote, 1, "", {1: page_text}, 1, question)
    return got.reason.value if got.reason else "verified"


def test_the_live_false_negative_now_verifies() -> None:
    assert claim_verdict(LIVE_CLAIM, LIVE_QUOTE, LIVE_PAGE, LIVE_QUESTION) == "verified"


def test_the_live_claim_without_the_question_still_fails() -> None:
    assert claim_verdict(LIVE_CLAIM, LIVE_QUOTE, LIVE_PAGE) == "number_not_in_quote"  # 2026, 9


def test_a_wrong_big_number_still_fails_even_with_context_and_spelling() -> None:
    wrong = LIVE_CLAIM.replace("83,584,333", "83,584,334")
    assert claim_verdict(wrong, LIVE_QUOTE, LIVE_PAGE, LIVE_QUESTION) == "number_not_in_quote"
    wrong = LIVE_CLAIM.replace("83,584,333", "83.7 million")
    assert claim_verdict(wrong, LIVE_QUOTE, LIVE_PAGE, LIVE_QUESTION) == "number_not_in_quote"


def test_a_big_number_in_the_question_does_not_vouch_for_itself() -> None:
    page = "Ridership rose by an estimated 41,000 daily trips over the period."
    quote = "Ridership rose by an estimated 41,000 daily trips"
    asked = "Did ridership rise by 50000 or 41,000 trips?"
    assert claim_verdict("Trips rose by 50000.", quote, page, asked) == "number_not_in_quote"
    assert claim_verdict("Trips rose by 41,000.", quote, page, asked) == "verified"


def test_a_wrong_small_number_not_spelled_and_not_asked_fails() -> None:
    assert claim_verdict("There were 5 lines.", LIVE_QUOTE, LIVE_PAGE, LIVE_QUESTION) == (
        "number_not_in_quote"
    )
    assert claim_verdict("There were 3 lines.", LIVE_QUOTE, LIVE_PAGE) == "number_not_in_quote"


def test_english_spelled_numbers_zero_to_twelve() -> None:
    for n, word in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve".split()
    ):
        page = f"The network has {word} lines in the report."
        assert claim_verdict(f"There are {n} lines.", page, page) == "verified", word
        other = (n + 1) % 13
        assert claim_verdict(f"There are {other} lines.", page, page) == "number_not_in_quote"
    thirteen = "Thirteen lines are in the report."
    assert claim_verdict("There are 13 lines.", thirteen, thirteen) == "number_not_in_quote"
    fourteen = "Fourteen lines are in the report."  # contains "four" but not as a word
    assert claim_verdict("There are 4 lines.", fourteen, fourteen) == "number_not_in_quote"


def test_korean_spelled_numbers_need_a_counter_or_a_long_form() -> None:
    cases = [
        (1, "노선이 하나 있습니다"), (1, "한 개 노선입니다 정말로"), (2, "노선이 두 개 있습니다"),
        (3, "세 개 노선이 있습니다"), (4, "네 개 노선이 있습니다"), (4, "노선은 넷 개로 나뉩니다"),
        (5, "다섯 개 노선이 있습니다"), (6, "여섯 개 노선이 있습니다"),
        (7, "일곱 개 노선이 있습니다"), (8, "여덟 개 노선이 있습니다"),
        (9, "아홉 개 노선이 있습니다"), (10, "열 개 노선이 있습니다"),
        (11, "열한 개 노선이 있습니다"), (12, "열두 개 노선이 있습니다"),
        (4, "사 개 노선이 있습니다"), (2, "이호선이 있습니다 정말로"), (4, "사개 노선이 있습니다"),
        (12, "십이 개 노선이 있습니다"), (3, "삼 호선이 있습니다 정말로"),
    ]  # fmt: skip
    for n, short in cases:
        quote = f"{short} 정말로 그렇습니다"  # long enough to pass the quote floor
        assert claim_verdict(f"노선은 {n}개입니다.", quote, quote) == "verified", quote


def test_korean_everyday_syllables_do_not_spell_a_number() -> None:
    page = "사용일자별 이용객은 오전과 오후로 나뉘며 이 문서는 구성을 설명합니다."
    for n in (2, 4, 5, 9, 1):
        assert claim_verdict(f"{n}개 노선이 있습니다.", page, page) == "number_not_in_quote", n


def test_a_decimal_or_percent_is_never_helped_by_a_spelled_word() -> None:
    page = "The share was four percent of all trips in the month."
    assert claim_verdict("The share was 4 percent.", page, page) == "number_not_in_quote"
    assert claim_verdict("The share was 4.0 percent.", page, page) == "number_not_in_quote"
    assert claim_verdict("There were 4 lines.", page, page) == "verified"  # a plain count is fine
