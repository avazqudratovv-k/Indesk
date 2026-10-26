import pytest
from pydantic import ValidationError

from app.ai.config import MODELS_FILE, ModelChain, load_model_chain
from app.core.config import load_limits

SPEC = {"timeout_seconds": 10, "max_output_tokens": 100, "thinking_budget": 0}


def test_models_toml_has_the_two_models_in_order() -> None:
    chain = load_model_chain()
    assert chain.total_budget_seconds == 35
    assert [
        (m.name, m.timeout_seconds, m.max_output_tokens, m.thinking_budget) for m in chain.chain
    ] == [
        ("gemini-2.5-flash", 20, 4096, 1024),
        ("gemini-2.5-flash-lite", 12, 4096, 0),
    ]
    assert not any("pro" in m.name for m in chain.chain)


def test_models_toml_says_the_names_are_unverified() -> None:
    text = MODELS_FILE.read_text()
    assert "UNVERIFIED" in text and "scripts/list_models.py" in text


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
