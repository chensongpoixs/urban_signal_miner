"""Sync router — trigger data sync from ModelScope."""
from fastapi import APIRouter
from api.services.sync_service import run_sync, get_sync_status
from api.models.common import ApiResponse
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(prefix="/api/v1", tags=["sync"])

executor = ThreadPoolExecutor(max_workers=1)


@router.get("/sync/status")
async def sync_status():
    """Get current sync state (running + last result)."""
    status = get_sync_status()
    return ApiResponse(success=True, data=status)


@router.post("/sync")
async def trigger_sync():
    """Trigger news data sync from ModelScope (git pull)."""
    # Run sync in thread to avoid blocking the event loop
    future = executor.submit(run_sync)
    result = future.result(timeout=180)
    return ApiResponse(success=result["status"] != "error", data=result)
