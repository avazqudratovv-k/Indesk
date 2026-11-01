"""Which client the worker uses, and the check that it can send at all."""

from app.core.config import Settings
from app.email.client import EmailClient
from app.email.dev_client import ConsoleEmailClient
from app.email.resend_client import ResendClient


class EmailNotConfigured(RuntimeError):
    """Names only, never values: this text reaches the logs."""


def missing_in_production(settings: Settings) -> list[str]:
    if settings.app_env != "production":
        return []
    missing = []
    if settings.resend_api_key is None:
        missing.append("RESEND_API_KEY")
    if not settings.email_from:
        missing.append("EMAIL_FROM")
    return missing


def check_worker_ready(settings: Settings) -> None:
    """The worker refuses to start in production without the key and the from-address."""
    missing = missing_in_production(settings)
    if missing:
        raise EmailNotConfigured("email is not configured: " + ", ".join(missing) + " must be set")


def build_email_client(settings: Settings) -> EmailClient:
    if settings.resend_api_key is not None and settings.email_from:
        return ResendClient(settings.resend_api_key, settings.email_from)
    if settings.app_env == "development":
        return ConsoleEmailClient(settings.app_env)
    raise EmailNotConfigured("email is not configured: RESEND_API_KEY and EMAIL_FROM must be set")
