"""Billing Pydantic Schemas."""

from typing import Any
from pydantic import BaseModel, Field


class CreateCheckoutRequest(BaseModel):
    price_id: str = Field(..., description="Stripe Price ID for target tier")
    seats: int = Field(default=5, ge=1, le=500)
    return_url: str | None = None


class CheckoutResponse(BaseModel):
    checkout_url: str


class CreatePortalRequest(BaseModel):
    return_url: str | None = None


class PortalResponse(BaseModel):
    portal_url: str


class SubscriptionDetailsResponse(BaseModel):
    organization_id: str
    plan: str
    subscription_status: str
    max_seats: int
    active_seats_30d: int
    monthly_scans_used: int
    max_monthly_scans: int
    entitlements: dict[str, Any]