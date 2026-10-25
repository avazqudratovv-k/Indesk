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
