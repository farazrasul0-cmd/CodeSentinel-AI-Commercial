"""Enterprise SOC2 Audit Logging Service.

Provides immutable, structured audit logging for security events, authentication,
RBAC modifications, billing events, and repository quality gate actions.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.infrastructure.db.models.audit_log import AuditLog


class AuditService:
    @staticmethod
    async def record_event(
        session: AsyncSession,
        org_id: str,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        user_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        """Records an immutable SOC2 audit log entry within the tenant scope."""
        log_entry = AuditLog(
            organization_id=org_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            created_at=datetime.now(UTC),
        )
        session.add(log_entry)
        await session.commit()
        await session.refresh(log_entry)

        logger.info(
            f"[AuditLog] org={org_id} action={action} resource={resource_type}:{resource_id} user={user_id}"
        )
        return log_entry

    @staticmethod
    async def query_logs(
        session: AsyncSession,
        org_id: str,
        limit: int = 50,
        offset: int = 0,
        action: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        """Queries tenant audit logs with pagination and optional action filtering."""
        query = select(AuditLog).where(AuditLog.organization_id == org_id)
        if action:
            query = query.where(AuditLog.action == action)

        # Count total
        count_res = await session.execute(query)
        total = len(count_res.scalars().all())

        # Paginated fetch
        paginated_stmt = query.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)
        res = await session.execute(paginated_stmt)
        logs = list(res.scalars().all())

        return logs, total
