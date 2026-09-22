"""GitHub REST API Client for Pull Requests, Single-Comment Upserts, and Check Runs."""

from abc import ABC, abstractmethod
from typing import Any
import httpx

from app.core.logging import logger

SUMMARY_COMMENT_TAG = "<!-- codesentinel-pr-summary -->"


class BaseGitHubPRClient(ABC):
    """Abstract interface for GitHub PR actions, file fetching, and check runs."""

    @abstractmethod
    async def get_pr_files(self, repo_full_name: str, pr_number: int) -> list[dict[str, Any]]:
        """Retrieves modified files and unified patches in a PR."""
        pass

    @abstractmethod
    async def upsert_pr_summary_comment(
        self,
        repo_full_name: str,
        pr_number: int,
        markdown_body: str,
    ) -> dict[str, Any]:
        """Updates the existing CodeSentinel summary comment in place, or creates it if none exists."""
        pass

    @abstractmethod
    async def post_inline_review(
        self,
        repo_full_name: str,
        pr_number: int,
        commit_sha: str,
        summary_body: str,
        comments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Posts structured inline review suggestions with 1-click apply blocks."""
        pass

    @abstractmethod
    async def create_or_update_check_run(
        self,
        repo_full_name: str,
        head_sha: str,
        name: str = "CodeSentinel Quality Gate",
        status: str = "completed",
        conclusion: str | None = "success",
        title: str = "Quality Gate Passed",
        summary: str = "",
        check_run_id: int | None = None,
    ) -> int:
        """Emits or updates a GitHub Check Run on the commit."""
        pass


class MockGitHubPRClient(BaseGitHubPRClient):
    """In-memory mock GitHub client for unit testing and local development."""

    def __init__(self) -> None:
        self.mock_files: list[dict[str, Any]] = [
            {
                "filename": "app/services/payment.py",
                "status": "modified",
                "additions": 4,
                "deletions": 1,
                "patch": "@@ -10,2 +10,4 @@ def process_payment(user_id, amount):\n-    pass\n+    cursor.execute(f\"SELECT * FROM accounts WHERE id = {user_id}\")\n+    api_key = \"production_unvaulted_secret_token_abcdef123456\"\n",
            }
        ]
        self.comments: list[dict[str, Any]] = []
        self.reviews: list[dict[str, Any]] = []
        self.check_runs: list[dict[str, Any]] = []

    async def get_pr_files(self, repo_full_name: str, pr_number: int) -> list[dict[str, Any]]:
        return self.mock_files

    async def upsert_pr_summary_comment(
        self,
        repo_full_name: str,
        pr_number: int,
        markdown_body: str,
    ) -> dict[str, Any]:
        tagged_body = f"{SUMMARY_COMMENT_TAG}\n{markdown_body}"
        for c in self.comments:
            if c["repo"] == repo_full_name and c["pr"] == pr_number and SUMMARY_COMMENT_TAG in c["body"]:
                c["body"] = tagged_body
                c["updated"] = True
                logger.info(f"[MockGitHub] In-place PATCH updated summary comment {c['id']} on PR #{pr_number}")
                return c

        new_comment = {
            "id": len(self.comments) + 1,
            "repo": repo_full_name,
            "pr": pr_number,
            "body": tagged_body,
            "updated": False,
        }
        self.comments.append(new_comment)
        logger.info(f"[MockGitHub] POST created new summary comment {new_comment['id']} on PR #{pr_number}")
        return new_comment

    async def post_inline_review(
        self,
        repo_full_name: str,
        pr_number: int,
        commit_sha: str,
        summary_body: str,
        comments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        review = {
            "id": len(self.reviews) + 1,
            "repo": repo_full_name,
            "pr": pr_number,
            "commit_sha": commit_sha,
            "body": summary_body,
            "comments": comments,
        }
        self.reviews.append(review)
        logger.info(f"[MockGitHub] Posted review with {len(comments)} inline comments on PR #{pr_number}")
        return review

    async def create_or_update_check_run(
        self,
        repo_full_name: str,
        head_sha: str,
        name: str = "CodeSentinel Quality Gate",
        status: str = "completed",
        conclusion: str | None = "success",
        title: str = "Quality Gate Passed",
        summary: str = "",
        check_run_id: int | None = None,
    ) -> int:
        if check_run_id is not None:
            for cr in self.check_runs:
                if cr["id"] == check_run_id:
                    cr.update({"status": status, "conclusion": conclusion, "title": title, "summary": summary})
                    return check_run_id

        new_id = len(self.check_runs) + 101
        self.check_runs.append({
            "id": new_id,
            "repo": repo_full_name,
            "head_sha": head_sha,
            "name": name,
            "status": status,
            "conclusion": conclusion,
            "title": title,
            "summary": summary,
        })
        logger.info(f"[MockGitHub] Emitted Check Run {new_id} ({status}: {conclusion})")
        return new_id


class LiveGitHubPRClient(BaseGitHubPRClient):
    """Production GitHub REST API Client using an installation access token."""

    def __init__(self, token: str) -> None:
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CodeSentinel-AI-Commercial",
        }

    async def get_pr_files(self, repo_full_name: str, pr_number: int) -> list[dict[str, Any]]:
        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/files"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=self.headers, timeout=20.0)
            res.raise_for_status()
            return res.json()

    async def upsert_pr_summary_comment(
        self,
        repo_full_name: str,
        pr_number: int,
        markdown_body: str,
    ) -> dict[str, Any]:
        tagged_body = f"{SUMMARY_COMMENT_TAG}\n{markdown_body}"
        comments_url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"

        async with httpx.AsyncClient() as client:
            res = await client.get(comments_url, headers=self.headers, timeout=15.0)
            if res.status_code == 200:
                comments = res.json()
                for c in comments:
                    if SUMMARY_COMMENT_TAG in c.get("body", ""):
                        patch_url = f"https://api.github.com/repos/{repo_full_name}/issues/comments/{c['id']}"
                        patch_res = await client.patch(patch_url, headers=self.headers, json={"body": tagged_body})
                        patch_res.raise_for_status()
                        return patch_res.json()

            post_res = await client.post(comments_url, headers=self.headers, json={"body": tagged_body})
            post_res.raise_for_status()
            return post_res.json()

    async def post_inline_review(
        self,
        repo_full_name: str,
        pr_number: int,
        commit_sha: str,
        summary_body: str,
        comments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"
        payload = {
            "commit_id": commit_sha,
            "body": summary_body,
            "event": "COMMENT",
            "comments": comments,
        }
        async with httpx.AsyncClient() as client:
            res = await client.post(url, headers=self.headers, json=payload, timeout=20.0)
            res.raise_for_status()
            return res.json()

    async def create_or_update_check_run(
        self,
        repo_full_name: str,
        head_sha: str,
        name: str = "CodeSentinel Quality Gate",
        status: str = "completed",
        conclusion: str | None = "success",
        title: str = "Quality Gate Passed",
        summary: str = "",
        check_run_id: int | None = None,
    ) -> int:
        async with httpx.AsyncClient() as client:
            if check_run_id is not None:
                url = f"https://api.github.com/repos/{repo_full_name}/check-runs/{check_run_id}"
                payload: dict[str, Any] = {"status": status, "output": {"title": title, "summary": summary}}
                if conclusion:
                    payload["conclusion"] = conclusion
                res = await client.patch(url, headers=self.headers, json=payload, timeout=15.0)
                res.raise_for_status()
                return check_run_id
            else:
                url = f"https://api.github.com/repos/{repo_full_name}/check-runs"
                payload = {
                    "name": name,
                    "head_sha": head_sha,
                    "status": status,
                    "output": {"title": title, "summary": summary},
                }
                if conclusion and status == "completed":
                    payload["conclusion"] = conclusion
                res = await client.post(url, headers=self.headers, json=payload, timeout=15.0)
                res.raise_for_status()
                return res.json()["id"]


# Default global client (swappable for testing)
github_pr_client: BaseGitHubPRClient = MockGitHubPRClient()
