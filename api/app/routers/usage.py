from fastapi import APIRouter

from app.core.enums import Plan
from app.routers.deps import AppSettings, CurrentUser, Db
from app.runs import quota
from app.schemas.usage import Usage

router = APIRouter(tags=["usage"])


@router.get("/usage", response_model=Usage)
def get_usage(db: Db, settings: AppSettings, user: CurrentUser) -> Usage:
    """How many of the free runs the signed-in user has used. Decided on the server."""
    plan = Plan(user.plan)
    if plan is not Plan.FREE:
        return Usage(plan=plan, free_runs_total=None, free_runs_used=None, free_runs_left=None)
    total = settings.limits.free_runs
    used = quota.free_runs_used(db, user.id)
    return Usage(
        plan=plan,
        free_runs_total=total,
        free_runs_used=used,
        free_runs_left=max(total - used, 0),
    )
