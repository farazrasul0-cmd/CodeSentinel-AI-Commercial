"""Authentication and Multi-Tenant Pydantic Schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


class GitHubLoginResponse(BaseModel):
    authorization_url: str


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class OrganizationMemberResponse(BaseModel):
    organization_id: str
    organization_name: str
    organization_slug: str
    role: str
    plan: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str | None = None
    avatar_url: str | None = None
    organizations: list[OrganizationMemberResponse] = Field(default_factory=list)


class CreateAPIKeyRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    scopes: list[str] = Field(default=["scans:trigger", "reports:read"])


class CreateAPIKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    raw_key: str
    scopes: list[str]
    created_at: datetime


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None = None