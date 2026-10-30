"""GET /api/runs/{id}/events: order, resume, ping, close, ownership, limits, disconnects."""

import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import Connection

from app.ai.caps import SessionFactory
from app.core.config import Settings, load_limits
from app.core.enums import (
    AgentKey,
    RunOutcome,
    RunReason,
    RunStatus,
    StepState,
    TraceKey,
)
from app.core.errors import AppError
from app.db.models import Run
from app.main import app
from app.routers.runs import get_enqueue, get_session_factory
from app.runs import sse, store, streams
from app.runs.trace import stopped_line
from app.schemas.events import DoneEvent, StepEvent
from tests.ai_helpers import factory_for
from tests.runs_helpers import World, line
from tests.test_auth import MakeClient
from tests.test_runs_api import body, code, new_upload
from tests.test_uploads import settings_for, signed_in

M = AgentKey.MANAGER
NOW = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)


@pytest.fixture
def factory(db_connection: Connection) -> SessionFactory:
    return factory_for(db_connection)


@pytest.fixture(autouse=True)
def _wire(factory: SessionFactory) -> None:
    app.dependency_overrides[get_enqueue] = lambda: lambda run_id: None
    app.dependency_overrides[get_session_factory] = lambda: factory


def fast(tmp_path: Path, **limits: Any) -> Settings:
    return settings_for(
        tmp_path,
        sse_poll_seconds=0.02,
        sse_ping_seconds=0.05,
        sse_max_seconds=0.4,
        **limits,
    )


@pytest.fixture
def alice(make_client: MakeClient, tmp_path: Path) -> TestClient:
    return signed_in(make_client, fast(tmp_path), "alice@example.com", 10)


@pytest.fixture
def bob(make_client: MakeClient, tmp_path: Path) -> TestClient:
    return signed_in(make_client, fast(tmp_path), "bob@example.com", 11)


def my_run(client: TestClient, factory: SessionFactory) -> World:
    """A running run owned by the signed-in user, made through the API so the owner is real."""
    run_id = client.post("/api/runs", json=body(new_upload(client))).json()["id"]
    with factory() as db:
        run = db.get(Run, uuid.UUID(run_id))
        assert run is not None
        user_id, uploads = run.user_id, ()
    store_claim(factory, uuid.UUID(run_id))
    return World(user_id, uuid.UUID(run_id), uploads)


def store_claim(factory: SessionFactory, run_id: uuid.UUID) -> None:
    with factory() as db:
        assert store.claim_run(db, run_id, NOW)


def add(factory: SessionFactory, world: World, n: int = 1, key: TraceKey = TraceKey.PLAN) -> None:
    for _ in range(n):
        with factory() as db:
            store.append_event(
                db,
                world.run_id,
                line(M, StepState.RUNNING, key, tok=5),
                attempt=1,
                payload=None,
                now=NOW,
            )


def finish(factory: SessionFactory, world: World, ok: bool = True) -> None:
    with factory() as db:
        if ok:
            args: dict[str, Any] = {
                "outcome": RunOutcome.ANSWERED, "reason": None,
                "final": line(M, StepState.DONE, TraceKey.READY),
            }  # fmt: skip
        else:
            args = {
                "outcome": RunOutcome.FAILED, "reason": RunReason.MODEL_BUSY,
                "final": stopped_line(RunReason.MODEL_BUSY),
            }  # fmt: skip
        assert store.finish_run(db, world.run_id, expected=RunStatus.RUNNING, now=NOW, **args)


def parse(text: str) -> tuple[list[dict[str, Any]], int]:
    """(events, number of ping comments)"""
    events, pings = [], 0
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        if block.startswith(":"):
            pings += 1
            continue
        fields = dict(part.split(": ", 1) for part in block.split("\n"))
        events.append(
            {"id": int(fields["id"]), "event": fields["event"], "data": json.loads(fields["data"])}
        )
    return events, pings


def stream_slots(settings: Settings, user_id: uuid.UUID) -> int:
    redis = Redis.from_url(settings.redis_url.get_secret_value())
    return int(redis.zcard(f"sse:{user_id}"))


# ---- order, resume, close ----


def test_events_arrive_in_order_and_the_stream_closes_on_done(
    alice: TestClient, factory: SessionFactory
) -> None:
    world = my_run(alice, factory)
    add(factory, world, 3)
    finish(factory, world)
    response = alice.get(f"/api/runs/{world.run_id}/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"
    events, _ = parse(response.text)
    assert [(e["id"], e["event"]) for e in events] == [
        (1, "step"), (2, "step"), (3, "step"), (4, "step"), (5, "done"),
    ]  # fmt: skip
    for e in events[:-1]:
        step = StepEvent.model_validate(e["data"])
        assert step.seq == e["id"] and step.run_id == str(world.run_id)
        assert set(e["data"]) == set(StepEvent.model_fields)  # nothing else travels
    assert events[-2]["data"]["key"] == "ready"
    done = DoneEvent.model_validate(events[-1]["data"])
    assert (done.outcome, done.reason, done.report_id) == (RunOutcome.ANSWERED, None, None)


def test_a_failed_run_says_why_with_a_code(alice: TestClient, factory: SessionFactory) -> None:
    world = my_run(alice, factory)
    finish(factory, world, ok=False)
    events, _ = parse(alice.get(f"/api/runs/{world.run_id}/events").text)
    assert (
        events[-1]["data"]["outcome"] == "failed" and events[-1]["data"]["reason"] == "model_busy"
    )
    assert events[-2]["data"]["args"] == {"reason": "model_busy"}


def test_resume_with_last_event_id_has_no_duplicates_and_no_gaps(
    alice: TestClient, factory: SessionFactory
) -> None:
    world = my_run(alice, factory)
    add(factory, world, 5)
    finish(factory, world)
    url = f"/api/runs/{world.run_id}/events"
    full, _ = parse(alice.get(url).text)
    assert len(full) == 7  # five lines, the closing line, done
    for last in range(0, len(full) + 1):  # 7 = the client already has done: 204, empty
        resumed, _ = parse(alice.get(url, headers={"Last-Event-ID": str(last)}).text)
        got = [e["id"] for e in resumed]
        assert got == [e["id"] for e in full if e["id"] > last], last  # exactly the newer ones
    # A dropped connection after event 3: the two halves join without a gap or a repeat.
    first = [e["id"] for e in full[:3]]
    rest = [e["id"] for e in parse(alice.get(url, headers={"Last-Event-ID": "3"}).text)[0]]
    assert first + rest == [e["id"] for e in full]


def test_a_client_that_already_has_done_gets_204_so_it_stops_reconnecting(
    alice: TestClient, factory: SessionFactory
) -> None:
    world = my_run(alice, factory)
    add(factory, world, 2)
    finish(factory, world)  # lines 1..3, done is id 4
    url = f"/api/runs/{world.run_id}/events"
    assert alice.get(url, headers={"Last-Event-ID": "3"}).text.count("event: done") == 1
    gone = alice.get(url, headers={"Last-Event-ID": "4"})
    assert gone.status_code == 204 and gone.text == ""


@pytest.mark.parametrize("raw", ["abc", "-5", "", "99999999999999999999", "1e3", " "])
def test_a_garbage_last_event_id_means_start_from_the_beginning(
    alice: TestClient, factory: SessionFactory, raw: str
) -> None:
    world = my_run(alice, factory)
    add(factory, world, 2)
    finish(factory, world)
    response = alice.get(f"/api/runs/{world.run_id}/events", headers={"Last-Event-ID": raw})
    assert response.status_code == 200
    assert [e["id"] for e in parse(response.text)[0]] == [1, 2, 3, 4]


def test_a_live_stream_pings_and_ends_at_its_time_limit(
    alice: TestClient, factory: SessionFactory, tmp_path: Path
) -> None:
    world = my_run(alice, factory)
    add(factory, world, 1)  # never finished
    events, pings = parse(alice.get(f"/api/runs/{world.run_id}/events").text)
    assert [e["id"] for e in events] == [1]  # no done: the run is not over
    assert pings >= 2
    assert stream_slots(fast(tmp_path), world.user_id) == 0  # the slot is given back


def test_the_slot_is_given_back_after_a_normal_finish(
    alice: TestClient, factory: SessionFactory, tmp_path: Path
) -> None:
    world = my_run(alice, factory)
    finish(factory, world)
    alice.get(f"/api/runs/{world.run_id}/events")
    assert stream_slots(fast(tmp_path), world.user_id) == 0


# ---- ownership ----


def test_another_user_gets_the_same_404_as_a_missing_run(
    alice: TestClient, bob: TestClient, factory: SessionFactory
) -> None:
    world = my_run(alice, factory)
    add(factory, world, 1)
    foreign = bob.get(f"/api/runs/{world.run_id}/events")
    missing = bob.get(f"/api/runs/{uuid.uuid4()}/events")
    code(foreign, 404, "NOT_FOUND")
    assert foreign.json() == missing.json()
    assert "plan" not in foreign.text
    code(bob.get("/api/runs/not-a-uuid/events"), 404, "NOT_FOUND")


# ---- per-user stream limit ----


def test_too_many_streams_are_refused(
    make_client: MakeClient, tmp_path: Path, factory: SessionFactory
) -> None:
    settings = fast(tmp_path, sse_streams_per_user=1)
    client = signed_in(make_client, settings, "carol@example.com", 12)
    world = my_run(client, factory)
    redis = Redis.from_url(settings.redis_url.get_secret_value())
    streams.acquire(redis, world.user_id, "another-tab", 1)
    refused = client.get(f"/api/runs/{world.run_id}/events")
    code(refused, 429, "TOO_MANY_STREAMS")
    assert refused.headers["Retry-After"] == "5"
    streams.release(redis, world.user_id, "another-tab")
    finish(factory, world)
    assert client.get(f"/api/runs/{world.run_id}/events").status_code == 200


def test_stream_slots_expire_and_redis_down_fails_closed() -> None:
    redis = Redis.from_url(settings_for(Path("/tmp")).redis_url.get_secret_value())  # noqa: S108
    user = uuid.uuid4()
    redis.zadd(f"sse:{user}", {"crashed": 1.0})  # a stream that died long ago
    streams.acquire(redis, user, "fresh", 1)  # the dead slot does not count
    with pytest.raises(AppError) as full:
        streams.acquire(redis, user, "second", 1)
    assert full.value.status == 429
    redis.delete(f"sse:{user}")
    nowhere = Redis.from_url("redis://127.0.0.1:1/15", socket_connect_timeout=0.2)
    with pytest.raises(AppError) as down:
        streams.acquire(nowhere, user, "x", 3)
    assert (down.value.status, down.value.code.value) == (503, "NOT_READY")


# ---- the generator itself: live writes, slow and vanishing clients ----


class FakeRequest:
    def __init__(self, gone_after: int | None = None) -> None:
        self.calls = 0
        self.gone_after = gone_after

    async def is_disconnected(self) -> bool:
        self.calls += 1
        return self.gone_after is not None and self.calls > self.gone_after


def generator(
    factory: SessionFactory,
    world: World,
    request: Any,
    after: int = 0,
    closed: list[int] | None = None,
) -> Any:
    return sse.stream_events(
        request=request, factory=factory,
        limits=load_limits().model_copy(
            update={"sse_poll_seconds": 0.01, "sse_ping_seconds": 0.03, "sse_max_seconds": 5.0}
        ),
        run_id=world.run_id, after=after, on_ping=lambda: None,
        on_close=lambda: (closed if closed is not None else []).append(1),
    )  # fmt: skip


def test_a_live_stream_delivers_lines_written_while_it_runs_even_to_a_slow_client(
    alice: TestClient, factory: SessionFactory
) -> None:
    world = my_run(alice, factory)
    add(factory, world, 1)
    closed: list[int] = []

    async def scenario() -> list[str]:
        agen = generator(factory, world, FakeRequest(), closed=closed)
        got = [await anext(agen)]
        pending = asyncio.ensure_future(anext(agen))
        await asyncio.sleep(0.1)  # nothing new: the poll just waits (and pings)
        add(factory, world, 4)  # the worker writes four more while the client is busy
        got.append(await pending)
        for _ in range(3):
            await asyncio.sleep(0.05)  # a slow reader
            got.append(await anext(agen))
        finish(factory, world)
        async for chunk in agen:
            got.append(chunk)
        return got

    chunks = asyncio.run(scenario())
    ids = [int(c.split("\n")[0][4:]) for c in chunks if c.startswith("id:")]
    assert ids == [1, 2, 3, 4, 5, 6, 7]  # 5 lines, the closing line, then done
    assert chunks[-1].startswith("id: 7\nevent: done")
    assert closed == [1]


def test_a_vanished_client_stops_its_generator_and_gives_the_slot_back(
    alice: TestClient, factory: SessionFactory
) -> None:
    world = my_run(alice, factory)
    add(factory, world, 2)
    closed: list[int] = []

    async def scenario() -> None:
        agen = generator(factory, world, FakeRequest(gone_after=1), closed=closed)
        await anext(agen)
        await anext(agen)
        with pytest.raises(StopAsyncIteration):
            await anext(agen)  # the next loop sees the disconnect and ends

    asyncio.run(scenario())
    assert closed == [1]


def test_cancelling_a_stream_runs_its_cleanup(alice: TestClient, factory: SessionFactory) -> None:
    world = my_run(alice, factory)
    add(factory, world, 1)
    closed: list[int] = []

    async def scenario() -> None:
        agen = generator(factory, world, FakeRequest(), closed=closed)
        await anext(agen)
        await agen.aclose()  # what the server does when the socket drops

    asyncio.run(scenario())
    assert closed == [1]


def test_a_dropped_stream_does_not_stop_the_job(alice: TestClient, factory: SessionFactory) -> None:
    """The job never looks at streams: it keeps writing and finishes after the reader is gone."""
    world = my_run(alice, factory)
    add(factory, world, 1)

    async def scenario() -> None:
        agen = generator(factory, world, FakeRequest())
        await anext(agen)
        await agen.aclose()

    asyncio.run(scenario())
    add(factory, world, 2)
    finish(factory, world)
    events, _ = parse(alice.get(f"/api/runs/{world.run_id}/events").text)
    assert [e["id"] for e in events] == [1, 2, 3, 4, 5]
