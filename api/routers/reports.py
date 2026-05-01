"""Reports router — list, get, generate, delete."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from api.services.report_service import report_service
from api.models.reports import ReportGenerateRequest
from api.models.common import ApiResponse

router = APIRouter(prefix="/api/v1", tags=["reports"])


@router.get("/reports")
async def list_reports(
    report_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    data = report_service.list_reports(
        report_type=report_type,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(success=True, data=data)


@router.get("/reports/{report_type}/{period_key:path}")
async def get_report(report_type: str, period_key: str):
    result = report_service.get_report(report_type, period_key)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Report not found: {report_type}/{period_key}")
    return ApiResponse(success=True, data=result)


@router.post("/reports/generate")
async def generate_report(request: ReportGenerateRequest):
    result = report_service.request_generate(request)
    return ApiResponse(success=True, data=result)


@router.delete("/reports/{report_type}/{period_key:path}")
async def delete_report(report_type: str, period_key: str):
    deleted = report_service.delete_report(report_type, period_key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Report not found: {report_type}/{period_key}")
    return ApiResponse(success=True, data={"deleted": True})


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    status = report_service.get_task_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return ApiResponse(success=True, data=status)


@router.get("/reports/{report_type}/{period_key:path}/exists")
async def check_report_exists(report_type: str, period_key: str):
    from utils.db import check_report_exists
    exists = check_report_exists(report_type, period_key)
    return ApiResponse(success=True, data={"exists": exists})
