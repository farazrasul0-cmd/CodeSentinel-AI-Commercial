"""Commercial Diff-Targeted Pull Request Analysis Engine."""

import textwrap
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.logging import logger
from app.domain.enums import FindingCategory, FindingSeverity
from app.domain.models import FileDiff
from app.infrastructure.git.diff_parser import GitDiffParser
from app.infrastructure.github.client import BaseGitHubPRClient, github_pr_client
from app.infrastructure.static_analysis.engine import StaticAnalysisEngine


@dataclass
class InlineSuggestion:
    path: str
    line: int
    rule_id: str
    severity: FindingSeverity
    title: str
    comment_body: str
    suggestion_code: str | None = None


@dataclass
class PRAnalysisResult:
    repo_full_name: str
    pr_number: int
    commit_sha: str
    files_analyzed: int
    total_added_lines: int
    issues: list[dict[str, Any]] = field(default_factory=list)
    inline_suggestions: list[InlineSuggestion] = field(default_factory=list)
    quality_gate_passed: bool = True
    rqi_delta: float = 0.0
    summary_markdown: str = ""


class PRAnalysisService:
    """Performs low-latency, diff-scoped static security & quality analysis on Pull Requests."""

    def __init__(self, client: BaseGitHubPRClient | None = None) -> None:
        self.client = client or github_pr_client

    async def analyze_pull_request(
        self,
        repo_full_name: str,
        pr_number: int,
        commit_sha: str,
    ) -> PRAnalysisResult:
        """Analyzes modified files in the PR diff and calculates quality gate compliance."""
        logger.info(f"Starting diff-targeted analysis for {repo_full_name} PR #{pr_number} @ {commit_sha[:7]}")

        pr_files = await self.client.get_pr_files(repo_full_name, pr_number)
        if not pr_files:
            return PRAnalysisResult(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                commit_sha=commit_sha,
                files_analyzed=0,
                total_added_lines=0,
                quality_gate_passed=True,
                rqi_delta=0.0,
            )

        all_issues: list[dict[str, Any]] = []
        all_inline: list[InlineSuggestion] = []
        total_added = 0

        for f in pr_files:
            filename = f.get("filename", "")
            patch = f.get("patch", "")
            if not patch:
                continue

            total_added += f.get("additions", 0)

            # Parse diff hunks to identify exact modified line numbers
            full_patch_text = f"diff --git a/{filename} b/{filename}\n--- a/{filename}\n+++ b/{filename}\n{patch}"
            file_diffs = GitDiffParser.parse_diff(full_patch_text)

            added_line_numbers: set[int] = set()
            hunk_offset = 0
            if file_diffs and file_diffs[0].hunks:
                for h in file_diffs[0].hunks:
                    added_line_numbers.update(h.added_lines)
                hunk_offset = file_diffs[0].hunks[0].new_start - 1

            reconstructed_code = self._reconstruct_file_from_patch(patch)
            if filename.endswith(".py"):
                dedented_code = textwrap.dedent(reconstructed_code)
                res = StaticAnalysisEngine.analyze_python_file(filename, dedented_code)

                for issue in res.issues:
                    # Map relative snippet line to file line
                    effective_line = (issue.line_start + hunk_offset) if hunk_offset > 0 else issue.line_start

                    # Verify that finding is in diff or directly affected
                    is_in_diff = (effective_line in added_line_numbers) or len(added_line_numbers) == 0 or issue.rule_id != "PARSE-SYNTAX-ERROR"

                    if is_in_diff and issue.rule_id != "PARSE-SYNTAX-ERROR":
                        issue_dict = {
                            "rule_id": issue.rule_id,
                            "severity": issue.severity,
                            "category": issue.category,
                            "file_path": filename,
                            "line_start": effective_line,
                            "line_end": (issue.line_end + hunk_offset) if issue.line_end and hunk_offset > 0 else effective_line,
                            "title": issue.title,
                            "description": issue.description,
                            "remediation": issue.remediation,
                        }
                        all_issues.append(issue_dict)

                        suggestion_block = self._generate_suggestion_code(issue)
                        all_inline.append(
                            InlineSuggestion(
                                path=filename,
                                line=effective_line,
                                rule_id=issue.rule_id,
                                severity=FindingSeverity(issue.severity) if isinstance(issue.severity, str) else issue.severity,
                                title=issue.title,
                                comment_body=self._format_inline_comment(issue, suggestion_block),
                                suggestion_code=suggestion_block,
                            )
                        )

        severity_order = {
            FindingSeverity.CRITICAL: 0,
            FindingSeverity.HIGH: 1,
            FindingSeverity.MEDIUM: 2,
            FindingSeverity.LOW: 3,
            FindingSeverity.INFO: 4,
        }
        all_inline.sort(key=lambda s: severity_order.get(s.severity, 99))
        capped_inline = all_inline[: settings.PR_MAX_INLINE_COMMENTS]

        has_critical = any(i["severity"] == "CRITICAL" for i in all_issues)
        has_too_many_highs = sum(1 for i in all_issues if i["severity"] == "HIGH") > 2
        quality_gate_passed = not (has_critical or has_too_many_highs)

        rqi_penalty = (
            sum(15 for i in all_issues if i["severity"] == "CRITICAL")
            + sum(7 for i in all_issues if i["severity"] == "HIGH")
            + sum(2 for i in all_issues if i["severity"] == "MEDIUM")
        )
        rqi_delta = round(max(-100.0, -rqi_penalty), 1) if all_issues else 0.0

        return PRAnalysisResult(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            commit_sha=commit_sha,
            files_analyzed=len(pr_files),
            total_added_lines=total_added,
            issues=all_issues,
            inline_suggestions=capped_inline,
            quality_gate_passed=quality_gate_passed,
            rqi_delta=rqi_delta,
        )

    @staticmethod
    def _reconstruct_file_from_patch(patch: str) -> str:
        """Extracts context and added lines from a patch into parseable source code."""
        lines = []
        for line in patch.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                lines.append(line[1:])
            elif line.startswith(" ") or (not line.startswith("-") and not line.startswith("@")):
                lines.append(line[1:] if line.startswith(" ") else line)
        return "\n".join(lines)

    @staticmethod
    def _generate_suggestion_code(issue: Any) -> str | None:
        """Produces a 1-click GitHub suggestion code snippet if an automated fix is known."""
        rule_id = getattr(issue, "rule_id", "")
        if "SQLI" in rule_id or "SQL" in rule_id:
            return "cursor.execute('SELECT * FROM accounts WHERE id = %s', (user_id,))"
        if "SECRET" in rule_id:
            return "api_key = os.environ.get('API_SECRET_KEY')"
        if "SHELL" in rule_id or "COMMAND" in rule_id:
            return "subprocess.run(['cmd_name', arg1], shell=False, check=True)"
        return None

    @classmethod
    def _format_inline_comment(cls, issue: Any, suggestion_code: str | None) -> str:
        """Formats an inline PR comment with markdown badge and suggestion block."""
        body = f"### ⚠️ CodeSentinel Alert: `{issue.rule_id}` ({issue.severity})\n\n"
        body += f"**{issue.title}**\n\n{issue.description}\n\n"
        if suggestion_code:
            body += f"#### Recommended 1-Click Fix:\n```suggestion\n{suggestion_code}\n```\n"
        elif issue.remediation:
            body += f"**Remediation:** {issue.remediation}\n"
        return body