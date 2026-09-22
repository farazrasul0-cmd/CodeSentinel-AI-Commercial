"""Integration tests for Commercial Stripe Billing and Entitlement APIs."""

import json
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.domain.enums import OrgPlan, UserRole
from app.infrastructure.db.models.membership import Membership
from app.infrastructure.db.models.organization import Organization
from app.infrastructure.db.models.user import User


@pytest.fixture
async def billing_test_setup(db_session: AsyncSession):
    """Sets up an Organization, Owner, and Member for billing tests."""
    org = Organization(
        name="Billing Test Org",
        slug="billing-test-org",
        plan=OrgPlan.TEAM,
        stripe_customer_id="cus_test_12345",
        subscription_status="active",
        max_seats=10,
    )
    db_session.add(org)
    await db_session.flush()

    owner = User(
        email="owner@billingtest.com",
        username="billing-owner",
        full_name="Billing Owner",
    )
    member = User(
        email="viewer@billingtest.com",
        username="billing-viewer",
        full_name="Billing Viewer",
    )
    db_session.add_all([owner, member])
    await db_session.flush()

    owner_membership = Membership(
        organization_id=org.id,
        user_id=owner.id,
        role=UserRole.OWNER,
    )
    member_membership = Membership(
        organization_id=org.id,
        user_id=member.id,
        role=UserRole.VIEWER,
    )
    db_session.add_all([owner_membership, member_membership])
    await db_session.commit()

    owner_token = create_access_token(
        data={"sub": str(owner.id), "org_id": str(org.id), "role": UserRole.OWNER.value}
    )
    member_token = create_access_token(
        data={"sub": str(member.id), "org_id": str(org.id), "role": UserRole.VIEWER.value}
    )

    return {
        "org": org,
        "owner": owner,
        "member": member,
        "owner_token": owner_token,
        "member_token": member_token,
    }


@pytest.mark.asyncio
async def test_get_subscription_details(
    async_client: AsyncClient,
    billing_test_setup: dict,
):
    token = billing_test_setup["owner_token"]
    res = await async_client.get(
        "/api/v1/billing/subscription",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["plan"] == OrgPlan.TEAM.value
    assert data["subscription_status"] == "active"
    assert data["max_seats"] == 10
    assert data["entitlements"]["allow_private_repos"] is True
    assert data["entitlements"]["allow_inline_suggestions"] is True


@pytest.mark.asyncio
async def test_create_checkout_session(
    async_client: AsyncClient,
    billing_test_setup: dict,
):
    token = billing_test_setup["owner_token"]
    with patch(
        "app.services.billing_service.BillingService.create_checkout_session",
        new_callable=AsyncMock,
        return_value="https://checkout.stripe.com/pay/cs_test_sample",
    ):
        res = await async_client.post(
            "/api/v1/billing/checkout",
            json={"price_id": "price_team_monthly", "seats": 5},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "checkout.stripe.com" in data["checkout_url"]


@pytest.mark.asyncio
async def test_create_checkout_forbidden_for_viewer(
    async_client: AsyncClient,
    billing_test_setup: dict,
):
    viewer_token = billing_test_setup["member_token"]
    res = await async_client.post(
        "/api/v1/billing/checkout",
        json={"price_id": "price_team_monthly", "seats": 5},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_create_portal_session(
    async_client: AsyncClient,
    billing_test_setup: dict,
):
    token = billing_test_setup["owner_token"]
    with patch(
        "app.services.billing_service.BillingService.create_customer_portal_session",
        new_callable=AsyncMock,
        return_value="https://billing.stripe.com/p/session/test_sample",
    ):
        res = await async_client.post(
            "/api/v1/billing/portal",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "billing.stripe.com" in data["portal_url"]


@pytest.mark.asyncio
async def test_stripe_webhook_flow_and_idempotency(
    async_client: AsyncClient,
    billing_test_setup: dict,
    db_session: AsyncSession,
):
    org = billing_test_setup["org"]

    webhook_payload = {
        "id": "evt_integ_test_001",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_test_abc",
                "customer": org.stripe_customer_id,
                "status": "active",
                "items": {
                    "data": [
                        {
                            "quantity": 15,
                            "price": {"id": "price_enterprise_yearly"},
                        }
                    ]
                },
            }
        },
    }

    # 1. First delivery
    res = await async_client.post(
        "/api/v1/billing/webhook",
        json=webhook_payload,
        headers={"stripe-signature": "mock_test_signature"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert res.json()["action"] == "event_processed"

    # Verify DB update
    await db_session.refresh(org)
    assert org.max_seats == 15

    # 2. Second delivery (Idempotent retry)
    res_retry = await async_client.post(
        "/api/v1/billing/webhook",
        json=webhook_payload,
        headers={"stripe-signature": "mock_test_signature"},
    )
    assert res_retry.status_code == 200
    assert res_retry.json()["action"] == "already_processed"
