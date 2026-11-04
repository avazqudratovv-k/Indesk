"""The two emails, in English and Korean: plain text plus a simple HTML version. The link is built
from the configured base URL and the token only; no request value reaches it. Any other language
falls back to English until its copy is written."""

from dataclasses import dataclass
from datetime import timedelta
from html import escape

from app.core.enums import EmailTokenPurpose

# How long each link works. The copy below states these numbers, so they live here.
TOKEN_TTL: dict[EmailTokenPurpose, timedelta] = {
    EmailTokenPurpose.RESET: timedelta(minutes=30),
    EmailTokenPurpose.VERIFY: timedelta(hours=24),
}
LINK_PATH: dict[EmailTokenPurpose, str] = {
    EmailTokenPurpose.RESET: "/reset-password",
    EmailTokenPurpose.VERIFY: "/verify-email",
}


@dataclass(frozen=True)
class Content:
    subject: str
    text: str
    html: str


@dataclass(frozen=True)
class _Copy:
    subject: str
    intro: str
    button: str
    expires: str
    ignore: str
    demo: str


_COPY: dict[tuple[EmailTokenPurpose, str], _Copy] = {
    (EmailTokenPurpose.RESET, "en"): _Copy(
        subject="Reset your Indesk password",
        intro=(
            "Someone asked to reset the password of your Indesk account. "
            "Use this link to choose a new one:"
        ),
        button="Choose a new password",
        expires="The link works once and expires in 30 minutes.",
        ignore="If you did not ask for this, ignore this email. Your password stays the same.",
        demo="Do not upload private or sensitive files.",
    ),
    (EmailTokenPurpose.RESET, "ko"): _Copy(
        subject="Indesk 비밀번호 재설정",
        intro=(
            "Indesk 계정의 비밀번호 재설정이 요청되었습니다. 아래 링크에서 새 비밀번호를 정하세요:"
        ),
        button="새 비밀번호 정하기",
        expires="링크는 한 번만 사용할 수 있으며 30분 후에 만료됩니다.",
        ignore="요청하지 않았다면 이 메일을 무시하세요. 비밀번호는 그대로 유지됩니다.",
        demo="개인 정보나 민감한 파일은 업로드하지 마세요.",
    ),
    (EmailTokenPurpose.VERIFY, "en"): _Copy(
        subject="Confirm your email for Indesk",
        intro="Welcome to Indesk. Confirm that this is your email address:",
        button="Confirm my email",
        expires="The link works once and expires in 24 hours.",
        ignore="If you did not sign up, ignore this email.",
        demo="Do not upload private or sensitive files.",
    ),
    (EmailTokenPurpose.VERIFY, "ko"): _Copy(
        subject="Indesk 이메일 확인",
        intro="Indesk에 가입해 주셔서 감사합니다. 이 이메일 주소가 본인 것인지 확인해 주세요:",
        button="이메일 확인하기",
        expires="링크는 한 번만 사용할 수 있으며 24시간 후에 만료됩니다.",
        ignore="가입하지 않았다면 이 메일을 무시하세요.",
        demo="개인 정보나 민감한 파일은 업로드하지 마세요.",
    ),
}


def link_for(purpose: EmailTokenPurpose, base_url: str, token: str) -> str:
    """The token goes in the URL fragment, so server logs and Referer headers never see it."""
    return f"{base_url.rstrip('/')}{LINK_PATH[purpose]}#token={token}"


def render(purpose: EmailTokenPurpose, lang: str, base_url: str, token: str) -> Content:
    copy = _COPY.get((purpose, lang)) or _COPY[(purpose, "en")]
    link = link_for(purpose, base_url, token)
    text = f"{copy.intro}\n\n{link}\n\n{copy.expires}\n{copy.ignore}\n\n--\n{copy.demo}\n"
    safe_link = escape(link, quote=True)
    html = (
        '<!doctype html><html><body style="font-family:Arial,sans-serif;'
        'line-height:1.5;color:#222">'
        f"<p>{escape(copy.intro)}</p>"
        f'<p><a href="{safe_link}" style="display:inline-block;padding:12px 20px;'
        f'background:#1f4fd8;color:#fff;border-radius:6px;text-decoration:none">'
        f"{escape(copy.button)}</a></p>"
        f'<p style="font-size:13px;color:#555">{safe_link}</p>'
        f"<p>{escape(copy.expires)}<br>{escape(copy.ignore)}</p>"
        f'<hr><p style="font-size:12px;color:#777">{escape(copy.demo)}</p>'
        "</body></html>"
    )
    return Content(subject=copy.subject, text=text, html=html)
