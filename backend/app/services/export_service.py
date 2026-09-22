"""Report Export Engine: Facade delegating to SARIF, Markdown, and HTML exporters."""

from app.api.v1.schemas.export import SarifLog
from app.infrastructure.db.models.analysis_report import AnalysisReport
from app.services.export.html import HtmlReportExporter
from app.services.export.markdown import MarkdownSummaryExporter
from app.services.export.sarif import SarifExporter
from app.services.scoring_service import QualityScorecard

__all__ = ["ExportService", "SarifExporter", "MarkdownSummaryExporter", "HtmlReportExporter"]


class ExportService:
    """Standardized report export facade conforming to SARIF v2.1.0 and print standards."""

    @staticmethod
    def generate_sarif(
        report: AnalysisReport,
        scorecard: QualityScorecard | None = None,
    ) -> SarifLog:
        """Serializes static findings, ML predictions, and review suggestions into OASIS SARIF v2.1.0."""
        return SarifExporter.export(report, scorecard)

    @staticmethod
    def generate_markdown_summary(
        report: AnalysisReport,
        scorecard: QualityScorecard | None = None,
        repo_name: str = "Repository",
    ) -> str:
        """Produces a structured GitHub PR review comment in standard markdown."""
        return MarkdownSummaryExporter.export(report, scorecard, repo_name)

    @staticmethod
    def generate_printable_html(
        report: AnalysisReport,
        scorecard: QualityScorecard | None = None,
        repo_name: str = "Repository",
    ) -> str:
        """Generates self-contained, standalone printable HTML executive report."""
        return HtmlReportExporter.export(report, scorecard, repo_name)
