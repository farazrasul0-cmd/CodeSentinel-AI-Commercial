"""Organization multi-tenant ORM model."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import OrgPlan
from app.infrastructure.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.db.models.api_key import APIKey
    from app.infrastructure.db.models.audit_log import AuditLog
    from app.infrastructure.db.models.membership import Membership
    from app.infrastructure.db.models.repository import Repository


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    plan: Mapped[OrgPlan] = mapped_column(
        Enum(OrgPlan, native_enum=False),
        default=OrgPlan.FREE,
        nullable=False,
    )

    # Stripe Commercial Fields
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    # Quotas & Limits
    max_monthly_scans: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    monthly_scans_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_seats: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # GitHub App Installation
    github_installation_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)

    # Relationships
    memberships: Mapped[list["Membership"]] = relationship(
        "Membership",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    repositories: Mapped[list["Repository"]] = relationship(
        "Repository",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    api_keys: Mapped[list["APIKey"]] = relationship(
        "APIKey",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="organization",
        cascade="all, delete-orphan",
    )