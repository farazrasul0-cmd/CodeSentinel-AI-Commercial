"""Unit tests for AuthService provisioning and API key lifecycle."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OrgPlan, UserRole
from app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_auth_service_provisioning_flow(db_session: AsyncSession):
    github_payload = {
        "github_id": 1234567,
        "login": "octocat-engineer",
        "email": "octocat@github.example.com",
        "name": "Octocat Engineer",
        "avatar_url": "https://avatars.githubusercontent.com/u/1234567",
        "access_token": "gho_test_mock_token_abc",
    }

    user, org, access_token, refresh_token = await AuthService.authenticate_or_provision_user(
        session=db_session,
        github_data=github_payload,
    )

    assert user.id is not None
    assert user.email == "octocat@github.example.com"
    assert user.github_username == "octocat-engineer"
    assert user.encrypted_github_token is not None

    assert org.id is not None
    assert org.plan == OrgPlan.FREE
    assert len(user.memberships) == 1
    assert user.memberships[0].role == UserRole.OWNER

    assert access_token is not None
    assert refresh_token is not None

    # Test token refresh
    new_access, new_refresh = await AuthService.refresh_tokens(db_session, refresh_token)
    assert new_access is not None
    assert new_refresh is not None


@pytest.mark.asyncio
async def test_auth_service_api_key_management(db_session: AsyncSession):
    github_payload = {
        "github_id": 7654321,
        "login": "dev-ops-lead",
        "email": "devops@example.com",
        "name": "DevOps Lead",
        "avatar_url": "https://avatars.githubusercontent.com/u/7654321",
        "access_token": "gho_devops_test_token",
    }

    user, org, _, _ = await AuthService.authenticate_or_provision_user(
        session=db_session,
        github_data=github_payload,
    )

    # 1. Create API Key
    api_key_record, raw_key = await AuthService.create_api_key(
        session=db_session,
        user=user,
        organization_id=org.id,
        name="Production GitHub Actions",
        scopes=["scans:trigger", "reports:read"],
    )
    assert api_key_record.id is not None
    assert api_key_record.name == "Production GitHub Actions"
    assert raw_key.startswith("cs_live_")
    assert api_key_record.is_active is True

    # 2. List API Keys
    keys = await AuthService.list_api_keys(db_session, org.id)
    assert len(keys) == 1
    assert keys[0].name == "Production GitHub Actions"

    # 3. Revoke API Key
    revoked = await AuthService.revoke_api_key(db_session, org.id, api_key_record.id)
    assert revoked is True

    # 4. List again (only active returned)
    active_keys = await AuthService.list_api_keys(db_session, org.id)
    assert len(active_keys) == 0