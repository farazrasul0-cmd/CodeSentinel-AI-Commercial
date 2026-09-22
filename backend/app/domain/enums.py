"""Domain enums for analysis status, finding severities, risk tiers, and multi-tenant RBAC."""

import enum


class JobStatus(enum.StrEnum):
    QUEUED = "QUEUED"
    CLONING = "CLONING"
    INDEXING = "INDEXING"
    STATIC_ANALYSIS = "STATIC_ANALYSIS"
    DEFECT_PREDICTION = "DEFECT_PREDICTION"
    AI_REVIEW = "AI_REVIEW"
    AGGREGATING = "AGGREGATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class FindingSeverity(enum.StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FindingCategory(enum.StrEnum):
    SECURITY = "SECURITY"
    CODE_SMELL = "CODE_SMELL"
    BUG_RISK = "BUG_RISK"
    PERFORMANCE = "PERFORMANCE"
    MAINTAINABILITY = "MAINTAINABILITY"
    ARCHITECTURE = "ARCHITECTURE"


class RiskTier(enum.StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"


class CommentStatus(enum.StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DISMISSED = "DISMISSED"


class UserRole(enum.StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


class OrgPlan(enum.StrEnum):
    FREE = "FREE"
    TEAM = "TEAM"
    ENTERPRISE = "ENTERPRISE"


ROLE_HIERARCHY: dict[UserRole, int] = {
    UserRole.VIEWER: 10,
    UserRole.MEMBER: 20,
    UserRole.ADMIN: 30,
    UserRole.OWNER: 40,
}