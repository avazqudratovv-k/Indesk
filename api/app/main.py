from fastapi import FastAPI

from app.core.errors import register_error_handlers
from app.routers import health

app = FastAPI(title="Indesk API", docs_url=None, redoc_url=None, openapi_url=None)
register_error_handlers(app)
app.include_router(health.router, prefix="/api")
