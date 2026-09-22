"""Authentication and API Key Endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_active_user, get_tenant_context, require_role
from app.api.v1.schemas.auth import (
    APIKeyResponse,
    CreateAPIKeyRequest,
    CreateAPIKeyResponse,
    GitHubLoginResponse,
    OAuthCallbackRequest,
    OrganizationMemberResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
)
from app.core.config import settings
from app.domain.enums import UserRole
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db_session
from app.services.auth_service import AuthService

router = APIRouter()


@router.get("/github/url", response_model=GitHubLoginResponse, summary="Get GitHub OAuth URL")
async def get_github_login_url(state: str | None = None) -> GitHubLoginResponse:
    """Returns the authorization URL to redirect users to GitHub OAuth SSO."""
    url = AuthService.get_github_auth_url(state=state)
    return GitHubLoginResponse(authorization_url=url)


@router.post("/github/callback", response_model=TokenResponse, summary="GitHub OAuth Callback")
async def github_oauth_callback(
    payload: OAuthCallbackRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Exchanges GitHub authorization code, provisions user/org, and returns JWT tokens."""
    try:
        github_data = await AuthService.exchange_github_code(payload.code)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with GitHub: {e}",
        )

    _, _, access_token, refresh_token = await AuthService.authenticate_or_provision_user(
        session=session,
        github_data=github_data,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse, summary="Refresh JWT Access Token")
async def refresh_access_token(
    payload: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Issues fresh access and refresh tokens using a valid refresh token."""
    try:
        access_token, refresh_token = await AuthService.refresh_tokens(session, payload.refresh_token)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/me", response_model=UserResponse, summary="Get Current Authenticated User")
async def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserResponse:
    """Returns current user profile and list of organizations with assigned roles."""
    orgs = [
        OrganizationMemberResponse(
            organization_id=m.organization.id,
            organization_name=m.organization.name,
            organization_slug=m.organization.slug,
            role=m.role.value if hasattr(m.role, "value") else str(m.role),
            plan=m.organization.plan.value if hasattr(m.organization.plan, "value") else str(m.organization.plan),
        )
        for m in current_user.memberships
        if m.is_active and m.organization
    ]
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        avatar_url=current_user.avatar_url,
        organizations=orgs,
    )


@router.post("/api-keys", response_model=CreateAPIKeyResponse, summary="Create API Key")
async def create_api_key(
    payload: CreateAPIKeyRequest,
    tenant_ctx: Annotated[TenantContext, Depends(require_role(UserRole.ADMIN))],
    session: AsyncSession = Depends(get_db_session),
) -> CreateAPIKeyResponse:
    """Generates an API key for programmatic access. Requires ADMIN role. Raw key is returned once."""
    api_key_record, raw_key = await AuthService.create_api_key(
        session=session,
        user=tenant_ctx.user,
        organization_id=tenant_ctx.organization.id,
        name=payload.name,
        scopes=payload.scopes,
    )
    return CreateAPIKeyResponse(
        id=api_key_record.id,
        name=api_key_record.name,
        key_prefix=api_key_record.key_prefix,
        raw_key=raw_key,
        scopes=api_key_record.scopes,
        created_at=api_key_record.created_at,
    )


@router.get("/api-keys", response_model=list[APIKeyResponse], summary="List API Keys")
async def list_api_keys(
    tenant_ctx: Annotated[TenantContext, Depends(require_role(UserRole.MEMBER))],
    session: AsyncSession = Depends(get_db_session),
) -> list[APIKeyResponse]:
    """Lists all active API keys for the current organization."""
    keys = await AuthService.list_api_keys(session, tenant_ctx.organization.id)
    return [
        APIKeyResponse(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            scopes=k.scopes,
            is_active=k.is_active,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
        )
        for k in keys
    ]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke API Key")
async def revoke_api_key(
    key_id: str,
    tenant_ctx: Annotated[TenantContext, Depends(require_role(UserRole.ADMIN))],
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Revokes an API key. Requires ADMIN role."""
    revoked = await AuthService.revoke_api_key(session, tenant_ctx.organization.id, key_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")