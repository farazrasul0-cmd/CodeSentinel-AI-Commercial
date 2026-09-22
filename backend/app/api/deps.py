"""FastAPI dependencies for Authentication, Multi-Tenant Resolution, and RBAC."""

import hashlib
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_jwt_token
from app.domain.enums import ROLE_HIERARCHY, UserRole
from app.infrastructure.db.models.api_key import APIKey
from app.infrastructure.db.models.membership import Membership
from app.infrastructure.db.models.organization import Organization
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db_session, set_tenant_context

security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    auth_header: Annotated[HTTPAuthorizationCredentials | None, Security(security_bearer)],
    x_api_key: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Authenticates the request via Bearer JWT token or programmatic X-API-Key header."""
    # 1. Try Bearer JWT Authentication
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
        payload = decode_jwt_token(token)
        if not payload or payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid, expired, or malformed access token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload missing subject identifier",
            )
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.memberships).selectinload(Membership.organization))
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User associated with token not found",
            )
        return user

    # 2. Try Programmatic X-API-Key Authentication
    if x_api_key:
        hashed_key = hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()
        stmt = (
            select(APIKey)
            .where(APIKey.hashed_key == hashed_key, APIKey.is_active == True)
            .options(selectinload(APIKey.user), selectinload(APIKey.organization))
        )
        result = await session.execute(stmt)
        api_key_record = result.scalar_one_or_none()
        if not api_key_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key",
            )
        return api_key_record.user

    # No credentials provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication credentials (provide Bearer token or X-API-Key header)",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Ensures the authenticated user account is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or deactivated",
        )
    return current_user


class TenantContext:
    """Encapsulates the resolved multi-tenant context for the active request."""

    def __init__(self, user: User, organization: Organization, membership: Membership):
        self.user = user
        self.organization = organization
        self.membership = membership
        self.role: UserRole = membership.role


async def get_tenant_context(
    current_user: Annotated[User, Depends(get_current_active_user)],
    x_organization_id: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db_session),
) -> TenantContext:
    """Resolves active Organization for current user and sets PostgreSQL RLS context."""
    if not current_user.memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to any organization",
        )

    target_org_id = x_organization_id or current_user.memberships[0].organization_id

    # Verify user has an active membership in the target organization
    active_membership = next(
        (m for m in current_user.memberships if m.organization_id == target_org_id and m.is_active),
        None,
    )

    if not active_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: User is not an active member of organization {target_org_id}",
        )

    # Fetch full organization record
    stmt = select(Organization).where(Organization.id == target_org_id)
    result = await session.execute(stmt)
    org = result.scalar_one_or_none()
    if not org or not org.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found or inactive",
        )

    # Set PostgreSQL session RLS variable
    await set_tenant_context(session, org.id)

    return TenantContext(user=current_user, organization=org, membership=active_membership)


def require_role(minimum_role: UserRole):
    """Dependency factory enforcing Role-Based Access Control (RBAC)."""

    async def role_checker(
        tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    ) -> TenantContext:
        user_level = ROLE_HIERARCHY.get(tenant_ctx.role, 0)
        required_level = ROLE_HIERARCHY.get(minimum_role, 0)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action requires at least '{minimum_role}' role (current role: '{tenant_ctx.role}')",
            )
        return tenant_ctx

    return role_checker