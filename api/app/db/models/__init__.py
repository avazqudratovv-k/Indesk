"""Importing this package registers every table on Base.metadata (Alembic and tests need it)."""

from app.db.models.reports import Claim, Evidence, Report
from app.db.models.runs import AgentStep, Run, RunFile
from app.db.models.uploads import Upload
from app.db.models.usage import AiCall, AuditLog, UsageDaily, UsageEvent
from app.db.models.users import RefreshToken, User

__all__ = [
    "AgentStep",
    "AiCall",
    "AuditLog",
    "Claim",
    "Evidence",
    "RefreshToken",
    "Report",
    "Run",
    "RunFile",
    "Upload",
    "UsageDaily",
    "UsageEvent",
    "User",
]
