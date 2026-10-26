from fastapi import APIRouter, Response

from app.example import load_example
from app.schemas.reports import ReportDetail

router = APIRouter(prefix="/example", tags=["example"])

CACHE_CONTROL = "public, max-age=300"


# No login, no database, no model, no rate limiter: a file already validated at startup.
@router.get("", response_model=ReportDetail, response_model_exclude_unset=True)
def get_example(response: Response) -> ReportDetail:
    """The cached example report, the same for everyone."""
    response.headers["Cache-Control"] = CACHE_CONTROL
    return load_example()
