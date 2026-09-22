"""User ORM model."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.db.models.audit_log import AuditLog
    from app.infrastructure.db.models.membership import Membership


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # GitHub Identity & Ephemeral / Encrypted OAuth Token
    github_id: Mapped[int | None] = mapped_column(Integer, unique=True, index=True, nullable=True)
    github_username: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    encrypted_github_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Security & Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    memberships: Mapped[list["Membership"]] = relationship(
        "Membership",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
    )