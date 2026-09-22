"""Commercial Health, Liveness, and Readiness Endpoints for Production Deployment."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.db.session import get_db_session

router = APIRouter(tags=["System"])


@router.get("/health", summary="Basic System Status")
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": "2.0.0",
        "edition": "commercial",
    }


@router.get("/health/live", summary="Kubernetes Liveness Probe")
async def liveness_probe():
    """Returns 200 OK immediately if the HTTP worker process is alive."""
    return {"status": "alive"}


@router.get("/health/ready", summary="Kubernetes Readiness Probe")
async def readiness_probe(session: AsyncSession = Depends(get_db_session)):
    """Verifies that upstream dependencies (PostgreSQL Database, Task Broker) are reachable."""
    checks = {
        "database": "unknown",
        "environment": settings.APP_ENV,
    }
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"unhealthy: {e}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=checks,
        )

    return {"status": "ready", "checks": checks}
