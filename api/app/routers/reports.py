from fastapi import APIRouter

from app.routers.deps import CurrentUser, Db
from app.schemas.reports import ReportDetail
from app.services import reports as service

router = APIRouter(prefix="/reports", tags=["reports"])


# exclude_unset: an evidence payload carries only the keys that were stored (never `code: null`).
@router.get("/{report_id}", response_model=ReportDetail, response_model_exclude_unset=True)
def get_report(report_id: str, db: Db, user: CurrentUser) -> ReportDetail:
    """The report with its claims and evidence. Owner only; the same 404 for anyone else."""
    return service.get_report_detail(db, user, report_id)
