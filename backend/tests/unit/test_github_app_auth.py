"""Unit tests for GitHub App authentication and ephemeral token caching."""

import pytest
from app.infrastructure.github.app_auth import GitHubAppAuthManager


@pytest.mark.asyncio
async def test_app_jwt_generation_default():
    mgr = GitHubAppAuthManager()
    jwt_token = mgr.generate_app_jwt()
    assert jwt_token is not None
    assert "mock_app_jwt" in jwt_token


@pytest.mark.asyncio
async def test_installation_token_caching_and_reuse():
    mgr = GitHubAppAuthManager()
    installation_id = 987654321

    # First call: Generates and caches token
    tok1 = await mgr.get_installation_token(installation_id)
    assert tok1.startswith("ghs_")

    # Second call: Returns cached token from memory/redis without regenerating
    tok2 = await mgr.get_installation_token(installation_id)
    assert tok1 == tok2