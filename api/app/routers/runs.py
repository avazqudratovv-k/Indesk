import logging
import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.ai.caps import SessionFactory
from app.core import clock, ratelimit
from app.core.enums import RunOutcome, RunReason, RunStatus
from app.core.errors import AppError, ErrorCode
from app.db.session import get_engine
from app.jobs.runs import enqueue_run
from app.routers.deps import AppSettings, CurrentUser, Db, IpHash, RedisDep
from app.runs import sse, store, streams
from app.runs.trace import stopped_line
from app.schemas.runs import RunCreate, RunCreated, RunView
from app.services import runs as service

logger = logging.getLogger("indesk.runs")
router = APIRouter(prefix="/runs", tags=["runs"])

Enqueue = Callable[[uuid.UUID], None]


def get_enqueue(settings: AppSettings, redis: RedisDep) -> Enqueue:
    def enqueue(run_id: uuid.UUID) -> None:
        enqueue_run(redis, run_id, settings.limits.run_job_timeout_seconds)

    return enqueue


def get_session_factory(settings: AppSettings) -> SessionFactory:
    """Short-lived sessions for the event stream, which must not hold the request's connection."""
    engine = get_engine(settings.database_url.get_secret_value())
    return lambda: Session(engine)


EnqueueDep = Annotated[Enqueue, Depends(get_enqueue)]
FactoryDep = Annotated[SessionFactory, Depends(get_session_factory)]


@router.post("", status_code=202, response_model=RunCreated)
def create_run(
    body: RunCreate,
    db: Db,
    settings: AppSettings,
    user: CurrentUser,
    ip_hash: IpHash,
    redis: RedisDep,
    enqueue: EnqueueDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> RunCreated:
    # Before anything is counted or stored. Off by default; the owner turns it on.
    if settings.email_verification_required and user.email_verified_at is None:
        raise AppError(403, ErrorCode.EMAIL_NOT_VERIFIED)
    # Every request of a signed-in user counts, accepted or not. Redis down: refused (503).
    ratelimit.hit(redis, f"rl:run:{user.id}", settings.limits.runs_per_hour, ratelimit.RUN_WINDOW)
    key = service.check_idempotency_key(idempotency_key)
    run, created = service.create_run(
        db, redis, settings.limits, user, body, idempotency_key=key, ip_hash=ip_hash
    )
    if created:
        try:
            enqueue(run.id)
        except Exception:  # noqa: BLE001  # the queue is down: end the run now, free its uploads
            logger.error("run %s could not be queued code=%s", run.id, "RUN_ENQUEUE_FAILED")
            store.finish_run(
                db, run.id, expected=RunStatus.QUEUED, outcome=RunOutcome.FAILED,
                reason=RunReason.INTERNAL_ERROR, final=stopped_line(RunReason.INTERNAL_ERROR),
                now=clock.utcnow(),
            )  # fmt: skip
            service.forget_key(redis, user.id, key)
            raise AppError(503, ErrorCode.NOT_READY) from None
    return RunCreated(id=str(run.id), status=run.status)


@router.get("/active", response_model=RunView, responses={204: {"description": "No active run"}})
def get_active_run(db: Db, user: CurrentUser) -> RunView | Response:
    run = service.get_active_run(db, user)
    if run is None:
        return Response(status_code=204)
    return service.run_view(db, run)


@router.get("/{run_id}", response_model=RunView)
def get_run(run_id: str, db: Db, user: CurrentUser) -> RunView:
    return service.run_view(db, service.get_run(db, user, run_id))


@router.get("/{run_id}/events", response_model=None)
def run_events(
    run_id: str,
    request: Request,
    db: Db,
    settings: AppSettings,
    user: CurrentUser,
    redis: RedisDep,
    factory: FactoryDep,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> Response:
    run = service.get_run(db, user, run_id)  # auth and ownership first, as a normal JSON error
    run_uuid, owner = run.id, user.id
    after = sse.parse_last_event_id(last_event_id)
    finished, top = sse.read_head(factory, run_uuid)
    db.close()  # a stream must not hold the request's connection for minutes
    if finished and after > top:
        return Response(status_code=204)  # the client already has `done`: tell EventSource to stop

    stream_id = uuid.uuid4().hex
    streams.acquire(redis, owner, stream_id, settings.limits.sse_streams_per_user)

    def on_ping() -> None:
        streams.refresh(redis, owner, stream_id)

    def on_close() -> None:
        streams.release(redis, owner, stream_id)

    body = sse.stream_events(
        request=request, factory=factory, limits=settings.limits, run_id=run_uuid,
        after=after, on_ping=on_ping, on_close=on_close,
    )  # fmt: skip
    return StreamingResponse(
        body,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        background=BackgroundTask(on_close),
    )
