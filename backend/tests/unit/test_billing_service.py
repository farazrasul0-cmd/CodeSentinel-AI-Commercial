"""Unit tests for Stripe BillingService and idempotent webhook event processing."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OrgPlan
from app.infrastructure.db.models.organization import Organization
from app.infrastructure.db.models.user import User
from app.services.billing_service import BillingService


@pytest.mark.asyncio
async def test_checkout_and_portal_url_generation(db_session: AsyncSession):
    org = Organization(
        name="Test SaaS Org",
        slug="test-saas-org",
        plan=OrgPlan.FREE,
        stripe_customer_id="cus_test_12345",
    )
    user = User(email="owner@test.com", username="owner", is_active=True)
    db_session.add_all([org, user])
    await db_session.commit()

    # Checkout session URL
    checkout_url = await BillingService.create_checkout_session(
        org=org,
        user=user,
        price_id="price_team_monthly",
        seats=5,
    )
    assert checkout_url != ""
    assert org.id in checkout_url

    # Customer portal session URL
    portal_url = await BillingService.create_customer_portal_session(org=org)
    assert portal_url != ""
    assert "cus_test_12345" in portal_url


@pytest.mark.asyncio
async def test_stripe_webhook_idempotency_and_state_lifecycle(db_session: AsyncSession):
    org = Organization(
        name="Acme Billing Corp",
        slug="acme-billing-corp",
        plan=OrgPlan.FREE,
    )
    db_session.add(org)
    await db_session.commit()

    # 1. First event: checkout.session.completed
    checkout_event_id = "evt_checkout_1001"
    checkout_data = {
        "client_reference_id": org.id,
        "customer": "cus_acme_999",
        "subscription": "sub_acme_888",
    }

    is_processed, msg = await BillingService.process_stripe_webhook_event(
        session=db_session,
        event_id=checkout_event_id,
        event_type="checkout.session.completed",
        data_object=checkout_data,
    )
    assert is_processed is True
    assert msg == "event_processed"

    # Verify state updated
    await db_session.refresh(org)
    assert org.plan == OrgPlan.TEAM
    assert org.stripe_customer_id == "cus_acme_999"
    assert org.stripe_subscription_id == "sub_acme_888"
    assert org.subscription_status == "active"

    # 2. Strict Idempotency Check: send exact same checkout event again
    duplicate_processed, dup_msg = await BillingService.process_stripe_webhook_event(
        session=db_session,
        event_id=checkout_event_id,
        event_type="checkout.session.completed",
        data_object=checkout_data,
    )
    assert duplicate_processed is True
    assert dup_msg == "already_processed"  # Verified idempotent!

    # 3. Event: customer.subscription.updated (seat count modified to 10)
    update_event_id = "evt_sub_update_2002"
    update_data = {
        "id": "sub_acme_888",
        "customer": "cus_acme_999",
        "status": "active",
        "quantity": 10,
    }
    await BillingService.process_stripe_webhook_event(
        session=db_session,
        event_id=update_event_id,
        event_type="customer.subscription.updated",
        data_object=update_data,
    )
    await db_session.refresh(org)
    assert org.max_seats == 10

    # 4. Event: invoice.payment_failed (marked past_due)
    failed_event_id = "evt_invoice_fail_3003"
    await BillingService.process_stripe_webhook_event(
        session=db_session,
        event_id=failed_event_id,
        event_type="invoice.payment_failed",
        data_object={"customer": "cus_acme_999"},
    )
    await db_session.refresh(org)
    assert org.subscription_status == "past_due"

    # 5. Event: customer.subscription.deleted (downgraded to FREE)
    deleted_event_id = "evt_sub_delete_4004"
    await BillingService.process_stripe_webhook_event(
        session=db_session,
        event_id=deleted_event_id,
        event_type="customer.subscription.deleted",
        data_object={"id": "sub_acme_888", "customer": "cus_acme_999"},
    )
    await db_session.refresh(org)
    assert org.plan == OrgPlan.FREE
    assert org.subscription_status == "canceled"
    assert org.max_seats == 1