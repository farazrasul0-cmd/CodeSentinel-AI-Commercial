"""Billing, Active Contributor Metering, and Idempotent Webhook Events ORM Models."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin


class ProcessedWebhookEvent(Base, UUIDPrimaryKeyMixin):
    """Tracks processed webhook event IDs to guarantee strict idempotency across retries."""

    __tablename__ = "processed_webhook_events"

    event_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="stripe", nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class ActiveAuthor(Base, UUIDPrimaryKeyMixin):
    """Tracks unique PR commit authors over a rolling 30-day window per organization for seat metering."""

    __tablename__ = "active_authors"
    __table_args__ = (
        UniqueConstraint("organization_id", "author_email", name="uq_org_author_email"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    author_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_commit_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )