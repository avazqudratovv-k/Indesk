"""One trace line: what an agent says, as a closed message key plus plain values.

The browser holds the text for each key. Model output and file names never go in: the arguments
a key accepts are listed here, and a string argument must look like a code (lowercase words and
digits), so a sentence cannot be smuggled through. Agents pass only values their code computed."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

from app.core.enums import AgentKey, Bubble, RunReason, StepKind, StepState, TraceKey

TraceValue = str | int | float | bool | None

_CODE: Final = re.compile(r"^[a-z0-9_]{1,40}$")

# The argument names each key may carry.
ALLOWED_ARGS: Final[Mapping[TraceKey, frozenset[str]]] = {
    TraceKey.PLAN: frozenset({"stub", "files"}),
    TraceKey.DISPATCH: frozenset({"stub", "agents"}),
    TraceKey.READ_CSV: frozenset({"stub", "rows", "cols"}),
    TraceKey.RUN_PYTHON: frozenset({"stub", "attempt"}),
    TraceKey.TOP3: frozenset({"stub", "rows"}),
    TraceKey.MERGE: frozenset({"stub"}),
    TraceKey.READY: frozenset({"stub"}),
    TraceKey.STEP_STARTED: frozenset({"attempt"}),
    TraceKey.STEP_FAILED: frozenset({"reason", "attempt"}),
    TraceKey.STOPPED: frozenset({"reason", "stub"}),
    TraceKey.VERIFY: frozenset({"claims", "verified"}),
    # Hound: pages = pages of the document, matched = passages kept, mode = hybrid or keyword
    # (a search by words alone, after the embedding failed); page, score (fused rank) and
    # similarity (raw cosine, left out when the passage came from words alone) = the best passage.
    TraceKey.SEARCH: frozenset({"pages", "matched", "mode"}),
    TraceKey.BEST_PASSAGE: frozenset({"page", "score", "similarity"}),
    TraceKey.SEARCH_FAILED: frozenset({"reason", "attempt"}),
    # keywordOnlySize: reason is the code "document_size". chunksSkipped: chunks not embedded.
    TraceKey.KEYWORD_ONLY_SIZE: frozenset({"reason"}),
    TraceKey.CHUNKS_SKIPPED: frozenset({"count"}),
}


class BadTraceLine(ValueError):
    """A trace line that breaks the rules above. A bug in an agent, never user input."""


@dataclass(frozen=True)
class TraceLine:
    agent: AgentKey
    kind: StepKind
    state: StepState
    key: TraceKey
    args: Mapping[str, TraceValue] = field(default_factory=dict)
    tok: int = 0
    bubble: Bubble | None = None

    def __post_init__(self) -> None:
        if self.tok < 0:
            raise BadTraceLine("tok")
        allowed = ALLOWED_ARGS[self.key]
        for name, value in self.args.items():
            if name not in allowed:
                raise BadTraceLine(f"argument {name} is not allowed for {self.key.value}")
            if isinstance(value, str) and not _CODE.match(value):
                raise BadTraceLine(f"argument {name} is not a code")


def stopped_line(reason: RunReason) -> TraceLine:
    """The closing line of a run that did not end in a normal answer."""
    return TraceLine(
        agent=AgentKey.MANAGER,
        kind=StepKind.SAY,
        state=StepState.DONE,
        key=TraceKey.STOPPED,
        args={"reason": reason.value},
    )
