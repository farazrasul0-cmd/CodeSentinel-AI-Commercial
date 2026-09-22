"""Stripe Commercial Billing Service with Strict Webhook Idempotency."""

from typing import Any
import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.domain.enums import OrgPlan
from app.infrastructure.db.models.billing import ProcessedWebhookEvent
from app.infrastructure.db.models.organization import Organization
from app.infrastructure.db.models.user import User

if settings.STRIPE_API_KEY:
    stripe.api_key = settings.STRIPE_API_KEY


async def _handle_checkout_completed(session: AsyncSession, data_object: dict[str, Any]) -> None:
    """Handles checkout.session.completed event."""
    org_id = data_object.get("client_reference_id") or data_object.get("metadata", {}).get("org_id")
    customer_id = data_object.get("customer")
    sub_id = data_object.get("subscription")

    if org_id:
        stmt = select(Organization).where(Organization.id == org_id)
        res = await session.execute(stmt)
        org = res.scalar_one_or_none()
        if org:
            org.stripe_customer_id = customer_id
            org.stripe_subscription_id = sub_id
            org.plan = OrgPlan.TEAM
            org.subscription_status = "active"
            logger.info(f"[Billing] Upgraded Org {org.name} to TEAM tier via Checkout")


async def _handle_subscription_updated(session: AsyncSession, data_object: dict[str, Any]) -> None:
    """Handles customer.subscription.updated event."""
    sub_id = data_object.get("id")
    customer_id = data_object.get("customer")
    status = data_object.get("status", "active")
    quantity = data_object.get("quantity")
    if quantity is None:
        items = data_object.get("items", {}).get("data", [])
        quantity = items[0].get("quantity", 5) if items else 5

    stmt = select(Organization).where(
        (Organization.stripe_subscription_id == sub_id) | (Organization.stripe_customer_id == customer_id)
    )
    res = await session.execute(stmt)
    org = res.scalar_one_or_none()
    if org:
        org.subscription_status = status
        org.max_seats = quantity
        logger.info(f"[Billing] Updated subscription status={status}, seats={quantity} for Org {org.name}")


async def _handle_subscription_deleted(session: AsyncSession, data_object: dict[str, Any]) -> None:
    """Handles customer.subscription.deleted event."""
    sub_id = data_object.get("id")
    customer_id = data_object.get("customer")

    stmt = select(Organization).where(
        (Organization.stripe_subscription_id == sub_id) | (Organization.stripe_customer_id == customer_id)
    )
    res = await session.execute(stmt)
    org = res.scalar_one_or_none()
    if org:
        org.plan = OrgPlan.FREE
        org.subscription_status = "canceled"
        org.max_seats = 1
        logger.info(f"[Billing] Downgraded Org {org.name} to FREE tier on subscription cancellation")


async def _handle_payment_failed(session: AsyncSession, data_object: dict[str, Any]) -> None:
    """Handles invoice.payment_failed event."""
    customer_id = data_object.get("customer")
    stmt = select(Organization).where(Organization.stripe_customer_id == customer_id)
    res = await session.execute(stmt)
    org = res.scalar_one_or_none()
    if org:
        org.subscription_status = "past_due"
        logger.warning(f"[Billing] Payment failed for Org {org.name}; marked past_due")


class BillingService:
    """Manages Stripe Checkout, Self-Serve Billing Portals, and Idempotent Webhook Processing."""

    @staticmethod
    async def create_checkout_session(
        org: Organization,
        user: User,
        price_id: str,
        seats: int = 5,
        return_url: str = "http://localhost:5173/settings/billing",
    ) -> str:
        """Creates a Stripe Checkout session URL for subscribing or upgrading."""
        if not settings.STRIPE_API_KEY or settings.STRIPE_API_KEY.startswith("mock_"):
            return f"https://checkout.stripe.mock/session_{org.id}_{price_id}"

        session_params: dict[str, Any] = {
            "mode": "subscription",
            "payment_method_types": ["card"],
            "line_items": [{"price": price_id, "quantity": max(1, seats)}],
            "success_url": f"{return_url}?session_id={{CHECKOUT_SESSION_ID}}&status=success",
            "cancel_url": f"{return_url}?status=cancelled",
            "client_reference_id": org.id,
            "metadata": {"org_id": org.id, "user_id": user.id},
        }

        if org.stripe_customer_id:
            session_params["customer"] = org.stripe_customer_id
        else:
            session_params["customer_email"] = user.email

        checkout_session = stripe.checkout.Session.create(**session_params)
        return checkout_session.url or ""

    @staticmethod
    async def create_customer_portal_session(
        org: Organization,
        return_url: str = "http://localhost:5173/settings/billing",
    ) -> str:
        """Generates self-serve Stripe Customer Portal session URL for subscription management."""
        if not org.stripe_customer_id:
            raise ValueError("Organization does not have an active Stripe customer account")

        if not settings.STRIPE_API_KEY or settings.STRIPE_API_KEY.startswith("mock_"):
            return f"https://billing.stripe.mock/portal_{org.stripe_customer_id}"

        portal = stripe.billing_portal.Session.create(
            customer=org.stripe_customer_id,
            return_url=return_url,
        )
        return portal.url or ""

    @classmethod
    async def process_stripe_webhook_event(
        cls,
        session: AsyncSession,
        event_id: str,
        event_type: str,
        data_object: dict[str, Any],
    ) -> tuple[bool, str]:
        """Processes Stripe event with strict DB-backed idempotency to prevent duplicate mutations."""
        stmt = select(ProcessedWebhookEvent).where(ProcessedWebhookEvent.event_id == event_id)
        res = await session.execute(stmt)
        if res.scalar_one_or_none():
            logger.info(f"[Billing] Skipped duplicate Stripe event {event_id} ({event_type})")
            return True, "already_processed"

        logger.info(f"[Billing] Ingesting Stripe webhook event {event_id}: {event_type}")

        event_handlers = {
            "checkout.session.completed": _handle_checkout_completed,
            "customer.subscription.updated": _handle_subscription_updated,
            "customer.subscription.deleted": _handle_subscription_deleted,
            "invoice.payment_failed": _handle_payment_failed,
        }
        handler = event_handlers.get(event_type)
        if handler:
            await handler(session, data_object)

        idempotent_record = ProcessedWebhookEvent(
            event_id=event_id,
            provider="stripe",
            event_type=event_type,
        )
        session.add(idempotent_record)
        await session.commit()

        return True, "event_processed"
