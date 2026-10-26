"""List the model names the GEMINI_API_KEY can use for text generation (names only).

    docker compose run --rm api python scripts/list_models.py

This is the ONLY code that may be run by hand against the real API. It prints names, never the key,
a URL or a response body. On a failure it prints only the HTTP status or the exception class.
It also says whether each model in config/models.toml is in the list."""

import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

import httpx
from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `app` imports from /app/scripts

from app.ai.config import load_model_chain  # noqa: E402
from app.ai.real_client import ListError, list_text_models  # noqa: E402


def main(
    env: Mapping[str, str],
    out: Callable[[str], None] = print,
    *,
    transport: httpx.BaseTransport | None = None,
) -> int:
    key = env.get("GEMINI_API_KEY", "").strip()
    if not key:
        out(
            "GEMINI_API_KEY is not set. Put it in api/.env (variable name only; never paste a key)."
        )
        return 2
    result = list_text_models(SecretStr(key), transport=transport)
    if isinstance(result, ListError):
        out(f"Could not list models: {result.label}")
        return 1
    out(f"{len(result.names)} models can generate text:")
    for name in result.names:
        out(f"  {name}")
    try:
        wanted = [spec.name for spec in load_model_chain().chain]
    except Exception:  # noqa: BLE001
        out("config/models.toml could not be read.")
        return 1
    out("config/models.toml chain:")
    for name in wanted:
        out(f"  {name}: {'listed' if name in result.names else 'NOT LISTED, fix models.toml'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(os.environ))
