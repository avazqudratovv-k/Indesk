from app.core.enums import Plan
from app.schemas.common import ApiModel


class Usage(ApiModel):
    """GET /api/usage. Counts and the plan name only: no model name, no tokens, no cost (#74).
    The free-run counts are null when the plan has no free-run limit."""

    plan: Plan
    free_runs_total: int | None
    free_runs_used: int | None
    free_runs_left: int | None
