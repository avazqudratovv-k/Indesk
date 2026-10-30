import ipaddress
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

AUTH_SECRET_MIN_LENGTH = 32
LIMITS_FILE = Path(__file__).resolve().parents[2] / "config" / "limits.toml"
MAX_CHUNK_CHARS = 3000  # ceiling for chunk_chars, checked at startup (embedding input cap, P14b)
MAX_EMBED_CHUNK_TOKENS = 6000  # below the model's 8,192-token input cap


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
    daily_calls_global: PositiveInt
    daily_calls_per_user: PositiveInt
    max_prompt_chars: PositiveInt
    files_per_slot: dict[str, PositiveInt]
    # Runs (P7). Each number names its source in limits.toml.
    max_question_chars: PositiveInt
    runs_per_hour: PositiveInt
    max_agent_steps: PositiveInt
    run_timeout_seconds: PositiveFloat
    run_job_timeout_seconds: PositiveInt
    run_hard_limit_seconds: PositiveFloat
    reaper_interval_seconds: PositiveInt
    reaper_gone_grace_seconds: PositiveFloat
    max_tokens_per_run: PositiveInt
    sse_streams_per_user: PositiveInt
    sse_poll_seconds: PositiveFloat
    sse_ping_seconds: PositiveFloat
    sse_max_seconds: PositiveFloat
    # Run quotas (P10a). PLACEHOLDERS: the owner replaces them after reading Google's rate limits.
    daily_runs_per_user: PositiveInt
    daily_runs_global: PositiveInt
    free_runs: NonNegativeInt
    # Ask agents (P8a).
    profile_sample_rows: PositiveInt
    profile_sample_columns: PositiveInt
    profile_cell_chars: PositiveInt
    profile_name_chars: PositiveInt
    max_stored_result_bytes: PositiveInt
    # PDF (P14a).
    max_pdf_pages: PositiveInt
    max_pdf_chars: PositiveInt
    pdf_min_text_chars: PositiveInt
    pdf_min_page_chars: PositiveInt
    chunk_chars: PositiveInt
    chunk_overlap_chars: NonNegativeInt
    # PDF search and embeddings (P14a part 2).
    max_embed_tokens_per_run: PositiveInt
    embed_usd_per_million_tokens: PositiveFloat
    retrieval_vector_k: PositiveInt
    retrieval_text_k: PositiveInt
    retrieval_keep: PositiveInt
    retrieval_rrf_k: PositiveInt
    retrieval_min_similarity: float = Field(ge=0, le=1)
    retrieval_min_terms: PositiveInt
    # Ask: a column the plan names that is not in the file counts as a near-miss of a real column
    # (a typo, not a missing column) at or above this similarity.
    column_match_similarity: float = Field(ge=0, le=1)
    # Daily purge: rows per batch, days before a finished run without a report goes, and days
    # before an ai_calls row goes.
    purge_batch: PositiveInt
    purge_no_report_days: PositiveInt
    ai_calls_retention_days: PositiveInt
    # Read and delete limits per user (reads fail open, deletes fail closed).
    reads_per_minute: PositiveInt
    deletes_per_hour: PositiveInt
    # A chunk whose estimated tokens pass this is not embedded (it stays searchable by words).
    embed_chunk_max_tokens: PositiveInt = MAX_EMBED_CHUNK_TOKENS

    @model_validator(mode="after")
    def _chunks_fit_the_embedding_model(self) -> "Limits":
        # The embedding model reads at most 8,192 tokens per text (Google's model page, owner answer
        # P14b Q3). At one token per character, the worst case for Korean, 3,000 characters stay
        # well under it. A bigger chunk size stops the server at startup.
        if self.chunk_chars > MAX_CHUNK_CHARS:
            raise ValueError(f"chunk_chars must be at most {MAX_CHUNK_CHARS}")
        if self.embed_chunk_max_tokens > MAX_EMBED_CHUNK_TOKENS:
            raise ValueError(f"embed_chunk_max_tokens must be at most {MAX_EMBED_CHUNK_TOKENS}")
        return self

    @model_validator(mode="after")
    def _overlap_is_small(self) -> "Limits":
        # The splitter looks for a break in the last 40% of a chunk; more overlap could stall it.
        if self.chunk_overlap_chars * 5 > self.chunk_chars * 2:
            raise ValueError("chunk_overlap_chars must be at most 40% of chunk_chars")
        return self


def load_limits(path: Path = LIMITS_FILE) -> Limits:
    with path.open("rb") as handle:
        return Limits.model_validate(tomllib.load(handle))


def _split_commas(value: object) -> object:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return value


def _is_local_origin(origin: str) -> bool:
    host = urlsplit(origin).hostname or ""
    return host in ("localhost", "127.0.0.1")


class Settings(BaseSettings):
    """Values come from environment variables only. Secrets are SecretStr, so they never print."""

    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    redis_url: SecretStr
    postgres_password: SecretStr | None = None
    auth_secret: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    # Absolute session length from login (SESSION_MAX_SECONDS); a refresh never extends past it.
    session_max_seconds: PositiveInt = 21600
    # Comma-separated in the environment. Origins that may send a write request (CSRF check).
    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    # Comma-separated IPs or CIDRs of reverse proxies whose X-Forwarded-For is believed.
    trusted_proxies: Annotated[list[str], NoDecode] = []
    # Where the sandbox service listens (only the worker shares a network with it).
    sandbox_url: str = "http://sandbox:8080"
    parser_url: str = "http://parser:8080"  # the PDF parser service (P14a); not the sandbox
    # DEV ONLY: lets a developer watch a run end to end with scripted agents and no Gemini. Honoured
    # only when app_env is "development" (like the web dev_session cookie, DECISIONS #67). Never set
    # in compose.yaml (a test checks); a developer sets it in their own api/.env.
    runs_dev_stub: bool = False
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

    @model_validator(mode="after")
    def _production_is_safe_to_start(self) -> "Settings":
        # Names only, never values: this text reaches the logs.
        if self.app_env != "production":
            return self
        problems = []
        if any(_is_local_origin(origin) for origin in self.allowed_origins):
            problems.append("ALLOWED_ORIGINS must not contain localhost or 127.0.0.1")
        if not self.trusted_proxies:
            problems.append("TRUSTED_PROXIES must not be empty")
        if not self.cookie_secure:
            problems.append("cookies must be marked Secure")
        if problems:
            raise ValueError("unsafe production settings: " + "; ".join(problems))
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
