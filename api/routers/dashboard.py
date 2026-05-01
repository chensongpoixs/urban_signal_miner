"""Dashboard router."""
from fastapi import APIRouter
from api.services.dashboard_service import DashboardService
from api.models.common import ApiResponse

router = APIRouter(prefix="/api/v1", tags=["dashboard"])
service = DashboardService()


@router.get("/dashboard/stats")
async def get_dashboard_stats(days: int = 30):
    data = service.get_stats(days=days)
    return ApiResponse(success=True, data=data)
