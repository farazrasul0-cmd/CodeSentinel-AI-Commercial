"""Pydantic schemas for SOC2 Audit Logging API."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    user_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    details: dict[str, Any]
    ip_address: str | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    limit: int
    offset: int
