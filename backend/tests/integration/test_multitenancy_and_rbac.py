"""Integration tests for Multi-Tenancy, Authentication, and RBAC endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.domain.enums import OrgPlan, UserRole
from app.infrastructure.db.models.membership import Membership
from app.infrastructure.db.models.organization import Organization
from app.infrastructure.db.models.user import User


@pytest.mark.asyncio
async def test_auth_github_url_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/auth/github/url?state=test_state_123")
    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    assert "github.com/login/oauth/authorize" in data["authorization_url"]
    assert "state=test_state_123" in data["authorization_url"]


@pytest.mark.asyncio
async def test_auth_github_callback_and_me(async_client: AsyncClient, db_session: AsyncSession):
    # Mock callback
    res = await async_client.post("/api/v1/auth/github/callback", json={"code": "sample_code"})
    assert res.status_code == 200
    token_data = res.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    access_token = token_data["access_token"]

    # Call /me with bearer token
    me_res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_res.status_code == 200
    user_info = me_res.json()
    assert user_info["username"] == "dev-engineer"
    assert len(user_info["organizations"]) == 1
    assert user_info["organizations"][0]["role"] == UserRole.OWNER


@pytest.mark.asyncio
async def test_rbac_and_api_key_lifecycle(async_client: AsyncClient, db_session: AsyncSession):
    # 1. Setup Organization
    org = Organization(name="Acme Corp", slug="acme-corp", plan=OrgPlan.TEAM)
    db_session.add(org)
    await db_session.flush()

    # 2. Setup Admin User & Viewer User
    admin_user = User(
        email="admin@acme.com",
        username="acme-admin",
        full_name="Acme Admin",
        is_active=True,
    )
    viewer_user = User(
        email="viewer@acme.com",
        username="acme-viewer",
        full_name="Acme Viewer",
        is_active=True,
    )
    db_session.add_all([admin_user, viewer_user])
    await db_session.flush()

    admin_membership = Membership(
        user_id=admin_user.id,
        organization_id=org.id,
        role=UserRole.ADMIN,
        is_active=True,
    )
    viewer_membership = Membership(
        user_id=viewer_user.id,
        organization_id=org.id,
        role=UserRole.VIEWER,
        is_active=True,
    )
    db_session.add_all([admin_membership, viewer_membership])
    await db_session.commit()

    admin_token = create_access_token({"sub": admin_user.id, "email": admin_user.email})
    viewer_token = create_access_token({"sub": viewer_user.id, "email": viewer_user.email})

    # 3. Viewer attempts to create API key -> Must be rejected with 403 FORBIDDEN
    viewer_res = await async_client.post(
        "/api/v1/auth/api-keys",
        headers={
            "Authorization": f"Bearer {viewer_token}",
            "X-Organization-Id": org.id,
        },
        json={"name": "Viewer Key", "scopes": ["scans:trigger"]},
    )
    assert viewer_res.status_code == 403
    assert "requires at least" in viewer_res.json()["detail"]

    # 4. Admin creates API key -> Succeeds with 200 OK
    admin_res = await async_client.post(
        "/api/v1/auth/api-keys",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Organization-Id": org.id,
        },
        json={"name": "CI Deployment Key", "scopes": ["scans:trigger", "reports:read"]},
    )
    assert admin_res.status_code == 200
    key_data = admin_res.json()
    assert key_data["name"] == "CI Deployment Key"
    raw_api_key = key_data["raw_key"]
    assert raw_api_key.startswith("cs_live_")

    # 5. Authenticate /me via X-API-Key header
    api_key_auth_res = await async_client.get(
        "/api/v1/auth/me",
        headers={"X-API-Key": raw_api_key},
    )
    assert api_key_auth_res.status_code == 200
    assert api_key_auth_res.json()["username"] == "acme-admin"

    # 6. Admin lists API keys
    list_res = await async_client.get(
        "/api/v1/auth/api-keys",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Organization-Id": org.id,
        },
    )
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # 7. Admin revokes API key
    revoke_res = await async_client.delete(
        f"/api/v1/auth/api-keys/{key_data['id']}",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "X-Organization-Id": org.id,
        },
    )
    assert revoke_res.status_code == 204


@pytest.mark.asyncio
async def test_cross_tenant_isolation(async_client: AsyncClient, db_session: AsyncSession):
    # Create Org Alpha and Org Beta
    org_alpha = Organization(name="Alpha Corp", slug="alpha-corp", plan=OrgPlan.FREE)
    org_beta = Organization(name="Beta Corp", slug="beta-corp", plan=OrgPlan.FREE)
    db_session.add_all([org_alpha, org_beta])
    await db_session.flush()

    user_alpha = User(email="alpha@corp.com", username="user-alpha", is_active=True)
    db_session.add(user_alpha)
    await db_session.flush()

    mem_alpha = Membership(
        user_id=user_alpha.id,
        organization_id=org_alpha.id,
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(mem_alpha)
    await db_session.commit()

    token_alpha = create_access_token({"sub": user_alpha.id, "email": user_alpha.email})

    # User Alpha attempts to access Org Beta with X-Organization-Id = org_beta.id -> 403 Forbidden
    cross_res = await async_client.get(
        "/api/v1/auth/api-keys",
        headers={
            "Authorization": f"Bearer {token_alpha}",
            "X-Organization-Id": org_beta.id,
        },
    )
    assert cross_res.status_code == 403
    assert "Access denied: User is not an active member" in cross_res.json()["detail"]