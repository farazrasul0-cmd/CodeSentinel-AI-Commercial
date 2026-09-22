"""Celery Application Configuration with Dual-Lane Priority Queues."""

import asyncio

from celery import Celery
from kombu import Queue

from app.core.config import settings

celery_app = Celery(
    "quality_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Dual-lane queue architecture: Fast interactive PR scans vs heavy monorepo batch jobs
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_queues=[
        Queue(settings.CELERY_PR_QUEUE, routing_key=f"{settings.CELERY_PR_QUEUE}.#"),
        Queue(settings.CELERY_BATCH_QUEUE, routing_key=f"{settings.CELERY_BATCH_QUEUE}.#"),
        Queue("cpu_heavy", routing_key="cpu_heavy.#"),
        Queue("llm_calls", routing_key="llm_calls.#"),
    ],
    task_default_queue=settings.CELERY_BATCH_QUEUE,
    task_routes={
        "app.workers.tasks.pr_review_task": {"queue": settings.CELERY_PR_QUEUE},
        "app.workers.tasks.monorepo_index_task": {"queue": settings.CELERY_BATCH_QUEUE},
        "app.workers.celery_app.analyze_repository_task": {"queue": settings.CELERY_BATCH_QUEUE},
        "app.workers.tasks.static_tasks.*": {"queue": "cpu_heavy"},
        "app.workers.tasks.ml_tasks.*": {"queue": "cpu_heavy"},
        "app.workers.tasks.llm_tasks.*": {"queue": "llm_calls"},
    },
)


@celery_app.task(name="app.workers.celery_app.analyze_repository_task")
def analyze_repository_task(job_id: str) -> str:
    """Synchronous Celery wrapper running the async ingestion pipeline."""
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
        report_id = loop.run_until_complete(_run())
        return report_id
    finally:
        loop.close()