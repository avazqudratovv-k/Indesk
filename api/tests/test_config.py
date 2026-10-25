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
