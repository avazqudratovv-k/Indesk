import ipaddress
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

AUTH_SECRET_MIN_LENGTH = 32
LIMITS_FILE = Path(__file__).resolve().parents[2] / "config" / "limits.toml"


class Limits(BaseModel):
    """Product limits from config/limits.toml, where each number names its source doc."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_file_bytes: PositiveInt
    max_rows: PositiveInt
    max_columns: PositiveInt | None = None  # None only in tests; the config file sets it
    uploads_per_hour: PositiveInt
    max_filename_chars: PositiveInt
    upload_ttl_hours: PositiveInt
    sweep_interval_seconds: PositiveInt
    files_per_slot: dict[str, PositiveInt]


def load_limits(path: Path = LIMITS_FILE) -> Limits:
    with path.open("rb") as handle:
        return Limits.model_validate(tomllib.load(handle))


def _split_commas(value: object) -> object:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return value


class Settings(BaseSettings):
    """Values come from environment variables only. Secrets are SecretStr, so they never print."""

    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    redis_url: SecretStr
    postgres_password: SecretStr | None = None
    auth_secret: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    # Comma-separated in the environment. Origins that may send a write request (CSRF check).
    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    # Comma-separated IPs or CIDRs of reverse proxies whose X-Forwarded-For is believed.
    trusted_proxies: Annotated[list[str], NoDecode] = []
    # Where the sandbox service listens (only the worker shares a network with it).
    sandbox_url: str = "http://sandbox:8080"
    # Where uploaded files live. A named volume shared by the api and the worker.
    storage_dir: Path = Path("/data/uploads")
    limits: Limits = Field(default_factory=load_limits)

    @property
    def auth_ready(self) -> bool:
        secret = self.auth_secret
        return secret is not None and len(secret.get_secret_value()) >= AUTH_SECRET_MIN_LENGTH

    @property
    def cookie_secure(self) -> bool:
        return self.app_env == "production"

    @model_validator(mode="after")
    def _production_needs_auth_secret(self) -> "Settings":
        if self.app_env == "production" and not self.auth_ready:
            raise ValueError("AUTH_SECRET must be set and at least 32 characters in production")
        return self

    @field_validator("allowed_origins", "trusted_proxies", mode="before")
    @classmethod
    def _comma_list(cls, value: object) -> object:
        return _split_commas(value)

    @field_validator("allowed_origins")
    @classmethod
    def _origins_shape(cls, value: list[str]) -> list[str]:
        cleaned = [origin.rstrip("/") for origin in value]
        if not all(o.startswith(("http://", "https://")) for o in cleaned):
            raise ValueError("each origin must start with http:// or https://")
        return cleaned

    @field_validator("trusted_proxies")
    @classmethod
    def _proxies_shape(cls, value: list[str]) -> list[str]:
        for entry in value:
            ipaddress.ip_network(entry, strict=False)  # raises ValueError on a bad entry
        return value

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
