import pytest
from pydantic import ValidationError

from app.core.config import Settings

DB = "postgresql+psycopg://u:pw-hidden@db:5432/x"
REDIS = "redis://redis:6379/0"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APP_ENV", "POSTGRES_PASSWORD", "AUTH_SECRET", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", DB)
    monkeypatch.setenv("REDIS_URL", REDIS)


def test_optional_keys_may_be_missing() -> None:
    settings = Settings()
    assert settings.app_env == "development"
    assert settings.auth_secret is None
    assert settings.gemini_api_key is None


def test_empty_optional_keys_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "")
    assert Settings().gemini_api_key is None


def test_secrets_do_not_print(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "key-hidden")
    text = repr(Settings())
    assert "key-hidden" not in text
    assert "pw-hidden" not in text


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL")
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("APP_ENV", "staging"),
        ("DATABASE_URL", "mysql://u:pw-hidden@db/x"),
        ("REDIS_URL", "http://redis"),
    ],
)
def test_bad_values_are_rejected_without_echoing_them(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError) as caught:
        Settings()
    assert value not in str(caught.value)


# ---- auth settings ----


def test_production_requires_a_long_auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://indesk.example")
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.0/8")
    for value in (None, "", "s" * 31):
        if value is None:
            monkeypatch.delenv("AUTH_SECRET", raising=False)
        else:
            monkeypatch.setenv("AUTH_SECRET", value)
        with pytest.raises(ValidationError) as caught:
            Settings()
        assert "s" * 31 not in str(caught.value)
    monkeypatch.setenv("AUTH_SECRET", "s" * 32)
    assert Settings().auth_ready


def test_development_may_start_without_an_auth_secret() -> None:
    settings = Settings()
    assert not settings.auth_ready
    assert not settings.cookie_secure


def test_origins_and_proxies_are_comma_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings().allowed_origins == ["http://localhost:3000"]
    assert Settings().trusted_proxies == []
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.example/, http://localhost:3000")
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.0/8, 127.0.0.1")
    settings = Settings()
    assert settings.allowed_origins == ["https://a.example", "http://localhost:3000"]
    assert settings.trusted_proxies == ["10.0.0.0/8", "127.0.0.1"]


@pytest.mark.parametrize(
    ("name", "value"), [("ALLOWED_ORIGINS", "ftp://x"), ("TRUSTED_PROXIES", "not-an-ip")]
)
def test_bad_origin_or_proxy_is_rejected(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings()


def test_production_startup_stops_without_a_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import app

    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError), TestClient(app):
            pass
    finally:
        get_settings.cache_clear()


# ---- production start guard ----


def _production(monkeypatch: pytest.MonkeyPatch, **env: str) -> None:
    good = {
        "APP_ENV": "production",
        "AUTH_SECRET": "s" * 32,
        "ALLOWED_ORIGINS": "https://indesk.example",
        "TRUSTED_PROXIES": "10.0.0.0/8",
    }
    for name, value in {**good, **env}.items():
        monkeypatch.setenv(name, value)


def test_a_safe_production_config_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    _production(monkeypatch)
    assert Settings().cookie_secure


@pytest.mark.parametrize(
    ("env", "named"),
    [
        ({"ALLOWED_ORIGINS": "https://indesk.example, http://localhost:3000"}, "ALLOWED_ORIGINS"),
        ({"ALLOWED_ORIGINS": "http://127.0.0.1:3000"}, "ALLOWED_ORIGINS"),
        ({"TRUSTED_PROXIES": ""}, "TRUSTED_PROXIES"),
    ],
)
def test_production_refuses_unsafe_origins_and_proxies(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], named: str
) -> None:
    _production(monkeypatch, **env)
    with pytest.raises(ValidationError) as caught:
        Settings()
    text = str(caught.value)
    assert named in text
    assert "s" * 32 not in text and "localhost:3000" not in text and "127.0.0.1:3000" not in text


def test_production_refuses_cookies_that_are_not_secure(monkeypatch: pytest.MonkeyPatch) -> None:
    _production(monkeypatch)
    monkeypatch.setattr(Settings, "cookie_secure", property(lambda self: False))
    with pytest.raises(ValidationError) as caught:
        Settings()
    assert "Secure" in str(caught.value) and "s" * 32 not in str(caught.value)


def test_development_keeps_localhost_and_no_proxies() -> None:
    settings = Settings()
    assert settings.allowed_origins == ["http://localhost:3000"] and settings.trusted_proxies == []
