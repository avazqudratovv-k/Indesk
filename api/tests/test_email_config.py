"""Email settings and the production guards: the base URL rules, the from-address shape, the worker
that will not start without a key, and the console client that can only exist in development."""

import io
from typing import get_args

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings, load_limits
from app.core.enums import EmailTokenPurpose
from app.email.client import EmailMessage, EmailOk
from app.email.dev_client import ConsoleEmailClient
from app.email.factory import (
    EmailNotConfigured,
    build_email_client,
    check_worker_ready,
    missing_in_production,
)
from app.email.resend_client import ResendClient
from app.email.templates import link_for

ENVS = get_args(Settings.model_fields["app_env"].annotation)
KEY = "re_test_key_0123456789"
FROM = "Indesk <no-reply@indesk.uz>"


def production(monkeypatch: pytest.MonkeyPatch, **env: str) -> None:
    good = {
        "APP_ENV": "production",
        "AUTH_SECRET": "s" * 32,
        "ALLOWED_ORIGINS": "https://indesk.uz",
        "TRUSTED_PROXIES": "10.0.0.0/8",
        "APP_BASE_URL": "https://indesk.uz",
    }
    for name, value in {**good, **env}.items():
        monkeypatch.setenv(name, value)


# ---- defaults and the limit ----


def test_defaults_are_safe_and_the_cap_is_50() -> None:
    settings = Settings()
    assert settings.email_verification_required is False
    assert settings.resend_api_key is None and settings.email_from is None
    assert settings.app_base_url is None and settings.email_link_base == "http://localhost:3000"
    assert load_limits().email_daily_global == 50


def test_the_flag_reads_0_and_1(monkeypatch: pytest.MonkeyPatch) -> None:
    for value, expected in (("0", False), ("1", True)):
        monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", value)
        assert Settings().email_verification_required is expected


def test_the_daily_cap_is_required_and_positive() -> None:
    values = load_limits().model_dump()
    from app.core.config import Limits  # noqa: PLC0415

    with pytest.raises(ValueError):
        Limits(**{k: v for k, v in values.items() if k != "email_daily_global"})
    with pytest.raises(ValueError):
        Limits(**{**values, "email_daily_global": 0})


def test_empty_values_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("RESEND_API_KEY", "EMAIL_FROM", "APP_BASE_URL"):
        monkeypatch.setenv(name, "")
    settings = Settings()
    assert (settings.resend_api_key, settings.email_from, settings.app_base_url) == (None,) * 3


# ---- the base URL ----


def test_a_good_production_base_url_starts_and_a_trailing_slash_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    production(monkeypatch, APP_BASE_URL="https://indesk.uz/")
    assert Settings().app_base_url == "https://indesk.uz"


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"APP_BASE_URL": ""}, "APP_BASE_URL must be set"),
        ({"APP_BASE_URL": "http://indesk.uz", "ALLOWED_ORIGINS": "http://indesk.uz"}, "https"),
        ({"APP_BASE_URL": "https://localhost", "ALLOWED_ORIGINS": "https://localhost"}, "https"),
        ({"APP_BASE_URL": "https://127.0.0.1", "ALLOWED_ORIGINS": "https://127.0.0.1"}, "https"),
        ({"APP_BASE_URL": "https://other.example"}, "ALLOWED_ORIGINS"),
        ({"APP_BASE_URL": "https://indesk.uz:8443"}, "ALLOWED_ORIGINS"),
    ],
)
def test_production_refuses_a_bad_base_url(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], message: str
) -> None:
    production(monkeypatch, **env)
    with pytest.raises(ValidationError) as caught:
        Settings()
    assert message in str(caught.value) and "s" * 32 not in str(caught.value)


@pytest.mark.parametrize(
    "value",
    ["https://indesk.uz/reset", "https://indesk.uz?x=1", "https://u:p@indesk.uz", "ftp://indesk.uz",
     "indesk.uz", "https://indesk.uz/#a", "https://in desk.uz"],
)  # fmt: skip
def test_a_base_url_must_be_a_plain_origin(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("APP_BASE_URL", value)
    with pytest.raises(ValidationError):
        Settings()


def test_the_link_comes_from_the_setting_only(monkeypatch: pytest.MonkeyPatch) -> None:
    production(monkeypatch)
    base = Settings().email_link_base
    assert (
        link_for(EmailTokenPurpose.RESET, base, "t") == "https://indesk.uz/reset-password#token=t"
    )


# ---- the from-address ----


@pytest.mark.parametrize("value", [FROM, "no-reply@indesk.uz", "  Indesk <no-reply@indesk.uz> "])
def test_good_from_addresses(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("EMAIL_FROM", value)
    assert Settings().email_from == value.strip()


@pytest.mark.parametrize(
    "value",
    ["Indesk", "Indesk <no-reply@indesk.uz", "no-reply@indesk.uz>", "a@b", "x" * 300,
     "Indesk <a@indesk.uz>\nBcc: evil@example.com", "A <a@indesk.uz> <b@indesk.uz>"],
)  # fmt: skip
def test_bad_from_addresses_are_refused(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("EMAIL_FROM", value)
    with pytest.raises(ValidationError):
        Settings()


# ---- the worker and the client factory ----


def test_the_worker_check_names_what_is_missing_in_production_and_no_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    production(monkeypatch)
    settings = Settings()
    assert missing_in_production(settings) == ["RESEND_API_KEY", "EMAIL_FROM"]
    with pytest.raises(EmailNotConfigured) as caught:
        check_worker_ready(settings)
    assert "RESEND_API_KEY" in str(caught.value) and "EMAIL_FROM" in str(caught.value)
    assert "indesk.uz" not in str(caught.value)

    only_key = settings.model_copy(update={"resend_api_key": SecretStr(KEY)})
    with pytest.raises(EmailNotConfigured, match="EMAIL_FROM"):
        check_worker_ready(only_key)

    ready = only_key.model_copy(update={"email_from": FROM})
    check_worker_ready(ready)  # does not raise
    assert isinstance(build_email_client(ready), ResendClient)


@pytest.mark.parametrize("app_env", ["development", "test"])
def test_the_worker_check_only_applies_in_production(app_env: str) -> None:
    check_worker_ready(Settings(app_env=app_env))


def test_the_worker_main_stops_before_listening_in_production_without_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.jobs import worker  # noqa: PLC0415

    production(monkeypatch)
    started: list[str] = []
    monkeypatch.setattr(worker, "get_settings", lambda: Settings())
    monkeypatch.setattr(worker, "Worker", lambda *a, **k: started.append("worker"))
    with pytest.raises(EmailNotConfigured):
        worker.main()
    assert started == []


@pytest.mark.parametrize("app_env", [e for e in ENVS if e != "development"])
def test_the_console_client_cannot_be_built_outside_development(app_env: str) -> None:
    with pytest.raises(RuntimeError, match="development only"):
        ConsoleEmailClient(app_env)


def test_with_no_key_only_development_gets_the_console_and_production_never_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for app_env in ENVS:
        if app_env == "development":
            assert isinstance(build_email_client(Settings(app_env=app_env)), ConsoleEmailClient)
            continue
        if app_env == "production":
            production(monkeypatch)
            settings = Settings()
        else:
            settings = Settings(app_env=app_env)
        with pytest.raises(EmailNotConfigured):
            build_email_client(settings)


def test_the_console_client_prints_the_message_and_reports_success() -> None:
    out = io.StringIO()
    message = EmailMessage(
        to="dev@example.com", subject="s", text="the link", html="<p>x</p>", idempotency_key="k"
    )
    assert ConsoleEmailClient("development", out=out).send(message) == EmailOk()
    assert "the link" in out.getvalue()
