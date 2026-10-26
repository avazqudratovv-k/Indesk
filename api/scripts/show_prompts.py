"""Print the Owl and Beaver prompts for a CSV, exactly as a run would build them. NO network call,
no key, no database: read the real prompt text before spending credit.

    docker compose run --rm api python scripts/show_prompts.py tests/fixtures/demo_ridership.csv
    ... show_prompts.py FILE.csv --question "your question" --random-nonce

The Beaver prompt needs a plan; Owl's real plan comes from a model, so this builds an example plan
from the first text column and the last number column. Everything else is what a run sends."""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `app` imports from /app/scripts

from app.core.config import load_limits  # noqa: E402
from app.runs.ask_schemas import OwlPlan  # noqa: E402
from app.runs.profile import CsvProfile, ProfileFailed, build_profile  # noqa: E402
from app.runs.prompts import (  # noqa: E402
    BEAVER_PROMPT_VERSION,
    OWL_PROMPT_VERSION,
    build_beaver_prompt,
    build_owl_prompt,
    new_nonce,
)

DEFAULT_QUESTION = "Which stations grew fastest since 2019?"
FIXED_NONCE = "0123456789abcdef"  # readable and repeatable; --random-nonce shows a real one


def example_plan(profile: CsvProfile) -> OwlPlan:
    text = [c.name for c in profile.columns if c.dtype == "text"][:1]
    number = [c.name for c in profile.columns if c.dtype in ("integer", "float")][-1:]
    return OwlPlan(
        task="rank", columns=[*text, *number], group_by=text, metric=number[0] if number else None,
        aggregation="sum" if number else "count", time_column=None, order="desc", top_n=5,
    )  # fmt: skip


def main(argv: list[str], out: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(description="Print the Owl and Beaver prompts for a CSV.")
    parser.add_argument("csv", type=Path)
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--random-nonce", action="store_true")
    args = parser.parse_args(argv)
    try:
        data = args.csv.read_bytes()
    except OSError:
        out("Could not read the file.")
        return 1
    limits = load_limits()
    profile = build_profile(data, limits)
    if isinstance(profile, ProfileFailed):
        out(f"This file would end the run as input_unusable ({profile.error.value}).")
        return 1
    nonce = new_nonce() if args.random_nonce else FIXED_NONCE
    owl = build_owl_prompt(args.question, profile, nonce=nonce)
    beaver = build_beaver_prompt(args.question, example_plan(profile), profile, nonce=nonce)
    out("NOTHING IS SENT ANYWHERE. These are the prompts a run would build.\n")
    for title, pair in (
        (f"OWL {OWL_PROMPT_VERSION}", owl),
        (f"BEAVER {BEAVER_PROMPT_VERSION}", beaver),
    ):
        out(f"======== {title}: SYSTEM ({len(pair.system)} chars) ========\n{pair.system}\n")
        out(f"======== {title}: PROMPT ({len(pair.prompt)} chars) ========\n{pair.prompt}\n")
    out("(The Beaver plan above is an EXAMPLE; a real run uses Owl's answer.)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
