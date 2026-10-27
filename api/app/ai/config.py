"""The model chains from config/models.toml, one per job class. Model names live there, not in
code (Decision #30)."""

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    model_validator,
)

from app.core.enums import JobClass

MODELS_FILE = Path(__file__).resolve().parents[2] / "config" / "models.toml"
MODEL_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,98}$"  # also used in a URL path, so no slashes


class ModelSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=MODEL_NAME_PATTERN)
    timeout_seconds: PositiveFloat
    max_output_tokens: PositiveInt
    # None (the key is left out of the file): no thinking field is sent at all, so the model uses
    # its own default. 0 is sent as 0.
    thinking_budget: NonNegativeInt | None = None
    # gemini-3.x models take a level, not a budget (the first real call showed HTTP 400 for
    # thinkingBudget 0 on gemini-3.5-flash-lite). Set at most one of the two.
    thinking_level: Literal["minimal", "low", "medium", "high"] | None = None

    @model_validator(mode="after")
    def _one_thinking_setting(self) -> "ModelSpec":
        if self.thinking_budget is not None and self.thinking_level is not None:
            raise ValueError("set thinking_budget or thinking_level, not both")
        return self


class ModelChain(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total_budget_seconds: PositiveFloat
    chain: list[ModelSpec] = Field(min_length=1, max_length=3)  # ai_calls.attempt is 1 to 3

    @model_validator(mode="after")
    def _unique_names(self) -> "ModelChain":
        names = [spec.name for spec in self.chain]
        if len(set(names)) != len(names):
            raise ValueError("model names in the chain must be unique")
        return self


class EmbedSpec(BaseModel):
    """The one embedding model. No chain of models: only retries on this one (P14a part 2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=MODEL_NAME_PATTERN)
    timeout_seconds: PositiveFloat
    dimensions: PositiveInt
    attempts: int = Field(ge=1, le=3)  # ai_calls.attempt is 1 to 3
    batch_size: int = Field(ge=1, le=100)  # the API takes at most 100 texts in one batch


class EmbedChain(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total_budget_seconds: PositiveFloat
    spec: EmbedSpec


class ModelChains(BaseModel):
    """One chain per job class (light, main), and the embedding model (None: not configured)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    light: ModelChain
    main: ModelChain
    embed: EmbedChain | None = None

    def for_class(self, job_class: JobClass) -> ModelChain:
        return self.light if job_class is JobClass.LIGHT else self.main


class _ModelsFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total_budget_seconds: PositiveFloat
    light: list[ModelSpec] = Field(min_length=1, max_length=3)
    main: list[ModelSpec] = Field(min_length=1, max_length=3)
    embed: list[EmbedSpec] = Field(default_factory=list, max_length=1)  # one model, no chain


def load_model_chains(path: Path = MODELS_FILE) -> ModelChains:
    with path.open("rb") as handle:
        raw = _ModelsFile.model_validate(tomllib.load(handle))
    return ModelChains(
        light=ModelChain(total_budget_seconds=raw.total_budget_seconds, chain=raw.light),
        main=ModelChain(total_budget_seconds=raw.total_budget_seconds, chain=raw.main),
        embed=(
            EmbedChain(total_budget_seconds=raw.total_budget_seconds, spec=raw.embed[0])
            if raw.embed
            else None
        ),
    )
