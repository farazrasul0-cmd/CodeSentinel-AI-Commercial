"""Unit tests for subscription tier entitlements and 30-day seat metering."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OrgPlan
from app.infrastructure.db.models.organization import Organization
from app.services.entitlement_service import EntitlementService, TIER_ENTITLEMENTS


def test_tier_entitlements_configuration():
    free_tier = EntitlementService.get_tier_entitlement(OrgPlan.FREE)
    assert free_tier.allow_private_repos is False
    assert free_tier.allow_inline_suggestions is False
    assert free_tier.max_seats == 1

    team_tier = EntitlementService.get_tier_entitlement(OrgPlan.TEAM)
    assert team_tier.allow_private_repos is True
    assert team_tier.allow_inline_suggestions is True
    assert team_tier.priority_queue is True


@pytest.mark.asyncio
async def test_30_day_seat_metering_and_soft_gating(db_session: AsyncSession):
    org = Organization(
        name="Team Seats Org",
        slug="team-seats-org",
        plan=OrgPlan.TEAM,
        max_seats=2,
    )
    db_session.add(org)
    await db_session.commit()

    # 1. Record 2 authors -> under quota
    await EntitlementService.record_commit_author(db_session, org.id, "alice@acme.com", "Alice")
    await EntitlementService.record_commit_author(db_session, org.id, "bob@acme.com", "Bob")

    count = await EntitlementService.count_active_contributors_30d(db_session, org.id)
    assert count == 2

    is_allowed, warning, data = await EntitlementService.evaluate_scan_permission(
        session=db_session,
        org=org,
        is_private_repo=True,
    )
    assert is_allowed is True
    assert warning is None  # Under quota

    # 2. Record 3rd author -> exceeds max_seats=2
    await EntitlementService.record_commit_author(db_session, org.id, "charlie@acme.com", "Charlie")
    count_updated = await EntitlementService.count_active_contributors_30d(db_session, org.id)
    assert count_updated == 3

    # Soft gating: Still permitted, but returns quota warning notice!
    is_allowed_soft, warning_soft, data_soft = await EntitlementService.evaluate_scan_permission(
        session=db_session,
        org=org,
        is_private_repo=True,
    )
    assert is_allowed_soft is True
    assert warning_soft is not None
    assert "licensed seat limit (3/2" in warning_soft
    assert data_soft["active_seats_30d"] == 3


@pytest.mark.asyncio
async def test_free_tier_hard_gate_on_private_repo(db_session: AsyncSession):
    free_org = Organization(
        name="Community Free Org",
        slug="community-free-org",
        plan=OrgPlan.FREE,
        max_seats=1,
    )
    db_session.add(free_org)
    await db_session.commit()

    # Private repo attempted on FREE plan -> Hard rejected
    is_allowed, reason, _ = await EntitlementService.evaluate_scan_permission(
        session=db_session,
        org=free_org,
        is_private_repo=True,
    )
    assert is_allowed is False
    assert "Private repository scanning requires a Team or Enterprise plan" in reason