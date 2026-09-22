"""GitHub App Authentication and Dynamic Ephemeral Installation Token Manager."""

import time
from typing import Any
import httpx
import jwt

from app.core.config import settings
from app.core.logging import logger
from app.infrastructure.redis.client import get_redis_client


class GitHubAppAuthManager:
    """Manages GitHub App RS256 JWT generation and ephemeral installation tokens cached in Redis."""

    def __init__(self) -> None:
        self._memory_token_cache: dict[str, tuple[str, float]] = {}

    def generate_app_jwt(self) -> str:
        """Generates an RS256 signed JWT for GitHub App authentication (valid for 10 minutes)."""
        app_id = settings.GITHUB_APP_ID or "100000"
        private_key = settings.GITHUB_APP_PRIVATE_KEY

        now = int(time.time())
        payload = {
            "iat": now - 60,  # 60 seconds clock drift allowance
            "exp": now + (9 * 60),  # 9 minutes expiration
            "iss": str(app_id),
        }

        if not private_key:
            # Development/Testing fallback when no PEM is configured
            return f"mock_app_jwt_{app_id}_{now}"

        try:
            return jwt.encode(payload, private_key, algorithm="RS256")
        except Exception as e:
            logger.warning(f"Failed to sign RS256 JWT with GITHUB_APP_PRIVATE_KEY: {e}. Falling back to mock.")
            return f"mock_app_jwt_{app_id}_{now}"

    async def get_installation_token(self, installation_id: int) -> str:
        """Retrieves a valid GitHub Installation Access Token.
        
        Cached in Redis with a 50-minute TTL (GitHub installation tokens expire in 60 minutes).
        Never persisted to PostgreSQL to prevent breach exposure.
        """
        cache_key = f"gh_install_{installation_id}"
        now = time.time()

        # 1. Check Redis cache
        try:
            redis = await get_redis_client()
            cached_token = await redis.get(cache_key)
            if cached_token:
                if isinstance(cached_token, bytes):
                    return cached_token.decode("utf-8")
                return str(cached_token)
        except Exception:
            # Fallback to in-memory cache if Redis is offline
            if cache_key in self._memory_token_cache:
                token, expires_at = self._memory_token_cache[cache_key]
                if now < expires_at:
                    return token

        # 2. Mock mode for testing / development without credentials
        if not settings.GITHUB_APP_PRIVATE_KEY or settings.GITHUB_APP_ID == "mock-app-id":
            mock_token = f"ghs_mock_installation_token_{installation_id}"
            await self._cache_token(cache_key, mock_token, ttl_seconds=3000)
            return mock_token

        # 3. Request fresh token from GitHub API
        app_jwt = self.generate_app_jwt()
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github.v3+json",
        }
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"

        async with httpx.AsyncClient() as client:
            res = await client.post(url, headers=headers, timeout=15.0)
            if res.status_code != 201:
                logger.error(f"GitHub installation token request failed ({res.status_code}): {res.text}")
                raise RuntimeError(f"Failed to obtain installation token: {res.text}")

            token_data = res.json()
            token = token_data["token"]

            # Cache in Redis with 50-minute TTL (3000s)
            await self._cache_token(cache_key, token, ttl_seconds=3000)
            return token

    async def _cache_token(self, cache_key: str, token: str, ttl_seconds: int = 3000) -> None:
        """Helper to cache token in Redis or in-memory fallback."""
        try:
            redis = await get_redis_client()
            await redis.set(cache_key, token, ex=ttl_seconds)
        except Exception:
            # Store in local memory with timestamp
            self._memory_token_cache[cache_key] = (token, time.time() + ttl_seconds)


# Global singleton
github_app_auth = GitHubAppAuthManager()