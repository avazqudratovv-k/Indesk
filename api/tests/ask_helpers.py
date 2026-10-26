"""Builders for the Ask tests: an in-memory storage, a client that keeps the prompts it was sent,
a rig with the REAL model chains and the Ask flow, canned model answers. Fake gateway client, fake
sandbox, no network."""

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.ai.caps import SessionFactory
from app.ai.client import ClientResult
from app.ai.config import load_model_chains
from app.core.enums import SandboxErrorCode
from app.db.models import Upload
from app.runs.ask_flow import AskFlow
from app.sandbox_client import SandboxOk
from app.storage import StorageError
from tests.ai_helpers import limits_with, make_gateway
from tests.fake_model_client import API_KEY, FakeClient, Step, ok
from tests.runs_helpers import FakeSandbox, Rig, World, make_rig, sandbox_error

FIXTURE = Path(__file__).parent / "fixtures" / "demo_ridership.csv"
CSV_GOOD = FIXTURE.read_bytes()
NONCE = "n0nce0123456789a"

PLAN: dict[str, Any] = {
    "task": "rank",
    "columns": ["station", "riders"],
    "group_by": ["station"],
    "metric": "riders",
    "aggregation": "sum",
    "time_column": None,
    "order": "desc",
    "top_n": 5,
}
CODE_OK = (
    "g = df.groupby('station')['riders'].sum().sort_values(ascending=False).head(5)\n"
    "result = {'columns': ['station', 'riders'], "
    "'rows': [[k, int(v)] for k, v in g.items()], 'rows_used': len(df)}"
)
RESULT_OK: dict[str, Any] = {
    "columns": ["station", "riders"],
    "rows": [["Synthetic Station 07", 123456], ["Synthetic Station 02", 100000]],
    "rows_used": 204,
}


def plan_answer(tokens_in: int = 10, tokens_out: int = 5, **override: Any) -> Step:
    return ok(json.dumps({**PLAN, **override}), tokens_in, tokens_out)


def code_answer(code: str = CODE_OK, tokens_in: int = 10, tokens_out: int = 5) -> Step:
    return ok(json.dumps({"code": code}), tokens_in, tokens_out)


def sandbox_ok(result: Any = None) -> SandboxOk:
    return SandboxOk(result=RESULT_OK if result is None else result, duration_ms=1)


class MemoryStorage:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}
        self.reads = 0

    def put(self, data: bytes) -> str:
        key = uuid.uuid4().hex
        self.data[key] = data
        return key

    def get(self, key: str) -> bytes:
        self.reads += 1
        try:
            return self.data[key]
        except KeyError:
            raise StorageError("read failed") from None

    def delete(self, key: str) -> None:
        self.data.pop(key, None)


@dataclass
class CapturingClient(FakeClient):
    """A FakeClient that also keeps what it was asked, so a test can read the prompts."""

    prompts: list[str] = field(default_factory=list)
    systems: list[str] = field(default_factory=list)

    def generate(self, **kw: Any) -> ClientResult:
        self.prompts.append(kw["prompt"])
        self.systems.append(kw["system"] or "")
        return super().generate(**kw)


def put_csv(
    factory: SessionFactory, world: World, storage: MemoryStorage, csv: bytes | list[bytes]
) -> None:
    """Store `csv` (one per upload) under each upload's storage key."""
    blobs = csv if isinstance(csv, list) else [csv] * len(world.upload_ids)
    with factory() as db:
        for upload_id, blob in zip(world.upload_ids, blobs, strict=True):
            key = db.scalar(select(Upload.storage_key).where(Upload.id == upload_id))
            assert key is not None
            storage.data[key] = blob


def ask_rig(
    factory: SessionFactory,
    world: World,
    *steps: Step,
    csv: bytes | list[bytes] = CSV_GOOD,
    sandbox: list[Any] | None = None,
    api_key: str | None = API_KEY,
    **limit_overrides: int,
) -> tuple[Rig, CapturingClient, MemoryStorage]:
    limits = limits_with(**limit_overrides)
    client = CapturingClient(list(steps))
    gateway = make_gateway(
        factory, client, chains=load_model_chains(), limits=limits, api_key=api_key
    )
    fake_sandbox = FakeSandbox(*(sandbox or []))
    rig = make_rig(
        factory, AskFlow(limits, nonce=lambda: NONCE), sandbox=fake_sandbox, limits=limits,
        gateway=gateway,
    )  # fmt: skip
    storage = MemoryStorage()
    rig.deps.storage = storage
    rig.client = client
    put_csv(factory, world, storage, csv)
    return rig, client, storage


def forbidden() -> Any:
    return sandbox_error(SandboxErrorCode.FORBIDDEN)
