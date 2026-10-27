"""Small numbers written as words, for one rule of Cat's PDF check: a claim may say "4" when its
quote says "four" or "네 개". Only whole numbers 0 to 12.

English words match as whole words. Korean is looser by nature, so it is held tight: the long
forms (다섯, 여섯, 일곱, 여덟, 아홉, 하나, 열하나, 열둘 ...) must not follow another Hangul letter,
and every short form (한, 두, 세, 네, 둘, 셋, 넷, 열, and the Sino-Korean 일, 이, 삼 ... 십이, which
are also everyday particles and syllables) counts only when a counter word follows (개, 명, 곳,
호선 ...). A closed list, no model. It never lets a number of 3 digits, a decimal or a number with
a thousands separator pass: those must be in the quote as written (app.runs.numbers)."""

import re
from typing import Final

MAX_SPELLED: Final = 12

_ENGLISH: Final[dict[int, str]] = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
    8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
}  # fmt: skip

# Native Korean. Short forms need a counter after them; long forms only need to start a word.
_NATIVE_LONG: Final[dict[int, tuple[str, ...]]] = {
    1: ("하나",), 5: ("다섯",), 6: ("여섯",), 7: ("일곱",), 8: ("여덟",), 9: ("아홉",),
    11: ("열하나", "열한"), 12: ("열둘", "열두"),
}  # fmt: skip
_NATIVE_SHORT: Final[dict[int, tuple[str, ...]]] = {
    1: ("한",), 2: ("둘", "두"), 3: ("셋", "세"), 4: ("넷", "네"), 10: ("열",),
}  # fmt: skip
# Sino-Korean, always with a counter: 일, 이, 삼 ... 십이 (영 and 공 for zero).
_SINO: Final[dict[int, tuple[str, ...]]] = {
    0: ("영", "공"), 1: ("일",), 2: ("이",), 3: ("삼",), 4: ("사",), 5: ("오",), 6: ("육",),
    7: ("칠",), 8: ("팔",), 9: ("구",), 10: ("십",), 11: ("십일",), 12: ("십이",),
}  # fmt: skip

_COUNTERS: Final = (
    "개월|개국|개|명|곳|건|번|회|가지|대|호선|노선|달|주|역|분|종|권|장|줄|사람|시간|일간|년"
)
_NOT_HANGUL_BEFORE: Final = r"(?<![가-힣])"


def _patterns(number: int) -> list[re.Pattern[str]]:
    found: list[re.Pattern[str]] = []
    if number in _ENGLISH:
        found.append(re.compile(rf"\b{_ENGLISH[number]}\b", re.IGNORECASE))
    for word in _NATIVE_LONG.get(number, ()):
        found.append(re.compile(_NOT_HANGUL_BEFORE + word))
    short = (*_NATIVE_SHORT.get(number, ()), *_SINO.get(number, ()))
    for word in short:
        found.append(re.compile(rf"{_NOT_HANGUL_BEFORE}{word}\s?(?:{_COUNTERS})"))
    return found


_PATTERNS: Final[dict[int, list[re.Pattern[str]]]] = {
    n: _patterns(n) for n in range(MAX_SPELLED + 1)
}


def spelled_in(number: int, text: str) -> bool:
    """Is `number` (0 to 12) written as a word in `text`?"""
    return any(p.search(text) for p in _PATTERNS.get(number, []))
