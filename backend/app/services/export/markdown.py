"""GitHub PR Markdown summary exporter."""

from typing import Any
from app.infrastructure.db.models.analysis_report import AnalysisReport
from app.services.scoring_service import QualityScorecard, ScoringService


class MarkdownSummaryExporter:
    """Builder for GitHub PR Markdown summaries."""

    @classmethod
    def export(
        cls,
        report: AnalysisReport,
        scorecard: QualityScorecard | None = None,
        repo_name: str = "Repository",
    ) -> str:
        sc = scorecard or ScoringService.calculate_scores(
            file_metrics=report.file_metrics,
            issues=report.issues,
            reviews=report.review_comments,
            defect_predictions=report.defect_predictions,
        )

        grade_badge = f"**Grade {sc.grade}** (`{sc.overall_score:.1f} / 100`)"
        lines = [
            f"# 🛡️ Software Quality Analysis: {repo_name}",
            "",
            f"**Overall Quality Score:** {grade_badge} &nbsp;|&nbsp; **Technical Debt:** `{sc.technical_debt_minutes}` mins",
            "",
            "### 📊 Multi-Pillar Quality Breakdown",
            "",
            "| Quality Pillar | Score | Weight | Grade | Status |",
            "| :--- | :---: | :---: | :---: | :--- |",
        ]

        cls._append_pillars(lines, sc.pillars)
        cls._append_recommendations(lines, sc.recommendations)

        if sc.false_positives_suppressed > 0:
            lines.extend([
                "",
                f"> 💡 **Triangulation Engine Note:** Suppressed `{sc.false_positives_suppressed}` false alarms on non-production test fixtures to prevent alert fatigue.",
            ])

        lines.extend([
            "",
            "---",
            "*Report generated automatically by [CodeSentinel AI](https://github.com/farazrasul0-cmd/CodeSentinel-AI).* "
            "Ingest SARIF log for detailed GitHub Code Scanning annotations.",
        ])

        return "\n".join(lines)

    @staticmethod
    def _append_pillars(lines: list[str], pillars: list[dict[str, Any]]) -> None:
        """Formats and appends tabular breakdown of quality pillars."""
        for p in pillars:
            weight_pct = int(p['weight'] * 100)
            lines.append(
                f"| **{p['name']}** | {p['score']:.1f} / 100 | {weight_pct}% | `{p['grade']}` | {p['summary']} |"
            )

    @staticmethod
    def _append_recommendations(lines: list[str], recs: list[dict[str, Any]]) -> None:
        """Formats and appends top actionable refactoring recommendations."""
        lines.extend(["", "---", "", "### 🎯 Prioritized Actionable Roadmap", ""])
        if recs:
            for r in recs:
                lines.append(
                    f"- **[Rank #{r['rank']}] {r['title']}** (+{r['potential_score_impact']} pts | ~{r['effort_minutes']} mins)"
                )
                lines.append(f"  *{r['description']}*")
        else:
            lines.append("- *No critical refactoring required. Codebase meets quality thresholds.*")
