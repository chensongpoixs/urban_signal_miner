"""News search models."""
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    id: str
    date: str
    source: str
    source_name: Optional[str] = ""
    source_url: Optional[str] = ""
    rank: Optional[int] = 0
    title: str
    domain: list[str] = []
    cities: list[str] = []
    entities: list[dict] = []
    tags: list[str] = []
    importance: int = 0
    ai_summary: Optional[str] = ""
    ai_why_matters: Optional[str] = ""
    file_path: Optional[str] = ""
    word_count: Optional[int] = 0


class NewsSearchParams(BaseModel):
    keyword: Optional[str] = None
    domain: Optional[str] = None
    city: Optional[str] = None
    source: Optional[str] = None
    min_importance: Optional[int] = Field(default=0, ge=0, le=5)
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = Field(default="date", pattern="^(date|importance)$")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
