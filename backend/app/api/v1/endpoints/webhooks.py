"""Commercial GitHub Webhook Ingestion with In-Place PR Reviews and Quality Gates."""

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.domain.enums import JobStatus
from app.infrastructure.db.models.analysis_job import AnalysisJob
from app.infrastructure.db.models.organization import Organization
from app.infrastructure.db.models.repository import Repository
from app.infrastructure.db.session import get_db_session
from app.infrastructure.github.client import github_pr_client
from app.infrastructure.github.webhook_handler import github_webhook_handler
from app.services.entitlement_service import EntitlementService
from app.services.pr_analysis_service import PRAnalysisService
from app.services.pr_comment_service import PRCommentService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def receive_github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Ingests and validates GitHub App webhooks, executing diff-targeted scans and in-place reviews."""
    raw_body = await request.body()

    # 1. Constant-time HMAC SHA-256 signature verification
    if not github_webhook_handler.verify_signature(raw_body, x_hub_signature_256):
        logger.warning("Rejected webhook due to invalid X-Hub-Signature-256 signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Hub-Signature-256 signature",
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook JSON payload: {e}",
        ) from e

    # 2. Handle GitHub App Installation Events
    if x_github_event == "installation":
        action = payload.get("action")
        installation_id = payload.get("installation", {}).get("id")
        account_login = payload.get("installation", {}).get("account", {}).get("login")

        if action == "created" and installation_id and account_login:
            stmt = select(Organization).where(Organization.slug.like(f"{account_login.lower()}%"))
            res = await session.execute(stmt)
            org = res.scalars().first()
            if org:
                org.github_installation_id = installation_id
                await session.commit()
                logger.info(f"Linked GitHub installation {installation_id} to Organization '{org.name}'")

        return {"status": "installation_handled", "action": action, "installation_id": installation_id}

    # 3. Handle Pull Request Events
    if x_github_event == "pull_request":
        action = payload.get("action")
        if action not in ("opened", "synchronize", "reopened"):
            return {"status": "ignored", "action": action, "event": "pull_request"}

        pr = payload.get("pull_request", {})
        repo_data = payload.get("repository", {})
        repo_full_name = repo_data.get("full_name") or "unknown/repo"
        clone_url = repo_data.get("clone_url", "")
        pr_number = pr.get("number")
        head_sha = pr.get("head", {}).get("sha")
        head_ref = pr.get("head", {}).get("ref")

        if not (pr_number and head_sha):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Missing pr.number or head.sha in pull_request payload",
            )

        # Ensure repository record exists
        stmt = select(Repository).where(Repository.url == clone_url)
        res = await session.execute(stmt)
        repo_record = res.scalar_one_or_none()
        if not repo_record:
            repo_record = Repository(
                name=repo_data.get("name", repo_full_name.split("/")[-1]),
                url=clone_url or f"https://github.com/{repo_full_name}",
                default_branch=repo_data.get("default_branch", "main"),
            )
            session.add(repo_record)
            await session.commit()
            await session.refresh(repo_record)

        # 4. Entitlement & Seat Metering Check
        commit_author = pr.get("user", {}).get("login") or "author"
        author_email = pr.get("user", {}).get("email") or f"{commit_author}@users.noreply.github.com"
        quota_warning = None

        if repo_record.organization_id:
            org_stmt = select(Organization).where(Organization.id == repo_record.organization_id)
            org_res = await session.execute(org_stmt)
            org = org_res.scalar_one_or_none()
            if org:
                is_permitted, quota_warning, _ = await EntitlementService.evaluate_scan_permission(
                    session=session,
                    org=org,
                    is_private_repo=repo_data.get("private", False),
                    author_email=author_email,
                )
                if not is_permitted:
                    return {
                        "status": "rejected",
                        "reason": quota_warning,
                        "pr_number": pr_number,
                    }

        # Log analysis job
        job = AnalysisJob(
            repository_id=repo_record.id,
            branch=head_ref or "pr-branch",
            commit_sha=head_sha,
            status=JobStatus.COMPLETED,
            current_stage="PR_DIFF_REVIEW_COMPLETED",
            progress_percent=100.0,
        )
        session.add(job)
        await session.commit()

        # Run Diff-Targeted PR Analysis
        analysis_service = PRAnalysisService(client=github_pr_client)
        analysis_result = await analysis_service.analyze_pull_request(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            commit_sha=head_sha,
        )

        # Append soft-gating notice if active seats exceed quota
        if quota_warning:
            analysis_result.summary_markdown += f"\n\n> ⚠️ **Quota Notice**: {quota_warning}\n"

        # Orchestrate In-Place Summary, Inline Fixes, and Check Run
        comment_service_res = await PRCommentService.execute_pr_review_actions(analysis_result, client=github_pr_client)

        return {
            "status": "accepted",
            "job_id": job.id,
            "repository_id": repo_record.id,
            "action": action,
            "repo": repo_full_name,
            "pr_number": pr_number,
            "commit_sha": head_sha,
            "quality_gate_passed": analysis_result.quality_gate_passed,
            "issues_count": len(analysis_result.issues),
            "quota_warning": quota_warning,
            "review_actions": comment_service_res,
        }

    return {"status": "event_acknowledged", "event": x_github_event}