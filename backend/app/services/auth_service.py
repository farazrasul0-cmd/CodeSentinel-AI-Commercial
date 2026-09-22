"""Commercial Authentication and Multi-Tenant Provisioning Service."""

import re
from datetime import UTC, datetime, timedelta
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    encrypt_secret,
    generate_api_key,
)
from app.domain.enums import OrgPlan, UserRole
from app.infrastructure.db.models.api_key import APIKey
from app.infrastructure.db.models.membership import Membership
from app.infrastructure.db.models.organization import Organization
from app.infrastructure.db.models.user import User


class AuthService:
    """Handles GitHub SSO, token lifecycle, team provisioning, and API keys."""

    @staticmethod
    def get_github_auth_url(state: str | None = None) -> str:
        """Generates GitHub OAuth authorization URL."""
        client_id = settings.GITHUB_CLIENT_ID or "mock-client-id"
        redirect_uri = settings.GITHUB_OAUTH_REDIRECT_URI
        scope = "read:user,user:email,repo"
        url = f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}"
        if state:
            url += f"&state={state}"
        return url

    @staticmethod
    async def exchange_github_code(code: str) -> dict:
        """Exchanges authorization code for GitHub access token and profile info."""
        if not settings.GITHUB_CLIENT_ID or settings.GITHUB_CLIENT_ID == "mock-client-id":
            return {
                "github_id": 999001,
                "login": "dev-engineer",
                "email": "dev@codesentinel.ai",
                "name": "Dev Engineer",
                "avatar_url": "https://github.com/identicons/dev.png",
                "access_token": "gho_mock_access_token_12345",
            }

        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
                },
                timeout=15.0,
            )
            token_json = token_res.json()
            access_token = token_json.get("access_token")
            if not access_token:
                raise ValueError(f"Failed to exchange code: {token_json.get('error_description', 'Unknown error')}")

            user_res = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=10.0,
            )
            profile = user_res.json()

            email = profile.get("email")
            if not email:
                emails_res = await client.get(
                    "https://api.github.com/user/emails",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                    },
                    timeout=10.0,
                )
                if emails_res.status_code == 200:
                    for em in emails_res.json():
                        if em.get("primary") and em.get("verified"):
                            email = em.get("email")
                            break

            return {
                "github_id": profile.get("id"),
                "login": profile.get("login"),
                "email": email or f"{profile.get('login')}@users.noreply.github.com",
                "name": profile.get("name") or profile.get("login"),
                "avatar_url": profile.get("avatar_url"),
                "access_token": access_token,
            }

    @staticmethod
    async def authenticate_or_provision_user(
        session: AsyncSession,
        github_data: dict,
    ) -> tuple[User, Organization, str, str]:
        """Provisions or updates a user from GitHub data and returns JWT tokens."""
        github_id = github_data.get("github_id")
        email = github_data.get("email")
        login = github_data.get("login")
        name = github_data.get("name")
        avatar_url = github_data.get("avatar_url")
        raw_token = github_data.get("access_token")

        stmt = (
            select(User)
            .where((User.github_id == github_id) | (User.email == email))
            .options(selectinload(User.memberships).selectinload(Membership.organization))
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        encrypted_token = encrypt_secret(raw_token) if raw_token else None

        if not user:
            user = User(
                email=email,
                username=login,
                full_name=name,
                avatar_url=avatar_url,
                github_id=github_id,
                github_username=login,
                encrypted_github_token=encrypted_token,
                is_active=True,
            )
            session.add(user)
            await session.flush()

            clean_slug = re.sub(r"[^a-zA-Z0-9-]", "-", login.lower()).strip("-")
            org = Organization(
                name=f"{login}'s Workspace",
                slug=f"{clean_slug}-workspace",
                plan=OrgPlan.FREE,
                is_active=True,
            )
            session.add(org)
            await session.flush()

            membership = Membership(
                user_id=user.id,
                organization_id=org.id,
                role=UserRole.OWNER,
                is_active=True,
            )
            session.add(membership)
            await session.flush()
        else:
            user.github_username = login
            user.avatar_url = avatar_url
            if encrypted_token:
                user.encrypted_github_token = encrypted_token

            if not user.memberships:
                clean_slug = re.sub(r"[^a-zA-Z0-9-]", "-", login.lower()).strip("-")
                org = Organization(
                    name=f"{login}'s Workspace",
                    slug=f"{clean_slug}-workspace",
                    plan=OrgPlan.FREE,
                    is_active=True,
                )
                session.add(org)
                await session.flush()
                membership = Membership(
                    user_id=user.id,
                    organization_id=org.id,
                    role=UserRole.OWNER,
                    is_active=True,
                )
                session.add(membership)
                await session.flush()
            else:
                org = user.memberships[0].organization

        await session.commit()

        # Eager reload user and relationships to avoid MissingGreenlet lazy load issues
        reload_stmt = (
            select(User)
            .where(User.id == user.id)
            .options(selectinload(User.memberships).selectinload(Membership.organization))
        )
        reload_res = await session.execute(reload_stmt)
        user = reload_res.scalar_one()
        org = user.memberships[0].organization

        access_token = create_access_token({"sub": user.id, "email": user.email, "org_id": org.id})
        refresh_token = create_refresh_token({"sub": user.id})

        return user, org, access_token, refresh_token

    @staticmethod
    async def refresh_tokens(session: AsyncSession, refresh_token: str) -> tuple[str, str]:
        """Validates refresh token and generates fresh access & refresh tokens."""
        payload = decode_jwt_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise ValueError("Invalid or expired refresh token")

        user_id = payload.get("sub")
        stmt = (
            select(User)
            .where(User.id == user_id, User.is_active == True)
            .options(selectinload(User.memberships))
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found or inactive")

        org_id = user.memberships[0].organization_id if user.memberships else None
        new_access = create_access_token({"sub": user.id, "email": user.email, "org_id": org_id})
        new_refresh = create_refresh_token({"sub": user.id})
        return new_access, new_refresh

    @staticmethod
    async def create_api_key(
        session: AsyncSession,
        user: User,
        organization_id: str,
        name: str,
        scopes: list[str],
    ) -> tuple[APIKey, str]:
        """Generates and persists a hashed API key; returns record and one-time raw key."""
        raw_key, prefix, sha256_hash = generate_api_key()
        api_key_record = APIKey(
            organization_id=organization_id,
            user_id=user.id,
            name=name,
            key_prefix=prefix,
            hashed_key=sha256_hash,
            scopes=scopes,
            is_active=True,
        )
        session.add(api_key_record)
        await session.commit()
        await session.refresh(api_key_record)
        return api_key_record, raw_key

    @staticmethod
    async def list_api_keys(session: AsyncSession, organization_id: str) -> list[APIKey]:
        """Lists active API keys for an organization."""
        stmt = (
            select(APIKey)
            .where(APIKey.organization_id == organization_id, APIKey.is_active == True)
            .order_by(APIKey.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def revoke_api_key(session: AsyncSession, organization_id: str, key_id: str) -> bool:
        """Revokes an API key."""
        stmt = select(APIKey).where(APIKey.id == key_id, APIKey.organization_id == organization_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if not record:
            return False
        record.is_active = False
        await session.commit()
        return True