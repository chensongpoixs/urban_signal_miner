"""Shared Pydantic models for API responses."""
from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    error: Optional[str] = None


class PaginatedData(BaseModel, Generic[T]):
    items: list[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 20


class PaginatedResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[PaginatedData[T]] = None
    error: Optional[str] = None
