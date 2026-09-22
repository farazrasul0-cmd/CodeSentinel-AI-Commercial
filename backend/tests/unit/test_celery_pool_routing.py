"""Unit tests for Celery task pool isolation, queue routing, and retry policies."""

from app.workers.celery_app import (
    analyze_repository_task,
    celery_app,
    monorepo_index_task,
    pr_review_task,
)


def test_celery_queue_routing_configuration():
    routes = celery_app.conf.task_routes
    assert routes["app.workers.celery_app.pr_review_task"]["queue"] == "pr_lane"
    assert routes["app.workers.celery_app.monorepo_index_task"]["queue"] == "batch_lane"
    assert routes["app.workers.celery_app.analyze_repository_task"]["queue"] == "batch_lane"


def test_celery_task_time_limits_annotations():
    annotations = celery_app.conf.task_annotations
    # PR review has strict interactive SLA time limit (60s)
    pr_limits = annotations["app.workers.celery_app.pr_review_task"]
    assert pr_limits["time_limit"] == 60
    assert pr_limits["soft_time_limit"] == 45

    # Monorepo batch tasks have extended time limits (1800s / 30 mins)
    batch_limits = annotations["app.workers.celery_app.analyze_repository_task"]
    assert batch_limits["time_limit"] == 1800
    assert batch_limits["soft_time_limit"] == 1500


def test_celery_task_retry_configuration():
    # Verify exponential backoff and max retries
    assert pr_review_task.max_retries == 3
    assert pr_review_task.retry_backoff is True

    assert analyze_repository_task.max_retries == 2
    assert analyze_repository_task.retry_backoff is True