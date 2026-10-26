"""Language of a question: Korean when Hangul is at least 30% of its letters, otherwise English.
Decided on the server; the client never sends it (DECISIONS #98: a report follows its question)."""

from app.core.enums import Lang

HANGUL_SHARE = 0.3


def _is_hangul(char: str) -> bool:
    code = ord(char)
    return 0xAC00 <= code <= 0xD7AF or 0x1100 <= code <= 0x11FF or 0x3130 <= code <= 0x318F


def detect_lang(question: str) -> Lang:
    letters = [c for c in question if c.isalpha()]
    if not letters:
        return Lang.EN
    share = sum(_is_hangul(c) for c in letters) / len(letters)
    return Lang.KO if share >= HANGUL_SHARE else Lang.EN
