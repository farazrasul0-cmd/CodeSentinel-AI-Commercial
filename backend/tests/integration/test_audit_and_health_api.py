"""Integration tests for Healthcheck, Liveness, and SOC2 Audit Logging APIs."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.domain.enums import OrgPlan, UserRole
from app.infrastructure.db.models.membership import Membership
from app.infrastructure.db.models.organization import Organization
from app.infrastructure.db.models.user import User
from app.services.audit_service import AuditService


@pytest.fixture
async def audit_test_setup(db_session: AsyncSession):
    org = Organization(name="SOC2 Corp", slug="soc2-corp", plan=OrgPlan.ENTERPRISE)
    admin_user = User(email="admin@soc2.com", username="soc2-admin")
    viewer_user = User(email="viewer@soc2.com", username="soc2-viewer")
    db_session.add_all([org, admin_user, viewer_user])
    await db_session.flush()

    m1 = Membership(organization_id=org.id, user_id=admin_user.id, role=UserRole.ADMIN)
    m2 = Membership(organization_id=org.id, user_id=viewer_user.id, role=UserRole.VIEWER)
    db_session.add_all([m1, m2])
    await db_session.commit()

    admin_token = create_access_token(
        data={"sub": str(admin_user.id), "org_id": str(org.id), "role": UserRole.ADMIN.value}
    )
    viewer_token = create_access_token(
        data={"sub": str(viewer_user.id), "org_id": str(org.id), "role": UserRole.VIEWER.value}
    )

    return {
        "org": org,
        "admin": admin_user,
        "viewer": viewer_user,
        "admin_token": admin_token,
        "viewer_token": viewer_token,
    }


@pytest.mark.asyncio
async def test_health_live_endpoint(async_client: AsyncClient):
    res = await async_client.get("/api/v1/health/live")
    assert res.status_code == 200
    assert res.json()["status"] == "alive"


@pytest.mark.asyncio
async def test_health_ready_endpoint(async_client: AsyncClient):
    res = await async_client.get("/api/v1/health/ready")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"
    assert res.json()["checks"]["database"] == "connected"


@pytest.mark.asyncio
async def test_soc2_audit_trail_lifecycle(
    async_client: AsyncClient,
    db_session: AsyncSession,
    audit_test_setup: dict,
):
    org = audit_test_setup["org"]
    admin = audit_test_setup["admin"]
    admin_token = audit_test_setup["admin_token"]
    viewer_token = audit_test_setup["viewer_token"]

    # 1. Record an event via service
    await AuditService.record_event(
        session=db_session,
        org_id=org.id,
        user_id=admin.id,
        action="API_KEY_ROTATED",
        resource_type="API_KEY",
        resource_id="key-abc-123",
        details={"reason": "periodic_rotation"},
        ip_address="192.168.1.100",
    )

    # 2. Query logs as Admin -> 200 OK
    res = await async_client.get(
        "/api/v1/audit/logs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert data["items"][0]["action"] == "API_KEY_ROTATED"
    assert data["items"][0]["resource_type"] == "API_KEY"
    assert data["items"][0]["ip_address"] == "192.168.1.100"

    # 3. Query logs as Viewer -> 403 Forbidden
    forbidden_res = await async_client.get(
        "/api/v1/audit/logs",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert forbidden_res.status_code == 403
