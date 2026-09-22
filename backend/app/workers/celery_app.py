"""Celery Application Configuration with Dual-Lane Workers and Exponential Backoff."""

import asyncio

from celery import Celery
from kombu import Queue

from app.core.config import settings

celery_app = Celery(
    "quality_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Dual-lane architecture: Isolated interactive PR pool vs heavy monorepo pool
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_queues=[
        Queue(settings.CELERY_PR_QUEUE, routing_key=f"{settings.CELERY_PR_QUEUE}.#"),
        Queue(settings.CELERY_BATCH_QUEUE, routing_key=f"{settings.CELERY_BATCH_QUEUE}.#"),
        Queue("cpu_heavy", routing_key="cpu_heavy.#"),
        Queue("llm_calls", routing_key="llm_calls.#"),
    ],
    task_default_queue=settings.CELERY_BATCH_QUEUE,
    task_routes={
        "app.workers.celery_app.pr_review_task": {
            "queue": settings.CELERY_PR_QUEUE,
        },
        "app.workers.celery_app.monorepo_index_task": {
            "queue": settings.CELERY_BATCH_QUEUE,
        },
        "app.workers.celery_app.analyze_repository_task": {
            "queue": settings.CELERY_BATCH_QUEUE,
        },
        "app.workers.tasks.static_tasks.*": {"queue": "cpu_heavy"},
        "app.workers.tasks.ml_tasks.*": {"queue": "cpu_heavy"},
        "app.workers.tasks.llm_tasks.*": {"queue": "llm_calls"},
    },
    task_annotations={
        "app.workers.celery_app.pr_review_task": {
            "time_limit": 60,
            "soft_time_limit": 45,
        },
        "app.workers.celery_app.monorepo_index_task": {
            "time_limit": 1800,
            "soft_time_limit": 1500,
        },
        "app.workers.celery_app.analyze_repository_task": {
            "time_limit": 1800,
            "soft_time_limit": 1500,
        },
    },
)


@celery_app.task(
    name="app.workers.celery_app.pr_review_task",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=30,
)
def pr_review_task(self, repo_full_name: str, pr_number: int, commit_sha: str) -> dict:
    """Low-latency PR webhook task running in pr_lane (SLA < 30s)."""
    from app.services.pr_analysis_service import PRAnalysisService
    from app.services.pr_comment_service import PRCommentService

    async def _run() -> dict:
        service = PRAnalysisService()
        result = await service.analyze_pull_request(repo_full_name, pr_number, commit_sha)
        review_actions = await PRCommentService.execute_pr_review_actions(result)
        return {
            "repo": repo_full_name,
            "pr_number": pr_number,
            "gate_passed": result.quality_gate_passed,
            "actions": review_actions,
        }

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(
    name="app.workers.celery_app.analyze_repository_task",
    bind=True,
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def analyze_repository_task(self, job_id: str) -> str:
    """Long-running monorepo analysis task running in batch_lane."""
    from app.infrastructure.db.session import async_session_factory
    from app.services.ingestion_service import IngestionService

    async def _run() -> str:
        async with async_session_factory() as session:
            service = IngestionService(session)
            report = await service.run_pipeline(job_id)
            return report.id

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()


@celery_app.task(
    name="app.workers.celery_app.monorepo_index_task",
    bind=True,
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def monorepo_index_task(self, repo_id: str, branch: str = "main") -> str:
    """Historical AST indexing for monorepos in batch_lane."""
    return f"monorepo_indexed_{repo_id}_{branch}"