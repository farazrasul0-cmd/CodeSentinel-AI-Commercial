"""Subscription Tier Entitlement and 30-Day Active Seat Metering Service."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OrgPlan
from app.infrastructure.db.models.billing import ActiveAuthor
from app.infrastructure.db.models.organization import Organization


@dataclass(frozen=True)
class TierEntitlement:
    plan: OrgPlan
    max_seats: int
    allow_private_repos: bool
    allow_inline_suggestions: bool
    allow_secret_scanning: bool
    allow_custom_rules: bool
    priority_queue: bool


TIER_ENTITLEMENTS: dict[OrgPlan, TierEntitlement] = {
    OrgPlan.FREE: TierEntitlement(
        plan=OrgPlan.FREE,
        max_seats=1,
        allow_private_repos=False,
        allow_inline_suggestions=False,
        allow_secret_scanning=False,
        allow_custom_rules=False,
        priority_queue=False,
    ),
    OrgPlan.TEAM: TierEntitlement(
        plan=OrgPlan.TEAM,
        max_seats=5,
        allow_private_repos=True,
        allow_inline_suggestions=True,
        allow_secret_scanning=True,
        allow_custom_rules=False,
        priority_queue=True,
    ),
    OrgPlan.ENTERPRISE: TierEntitlement(
        plan=OrgPlan.ENTERPRISE,
        max_seats=9999,
        allow_private_repos=True,
        allow_inline_suggestions=True,
        allow_secret_scanning=True,
        allow_custom_rules=True,
        priority_queue=True,
    ),
}


class EntitlementService:
    """Evaluates organization feature entitlements, quotas, and rolling 30-day seat usage."""

    @classmethod
    def get_tier_entitlement(cls, plan: OrgPlan) -> TierEntitlement:
        return TIER_ENTITLEMENTS.get(plan, TIER_ENTITLEMENTS[OrgPlan.FREE])

    @classmethod
    async def record_commit_author(
        cls,
        session: AsyncSession,
        organization_id: str,
        author_email: str,
        author_name: str | None = None,
    ) -> None:
        """Records or updates commit author timestamp for active seat metering."""
        if not author_email:
            return

        clean_email = author_email.lower().strip()
        stmt = select(ActiveAuthor).where(
            ActiveAuthor.organization_id == organization_id,
            ActiveAuthor.author_email == clean_email,
        )
        res = await session.execute(stmt)
        record = res.scalar_one_or_none()

        now = datetime.now(UTC)
        if record:
            record.last_commit_at = now
            if author_name:
                record.author_name = author_name
        else:
            record = ActiveAuthor(
                organization_id=organization_id,
                author_email=clean_email,
                author_name=author_name,
                last_commit_at=now,
            )
            session.add(record)

        await session.commit()

    @classmethod
    async def count_active_contributors_30d(
        cls,
        session: AsyncSession,
        organization_id: str,
    ) -> int:
        """Counts unique active commit authors on analyzed PRs over the rolling 30-day window."""
        window_start = datetime.now(UTC) - timedelta(days=30)
        stmt = (
            select(func.count(ActiveAuthor.id))
            .where(
                ActiveAuthor.organization_id == organization_id,
                ActiveAuthor.last_commit_at >= window_start,
            )
        )
        res = await session.execute(stmt)
        count = res.scalar() or 0
        return int(count)

    @classmethod
    async def evaluate_scan_permission(
        cls,
        session: AsyncSession,
        org: Organization,
        is_private_repo: bool = False,
        author_email: str | None = None,
    ) -> tuple[bool, str | None, dict[str, Any]]:
        """Evaluates whether scan is permitted or if soft-gating warnings apply.
        
        Returns:
            (is_permitted, soft_warning_message, entitlements_dict)
        """
        entitlement = cls.get_tier_entitlement(org.plan)

        # 1. Hard Gate: Private repos not permitted on FREE tier
        if is_private_repo and not entitlement.allow_private_repos:
            return (
                False,
                f"Private repository scanning requires a Team or Enterprise plan (current plan: {org.plan.value}).",
                {"plan": org.plan.value},
            )

        # 2. Record author if provided
        if author_email:
            await cls.record_commit_author(session, org.id, author_email)

        # 3. Soft Gate: Check 30-day seat metering
        active_seats = await cls.count_active_contributors_30d(session, org.id)
        max_seats = org.max_seats or entitlement.max_seats

        warning = None
        if active_seats > max_seats:
            warning = (
                f"Your team has reached its licensed seat limit ({active_seats}/{max_seats} active authors). "
                "Upgrade your plan in CodeSentinel settings to unlock automated fixes for new contributors."
            )

        return (
            True,
            warning,
            {
                "plan": org.plan.value,
                "allow_inline_suggestions": entitlement.allow_inline_suggestions,
                "allow_secret_scanning": entitlement.allow_secret_scanning,
                "active_seats_30d": active_seats,
                "max_seats": max_seats,
            },
        )