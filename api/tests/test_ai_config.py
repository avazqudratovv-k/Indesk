import pytest
from pydantic import ValidationError

from app.ai.config import MODELS_FILE, ModelChain, load_model_chains
from app.core.config import load_limits

SPEC = {"timeout_seconds": 10, "max_output_tokens": 100, "thinking_budget": 0}


def test_models_toml_has_the_two_chains_in_order() -> None:
    chains = load_model_chains()
    assert chains.light.total_budget_seconds == chains.main.total_budget_seconds == 35
    # DECISIONS #27 (light) and #28 (main).
    assert [m.name for m in chains.light.chain] == [
        "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash",
    ]  # fmt: skip
    assert [m.name for m in chains.main.chain] == [
        "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite",
    ]  # fmt: skip
    assert all(m.max_output_tokens == 8192 for m in chains.main.chain)
    assert not any(
        "pro" in m.name or "argon" in m.name for c in (chains.light, chains.main) for m in c.chain
    )


def test_a_left_out_thinking_budget_is_none() -> None:
    spec = ModelChain.model_validate(
        {
            "total_budget_seconds": 35,
            "chain": [{"name": "a", "timeout_seconds": 5, "max_output_tokens": 9}],
        }
    ).chain[0]
    assert spec.thinking_budget is None


def test_models_toml_says_the_names_are_unverified() -> None:
    text = MODELS_FILE.read_text()
    assert "UNVERIFIED" in text and "scripts/list_models.py" in text
    assert "max_output_tokens" in text and "gemini-3.x" in text


def test_new_limits() -> None:
    limits = load_limits()
    assert (limits.daily_calls_global, limits.daily_calls_per_user) == (200, 50)
    assert limits.max_prompt_chars == 40000


@pytest.mark.parametrize(
    "data",
    [
        {"total_budget_seconds": 35, "chain": []},
        {"total_budget_seconds": 35, "chain": [{"name": "a", **SPEC}, {"name": "a", **SPEC}]},
        {"total_budget_seconds": 35, "chain": [{"name": f"m{i}", **SPEC} for i in range(4)]},
        {"total_budget_seconds": 35, "chain": [{"name": "bad/name", **SPEC}]},
        {"total_budget_seconds": 0, "chain": [{"name": "a", **SPEC}]},
        {"total_budget_seconds": 35, "chain": [{"name": "a", **{**SPEC, "thinking_budget": -1}}]},
        {"total_budget_seconds": 35, "chain": [{"name": "a", **SPEC, "extra": 1}]},
    ],
)
def test_bad_chains_are_rejected(data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ModelChain.model_validate(data)
