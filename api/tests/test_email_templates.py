"""The two emails: the link is built from the base URL and the token alone, both languages exist,
and an unknown language falls back to English."""

import re

import pytest

from app.core.enums import EmailTokenPurpose
from app.email.templates import LINK_PATH, TOKEN_TTL, link_for, render

BASE = "https://indesk.uz"
TOKEN = "tok_-AbC123"


@pytest.mark.parametrize("purpose", list(EmailTokenPurpose))
@pytest.mark.parametrize("lang", ["en", "ko"])
def test_each_email_has_text_html_and_the_link_in_the_fragment(
    purpose: EmailTokenPurpose, lang: str
) -> None:
    content = render(purpose, lang, BASE, TOKEN)
    link = f"{BASE}{LINK_PATH[purpose]}#token={TOKEN}"

    assert link in content.text and link in content.html
    assert content.subject and "<html" in content.html and "<a href=" in content.html
    assert "?token" not in content.text  # never in the query string
    assert "demo" in content.text.lower() or "데모" in content.text


@pytest.mark.parametrize("purpose", list(EmailTokenPurpose))
def test_korean_is_korean_and_other_languages_fall_back_to_english(
    purpose: EmailTokenPurpose,
) -> None:
    korean = render(purpose, "ko", BASE, TOKEN)
    english = render(purpose, "en", BASE, TOKEN)
    assert re.search(r"[가-힣]", korean.subject) and not re.search(r"[가-힣]", english.subject)
    for lang in ("ja", "ru", "uz", "xx"):
        assert render(purpose, lang, BASE, TOKEN) == english


def test_the_text_states_the_real_lifetime() -> None:
    reset = render(EmailTokenPurpose.RESET, "en", BASE, TOKEN).text
    verify = render(EmailTokenPurpose.VERIFY, "en", BASE, TOKEN).text
    assert "30 minutes" in reset and TOKEN_TTL[EmailTokenPurpose.RESET].total_seconds() == 1800
    assert "24 hours" in verify and TOKEN_TTL[EmailTokenPurpose.VERIFY].total_seconds() == 86400


def test_a_trailing_slash_on_the_base_is_dropped_and_html_is_escaped() -> None:
    assert (
        link_for(EmailTokenPurpose.RESET, BASE + "/", TOKEN)
        == f"{BASE}/reset-password#token={TOKEN}"
    )
    html = render(EmailTokenPurpose.RESET, "en", 'https://x.test/"><script>', TOKEN).html
    assert "<script>" not in html and "&lt;script&gt;" in html
