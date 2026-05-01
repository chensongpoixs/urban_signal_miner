"""Pipeline router — one-click full pipeline trigger."""
from fastapi import APIRouter, Query
from api.services.pipeline_service import run_pipeline, get_pipeline_status
from api.models.common import ApiResponse
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(prefix="/api/v1", tags=["pipeline"])

executor = ThreadPoolExecutor(max_workers=1)


@router.get("/pipeline/status")
async def pipeline_status():
    """Get current pipeline status (running step, progress, results)."""
    status = get_pipeline_status()
    return ApiResponse(success=True, data=status)


@router.post("/pipeline")
async def trigger_pipeline(
    classify_limit: int = Query(0, ge=0, description="Limit classify count, 0=all"),
    skip_classify: bool = Query(False, description="Skip AI classify step"),
):
    """Trigger the full pipeline: sync → classify → index → report."""
    future = executor.submit(run_pipeline, classify_limit, skip_classify)
    # Don't wait — return immediately with current status
    return ApiResponse(
        success=True,
        data={
            "message": "流水线已启动，请通过 GET /pipeline/status 轮询进度",
            "status": "started",
        },
    )
