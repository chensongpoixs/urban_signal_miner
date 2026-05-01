"""Dashboard models."""
from typing import Optional
from pydantic import BaseModel


class StatCard(BaseModel):
    label: str
    value: str
    change: Optional[str] = None  # e.g. "+12%", "-3%"


class DailyCount(BaseModel):
    date: str
    count: int
    avg_importance: float


class DomainDist(BaseModel):
    domain: str
    count: int
    percentage: float


class CityDist(BaseModel):
    city: str
    count: int
    percentage: float


class SourceDist(BaseModel):
    source: str
    source_name: str
    count: int
    avg_importance: Optional[float] = None


class ReportPreview(BaseModel):
    id: int
    report_type: str
    period_key: str
    news_count: Optional[int] = 0
    key_findings: Optional[str] = ""
    created_at: Optional[str] = ""


class DashboardStats(BaseModel):
    stats: list[StatCard]
    news_by_day: list[DailyCount]
    top_domains: list[DomainDist]
    top_cities: list[CityDist]
    top_sources: list[SourceDist]
    importance_distribution: dict[str, int]
    recent_reports: list[ReportPreview]
