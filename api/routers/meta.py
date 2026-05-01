"""Meta router — domains, cities, sources, report types."""
from fastapi import APIRouter
from utils.config_loader import get_domains, get_cities, get_source_weights
from api.services.report_service import report_service
from api.models.common import ApiResponse

router = APIRouter(prefix="/api/v1/meta", tags=["meta"])


@router.get("/domains")
async def list_domains():
    domains = get_domains()
    return ApiResponse(success=True, data=domains)


@router.get("/cities")
async def list_cities():
    cities = get_cities()
    return ApiResponse(success=True, data=cities)


@router.get("/sources")
async def list_sources():
    sources = get_source_weights()
    result = [{"source": k, **v} for k, v in sources.items()]
    return ApiResponse(success=True, data=result)


@router.get("/report-types")
async def list_report_types():
    types = [
        {"key": "weekly", "label": "Weekly Report", "description": "Weekly trend analysis and top events"},
        {"key": "monthly", "label": "Monthly Report", "description": "Monthly trend confirmation and cross-domain analysis"},
        {"key": "quarterly", "label": "Quarterly Deep Analysis", "description": "2-phase deep analysis with causal chains and opportunity maps"},
        {"key": "special_city_compare", "label": "City Comparison", "description": "6-city competitive analysis"},
        {"key": "special_causal_chain", "label": "Causal Chain", "description": "Topic-based causal chain tracking"},
    ]
    return ApiResponse(success=True, data=types)


@router.get("/available-periods/{report_type}")
async def get_available_periods(report_type: str):
    periods = report_service.get_available_periods(report_type)
    return ApiResponse(success=True, data=periods)
