"""The model chain from config/models.toml. Model names live there, not in code (Decision #30)."""

import tomllib
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    model_validator,
)

MODELS_FILE = Path(__file__).resolve().parents[2] / "config" / "models.toml"
MODEL_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,98}$"  # also used in a URL path, so no slashes


class ModelSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=MODEL_NAME_PATTERN)
    timeout_seconds: PositiveFloat
    max_output_tokens: PositiveInt
    thinking_budget: NonNegativeInt


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


def load_model_chain(path: Path = MODELS_FILE) -> ModelChain:
    with path.open("rb") as handle:
        return ModelChain.model_validate(tomllib.load(handle))
