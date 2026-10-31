"""The quantity-word detector (P14b): a size said in words ("about a million") that number_tokens,
which reads digits only, never saw. Closed lists, no model."""

import pytest

from app.runs.numbers import quantity_words, unsupported_quantity_words


@pytest.mark.parametrize(
    ("text", "words"),
    [
        ("Weekdays carry about a million more boardings than weekends.", ["million"]),
        ("Hundreds of riders and thousands of trips", ["hundred", "thousand"]),
        ("a billion, a trillion", ["billion", "trillion"]),
        ("Ridership doubled and then tripled", ["double", "triple"]),
        ("twice as many, a double dose, a triple jump", ["twice", "double", "triple"]),
        ("Million MILLION million", ["million"]),  # case folded, one entry per word
        ("수억 원이 들었다", ["억"]),
        ("십억 명이 탔다", ["억"]),
        ("오십억이 넘는다", ["억"]),
        ("수조 원", ["조"]),
        ("조가 넘는다", ["조"]),
        ("수백만 명", ["백만"]),
        ("천만 명이 넘는다", ["천만"]),
        ("절반을 넘는다", ["절반"]),
        ("두 배로 늘었다", ["두 배"]),
        ("세배 가까이", ["세 배"]),
    ],
)
def test_a_quantity_word_is_found(text: str, words: list[str]) -> None:
    assert quantity_words(text) == words


@pytest.mark.parametrize(
    "text",
    [
        "기억",
        "억울",
        "조건",
        "조금",
        "조사",  # Korean words that only contain 억 or 조
        "구조",
        "일조",
        "백조",
        "추억",
        "기억에 남는 조건",  # and the numeral-looking ones
        "half the stations and a dozen lines",  # not on the list
        "2.45 million boardings",  # a written number: number_tokens checks it
        "1,000,000 boardings",
        "5 thousand and 3 hundred",
        "2.5억 원",
        "Station names: Millionaire Street, Doubleday, Tripleton",  # a word needs its boundary
        "",
    ],
)
def test_ordinary_words_and_written_numbers_do_not_trigger(text: str) -> None:
    assert quantity_words(text) == []


def test_support_must_say_the_same_word() -> None:
    sentence = "Weekdays carry about a million more boardings."
    assert unsupported_quantity_words(sentence) == ["million"]
    assert unsupported_quantity_words(sentence, "Is it about a million more?") == []
    assert unsupported_quantity_words(sentence, "the quote says billion") == ["million"]
    assert unsupported_quantity_words("Ridership doubled.", "twice", "double") == []
    assert unsupported_quantity_words("no sizes here", "anything") == []


def test_a_written_number_in_the_support_is_not_a_word_in_the_support() -> None:
    # "2.45 million" is a number the digit check reads; it does not license "about a million".
    assert unsupported_quantity_words("about a million", "carried 2.45 million riders") == [
        "million"
    ]
