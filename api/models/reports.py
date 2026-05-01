"""Report models."""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class ReportIndexItem(BaseModel):
    id: int
    report_type: str
    period_key: str
    file_path: str
    news_count: Optional[int] = 0
    key_findings: Optional[str] = ""
    created_at: Optional[str] = ""


class ReportSection(BaseModel):
    id: str
    title: str
    type: str = "text"  # text, ranked_list, domain_summary, table, chart, causal_chain
    content: Optional[str] = ""
    items: Optional[list[dict[str, Any]]] = None
    metadata: Optional[dict[str, Any]] = None


class ReportMetadata(BaseModel):
    title: Optional[str] = ""
    period_start: Optional[str] = ""
    period_end: Optional[str] = ""
    generated_at: Optional[str] = ""
    news_count: Optional[int] = 0
    method_note: Optional[str] = ""


class ReportDetail(BaseModel):
    report_type: str
    period_key: str
    file_path: Optional[str] = ""
    metadata: ReportMetadata
    sections: list[ReportSection]
    key_findings: Optional[str] = ""
    raw_markdown: Optional[str] = ""


class ReportGenerateRequest(BaseModel):
    report_type: str = Field(..., pattern="^(weekly|monthly|quarterly|special_city_compare|special_causal_chain)$")
    period_key: Optional[str] = None
    force_regenerate: bool = False
    # For causal_chain
    topic: Optional[str] = None
    # For city_compare
    months: Optional[int] = Field(default=3, ge=1, le=24)
    # For quarterly
    offset: Optional[int] = Field(default=0)


class GenerateTaskStatus(BaseModel):
    task_id: str
    status: str  # pending, running, completed, failed
    progress: Optional[int] = 0
    message: str = ""
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = ""
    completed_at: Optional[str] = ""


class AvailablePeriod(BaseModel):
    period_key: str
    label: str
    has_report: bool = False
