"""Pull Request Comment Formatting and Review Orchestration Service."""

from typing import Any

from app.core.logging import logger
from app.infrastructure.github.client import BaseGitHubPRClient, SUMMARY_COMMENT_TAG, github_pr_client
from app.services.pr_analysis_service import PRAnalysisResult


class PRCommentService:
    """Orchestrates single in-place summary comment updates, inline suggestions, and check runs."""

    @classmethod
    def format_summary_markdown(cls, result: PRAnalysisResult) -> str:
        """Generates an executive, non-spammy Markdown report with quality gate status."""
        gate_badge = "✅ **PASSED**" if result.quality_gate_passed else "❌ **FAILED**"
        delta_display = f"{result.rqi_delta:+.1f}%" if result.rqi_delta != 0 else "0.0%"

        # Count findings by severity
        crit_count = sum(1 for i in result.issues if i.get("severity") == "CRITICAL")
        high_count = sum(1 for i in result.issues if i.get("severity") == "HIGH")
        med_count = sum(1 for i in result.issues if i.get("severity") == "MEDIUM")
        low_count = sum(1 for i in result.issues if i.get("severity") in ("LOW", "INFO"))

        md = f"{SUMMARY_COMMENT_TAG}\n"
        md += f"## 🛡️ CodeSentinel AI Quality Report\n\n"
        md += f"**Quality Gate:** {gate_badge} &nbsp;|&nbsp; "
        md += f"**Health Impact:** `{delta_display}` &nbsp;|&nbsp; "
        md += f"**Files Analyzed:** `{result.files_analyzed}`\n\n"

        md += "### 📊 Findings Overview\n\n"
        md += "| Severity | Count | Gate Policy |\n"
        md += "| :--- | :---: | :--- |\n"
        md += f"| 🔴 **Critical** | `{crit_count}` | Must be `0` to merge |\n"
        md += f"| 🟠 **High** | `{high_count}` | Max `2` allowed |\n"
        md += f"| 🟡 **Medium** | `{med_count}` | Advisory |\n"
        md += f"| 🔵 **Low / Info** | `{low_count}` | Advisory |\n\n"

        if result.inline_suggestions:
            md += "### ⚡ Top Remediations with 1-Click Fixes\n\n"
            for idx, s in enumerate(result.inline_suggestions[:3], 1):
                md += f"{idx}. **[`{s.path}:{s.line}`]({s.path})** — `{s.rule_id}`: {s.title}\n"
            md += "\n*Inline code suggestions have been added directly to the PR diff lines below.*\n\n"
        elif not result.issues:
            md += "✨ **Clean Diff**: No static code smells, complexity spikes, or security flaws detected in this PR.\n\n"

        md += "---\n"
        md += f"*Analysis completed for commit `{result.commit_sha[:7]}`. CodeSentinel automatically updates this comment on subsequent pushes.*\n"
        return md

    @classmethod
    async def execute_pr_review_actions(
        cls,
        result: PRAnalysisResult,
        client: BaseGitHubPRClient | None = None,
    ) -> dict[str, Any]:
        """Publishes in-place summary comment, inline review comments, and GitHub check-run."""
        gh_client = client or github_pr_client
        summary_md = cls.format_summary_markdown(result)
        result.summary_markdown = summary_md

        # 1. Update or create single summary comment (In-Place Upsert)
        comment_record = await gh_client.upsert_pr_summary_comment(
            repo_full_name=result.repo_full_name,
            pr_number=result.pr_number,
            markdown_body=summary_md,
        )

        # 2. Post inline review suggestions if findings exist
        review_record = None
        if result.inline_suggestions:
            inline_payload = [
                {
                    "path": s.path,
                    "line": s.line,
                    "side": "RIGHT",
                    "body": s.comment_body,
                }
                for s in result.inline_suggestions
            ]
            review_summary = f"CodeSentinel detected {len(inline_payload)} actionable issues in this diff."
            review_record = await gh_client.post_inline_review(
                repo_full_name=result.repo_full_name,
                pr_number=result.pr_number,
                commit_sha=result.commit_sha,
                summary_body=review_summary,
                comments=inline_payload,
            )

        # 3. Emit GitHub Check Run
        conclusion = "success" if result.quality_gate_passed else "failure"
        title = "Quality Gate Passed" if result.quality_gate_passed else "Quality Gate Failed (Critical/High findings)"
        check_run_id = await gh_client.create_or_update_check_run(
            repo_full_name=result.repo_full_name,
            head_sha=result.commit_sha,
            name="CodeSentinel Quality Gate",
            status="completed",
            conclusion=conclusion,
            title=title,
            summary=f"Found {len(result.issues)} issues across {result.files_analyzed} files in PR #{result.pr_number}.",
        )

        logger.info(
            f"Completed PR #{result.pr_number} actions: Comment ID={comment_record.get('id')}, Check Run={check_run_id}, Gate={conclusion}"
        )

        return {
            "summary_comment_id": comment_record.get("id"),
            "is_summary_updated": comment_record.get("updated", False),
            "inline_reviews_count": len(result.inline_suggestions),
            "check_run_id": check_run_id,
            "conclusion": conclusion,
        }