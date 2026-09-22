"""API v1 Router Aggregator."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    analysis,
    auth,
    benchmarks,
    events,
    exports,
    health,
    reports,
    repositories,
    reviews,
    scorecard,
    webhooks,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(repositories.router)
api_router.include_router(analysis.router)
api_router.include_router(reports.router)
api_router.include_router(events.router)
api_router.include_router(reviews.router)
api_router.include_router(scorecard.router)
api_router.include_router(benchmarks.router)
api_router.include_router(exports.router)
api_router.include_router(webhooks.router)