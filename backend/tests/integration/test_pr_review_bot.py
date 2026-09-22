"""Integration tests for GitHub PR review bot, in-place summary comments, and Check Runs."""

import hashlib
import hmac
import json
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.github.client import github_pr_client, MockGitHubPRClient
from app.infrastructure.github.webhook_handler import github_webhook_handler


@pytest.mark.asyncio
async def test_pr_review_webhook_in_place_commenting(async_client: AsyncClient, db_session: AsyncSession):
    mock_client = MockGitHubPRClient()
    import app.api.v1.endpoints.webhooks as webhooks_module

    webhooks_module.github_pr_client = mock_client
    secret = github_webhook_handler.secret or "test-secret-key-123"

    # 1. First push: pull_request.opened
    payload_pr_opened = {
        "action": "opened",
        "repository": {
            "name": "payment-service",
            "full_name": "acme/payment-service",
            "clone_url": "https://github.com/acme/payment-service.git",
            "default_branch": "main",
        },
        "pull_request": {
            "number": 99,
            "head": {
                "ref": "feat/payments",
                "sha": "1111111111111111111111111111111111111111",
            },
        },
    }
    raw_body_1 = json.dumps(payload_pr_opened).encode("utf-8")
    sig_1 = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body_1, hashlib.sha256).hexdigest()

    res_1 = await async_client.post(
        "/api/v1/webhooks/github",
        content=raw_body_1,
        headers={
            "X-Hub-Signature-256": sig_1,
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert res_1.status_code == 202
    data_1 = res_1.json()
    assert data_1["status"] == "accepted"
    assert data_1["review_actions"]["is_summary_updated"] is False
    first_comment_id = data_1["review_actions"]["summary_comment_id"]
    assert first_comment_id is not None
    assert data_1["review_actions"]["check_run_id"] is not None

    # 2. Second push on same PR: pull_request.synchronize
    payload_pr_sync = {
        "action": "synchronize",
        "repository": {
            "name": "payment-service",
            "full_name": "acme/payment-service",
            "clone_url": "https://github.com/acme/payment-service.git",
            "default_branch": "main",
        },
        "pull_request": {
            "number": 99,
            "head": {
                "ref": "feat/payments",
                "sha": "2222222222222222222222222222222222222222",
            },
        },
    }
    raw_body_2 = json.dumps(payload_pr_sync).encode("utf-8")
    sig_2 = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body_2, hashlib.sha256).hexdigest()

    res_2 = await async_client.post(
        "/api/v1/webhooks/github",
        content=raw_body_2,
        headers={
            "X-Hub-Signature-256": sig_2,
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert res_2.status_code == 202
    data_2 = res_2.json()
    assert data_2["status"] == "accepted"
    # CRITICAL COMMERCIAL BEHAVIOR: In-place update prevents duplicate comment spam!
    assert data_2["review_actions"]["is_summary_updated"] is True
    assert data_2["review_actions"]["summary_comment_id"] == first_comment_id