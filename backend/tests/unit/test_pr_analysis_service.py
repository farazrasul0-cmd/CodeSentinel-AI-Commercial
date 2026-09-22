"""Unit tests for diff-targeted PR scanning and 1-click suggestion generation."""

import pytest
from app.infrastructure.github.client import MockGitHubPRClient
from app.services.pr_analysis_service import PRAnalysisService


@pytest.mark.asyncio
async def test_pr_analysis_diff_targeted_detection():
    mock_client = MockGitHubPRClient()
    # Mock client returns a patch with SQL injection and hardcoded secret
    service = PRAnalysisService(client=mock_client)

    result = await service.analyze_pull_request(
        repo_full_name="acme/payment-api",
        pr_number=42,
        commit_sha="a1b2c3d4e5f6071829",
    )

    assert result.repo_full_name == "acme/payment-api"
    assert result.pr_number == 42
    assert result.files_analyzed == 1
    assert len(result.issues) >= 1

    # Verify quality gate failed due to critical finding (SQL injection / hardcoded secret)
    assert result.quality_gate_passed is False
    assert result.rqi_delta < 0

    # Verify inline suggestions formatting with suggestion blocks
    assert len(result.inline_suggestions) > 0
    first_suggestion = result.inline_suggestions[0]
    assert first_suggestion.suggestion_code is not None
    assert "```suggestion" in first_suggestion.comment_body


@pytest.mark.asyncio
async def test_pr_analysis_clean_diff():
    mock_client = MockGitHubPRClient()
    # Set clean patch
    mock_client.mock_files = [
        {
            "filename": "app/clean_code.py",
            "status": "modified",
            "additions": 4,
            "deletions": 0,
            "patch": "@@ -1,2 +1,6 @@\n def add(a: int, b: int) -> int:\n+    # Clean helper\n+    return a + b\n",
        }
    ]
    service = PRAnalysisService(client=mock_client)

    result = await service.analyze_pull_request(
        repo_full_name="acme/clean-repo",
        pr_number=10,
        commit_sha="c1e2a3n4",
    )

    assert result.quality_gate_passed is True
    assert len(result.issues) == 0
    assert result.rqi_delta == 0.0