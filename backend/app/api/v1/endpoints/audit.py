"""Commercial SOC2 Audit Log Query and Export Endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_role
from app.api.v1.schemas.audit import AuditLogListResponse, AuditLogResponse
from app.domain.enums import UserRole
from app.infrastructure.db.session import get_db_session
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get("/logs", response_model=AuditLogListResponse, summary="Query Organization Audit Trail")
async def list_audit_logs(
    tenant_ctx: Annotated[TenantContext, Depends(require_role(UserRole.ADMIN))],
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
) -> AuditLogListResponse:
    """Lists immutable audit logs for the current tenant organization. Requires ADMIN or OWNER."""
    logs, total = await AuditService.query_logs(
        session=session,
        org_id=tenant_ctx.organization.id,
        limit=limit,
        offset=offset,
        action=action,
    )

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        limit=limit,
        offset=offset,
    )
