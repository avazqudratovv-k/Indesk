from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.routers.deps import CurrentUser, Db, DeleteLimit, ReadLimit
from app.schemas.reports import ReportDetail, ReportPage
from app.services import reports as service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=ReportPage, dependencies=[ReadLimit])
def list_reports(
    db: Db,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=service.MAX_LIST_LIMIT)] = service.DEFAULT_LIST_LIMIT,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> ReportPage:
    """The caller's own reports, newest first, metadata only."""
    return service.list_reports(db, user, limit=limit, cursor=cursor)


# exclude_unset: an evidence payload carries only the keys that were stored (never `code: null`).
@router.get(
    "/{report_id}",
    response_model=ReportDetail,
    response_model_exclude_unset=True,
    dependencies=[ReadLimit],
)
def get_report(report_id: str, db: Db, user: CurrentUser) -> ReportDetail:
    """The report with its claims and evidence. Owner only; the same 404 for anyone else."""
    return service.get_report_detail(db, user, report_id)


@router.delete("/{report_id}", status_code=204, dependencies=[DeleteLimit])
def delete_report(report_id: str, db: Db, user: CurrentUser) -> Response:
    """Delete the whole run behind the report. Owner only; no refund of any quota."""
    service.delete_report(db, user, report_id)
    return Response(status_code=204)
