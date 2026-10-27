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
