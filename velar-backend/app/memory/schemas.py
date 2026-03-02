"""Pydantic schemas for the /memory CRUD API.

FactResponse is the standard output shape for all read endpoints.
FactCreate is used for POST (manual fact creation).
FactUpdate is used for PATCH (creates superseding version).
"""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class FactCreate(BaseModel):
    """Request body for POST /api/v1/memory — manually add a fact."""
    category: str = Field(..., description="Category: health, food, social, place, habit, work, preference")
    key: str = Field(..., min_length=1, max_length=100, description="Attribute name in snake_case")
    value: str = Field(..., min_length=1, max_length=2000, description="Fact value as stated")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="1.0 for user-stated facts")


class FactUpdate(BaseModel):
    """Request body for PATCH /api/v1/memory/{id} — update creates superseding version."""
    value: str = Field(..., min_length=1, max_length=2000, description="Updated fact value")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class FactResponse(BaseModel):
    """Standard output for all /memory endpoints."""
    id: uuid.UUID
    category: str
    key: str
    value: str
    source: str
    confidence: float
    valid_from: datetime
    valid_until: Optional[datetime] = None
    superseded_by: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FactListResponse(BaseModel):
    """Paginated list of facts."""
    facts: list[FactResponse]
    total: int
    page: int
    page_size: int


class MemorySummaryResponse(BaseModel):
    """Claude-synthesized summary of all stored facts."""
    summary: str
    fact_count: int
