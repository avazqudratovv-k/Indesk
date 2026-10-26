from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.core.bodylimit import MULTIPART_OVERHEAD, BodyLimitMiddleware
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.routers import auth, health, me, runs, uploads
from app.routers.deps import check_write_request


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_settings()  # a bad setting (for example a short AUTH_SECRET in production) stops startup
    yield


# The write-request check is app-wide, so a route added later cannot forget it.
app = FastAPI(
    title="Indesk API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
    dependencies=[Depends(check_write_request)],
)
register_error_handlers(app)
app.add_middleware(
    BodyLimitMiddleware,
    method="POST",
    path="/api/uploads",
    limit=lambda: get_settings().limits.max_file_bytes + MULTIPART_OVERHEAD,
)
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(me.router, prefix="/api")
app.include_router(uploads.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
