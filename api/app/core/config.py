from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Values come from environment variables only. Secrets are SecretStr, so they never print."""

    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    redis_url: SecretStr
    postgres_password: SecretStr | None = None
    auth_secret: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def _database_scheme(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("must start with postgresql+psycopg://")
        return value

    @field_validator("redis_url")
    @classmethod
    def _redis_scheme(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(("redis://", "rediss://")):
            raise ValueError("must start with redis:// or rediss://")
        return value

    @field_validator("postgres_password", "auth_secret", "gemini_api_key", mode="before")
    @classmethod
    def _empty_is_unset(cls, value: object) -> object:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
