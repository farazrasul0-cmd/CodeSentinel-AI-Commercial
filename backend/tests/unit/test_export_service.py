"""Unit tests for SARIF, Markdown, and Printable HTML Exporters."""

from app.domain.enums import CommentStatus, FindingCategory, FindingSeverity, RiskTier
from app.infrastructure.db.models.analysis_report import AnalysisReport
from app.infrastructure.db.models.defect_prediction import DefectPrediction
from app.infrastructure.db.models.file_metric import FileMetric
from app.infrastructure.db.models.issue import Issue
from app.infrastructure.db.models.review_comment import ReviewComment
from app.services.export_service import ExportService


def _create_mock_report() -> AnalysisReport:
    report = AnalysisReport(
        id="rep-export-1",
        job_id="job-export-1",
        overall_score=84.5,
        maintainability_score=80.0,
        security_score=75.0,
        testing_score=70.0,
        architecture_score=88.0,
        total_files=3,
        total_lines_of_code=350,
        technical_debt_minutes=120,
        summary_metadata={},
    )

    metric = FileMetric(
        report_id=report.id,
        file_path="src/auth/service.py",
        sloc=150,
        cyclomatic_complexity=12,
        cognitive_complexity=14,
        maintainability_index=72.0,
    )

    issue = Issue(
        report_id=report.id,
        rule_id="SEC-SQLI",
        cwe_id="CWE-89",
        category=FindingCategory.SECURITY,
        severity=FindingSeverity.CRITICAL,
        file_path="src/auth/service.py",
        line_start=24,
        line_end=26,
        title="SQL Injection Detected",
        description="Raw SQL concatenation query",
    )

    dp = DefectPrediction(
        report_id=report.id,
        file_path="src/auth/service.py",
        defect_probability=0.82,
        risk_tier=RiskTier.CRITICAL,
        model_version="defect_model_v1",
        shap_factors={},
    )

    rev = ReviewComment(
        report_id=report.id,
        file_path="src/auth/service.py",
        line_number=24,
        comment="**[CRITICAL] SQL Injection** Parameterize database query.",
        suggested_patch="@@ -24,1 +24,1 @@\n- query = f'SELECT * FROM u WHERE id={id}'\n+ query = 'SELECT * FROM u WHERE id=:id'",
        status=CommentStatus.PENDING,
    )

    report.file_metrics = [metric]
    report.issues = [issue]
    report.defect_predictions = [dp]
    report.review_comments = [rev]

    return report


def test_sarif_export_schema_and_results():
    report = _create_mock_report()
    sarif = ExportService.generate_sarif(report)

    # 1. Root structure
    assert sarif.version == "2.1.0"
    assert "sarif-spec" in sarif.schema_uri
    assert len(sarif.runs) == 1

    run = sarif.runs[0]
    assert run.tool.driver.name == "CodeSentinel AI"
    assert len(run.tool.driver.rules) >= 2

    # 2. Results mapping
    assert len(run.results) >= 3  # Static issue, ML defect, AI review

    # Check static finding
    sqli_result = next(r for r in run.results if r.ruleId == "SEC-SQLI")
    assert sqli_result.level == "error"
    assert sqli_result.locations[0].physicalLocation.artifactLocation.uri == "src/auth/service.py"
    assert sqli_result.locations[0].physicalLocation.region.startLine == 24

    # Check ML defect
    ml_result = next(r for r in run.results if r.ruleId == "ML-DEFECT-PROBABILITY-HIGH")
    assert ml_result.level == "error"
    assert "82%" in ml_result.message.text

    # Check AI review with fix patch
    ai_result = next(r for r in run.results if r.ruleId == "AI-HYBRID-CODE-REVIEW")
    assert ai_result.fixes is not None
    assert len(ai_result.fixes) == 1
    assert "SELECT * FROM u" in ai_result.fixes[0].artifactChanges[0].replacements[0].insertedContent.text


def test_markdown_pr_summary_export():
    report = _create_mock_report()
    md = ExportService.generate_markdown_summary(report, repo_name="Backend Core")

    assert "# 🛡️ Software Quality Analysis: Backend Core" in md
    assert "Grade" in md
    assert "Maintainability" in md
    assert "Security" in md
    assert "Prioritized Actionable Roadmap" in md


def test_printable_html_export():
    report = _create_mock_report()
    html_content = ExportService.generate_printable_html(report, repo_name="Backend Core")

    assert "<!DOCTYPE html>" in html_content
    assert "@media print" in html_content
    assert "Backend Core" in html_content
    assert "window.print()" in html_content
    assert "Repository Quality Index" in html_content


def test_sarif_export_empty_report():
    """Verifies that an empty report without findings produces valid SARIF v2.1.0."""
    empty_report = AnalysisReport(
        id="rep-empty",
        job_id="job-empty",
        overall_score=100.0,
        maintainability_score=100.0,
        security_score=100.0,
        testing_score=100.0,
        architecture_score=100.0,
        total_files=0,
        total_lines_of_code=0,
        technical_debt_minutes=0,
        summary_metadata={},
    )
    empty_report.file_metrics = []
    empty_report.issues = []
    empty_report.defect_predictions = []
    empty_report.review_comments = []

    sarif = ExportService.generate_sarif(empty_report)
    assert sarif.version == "2.1.0"
    assert len(sarif.runs) == 1
    assert len(sarif.runs[0].results) == 0


def test_markdown_and_html_with_custom_name():
    """Verifies repository branding in Markdown and HTML outputs."""
    report = _create_mock_report()
    custom_name = "Enterprise/Core-API"

    md = ExportService.generate_markdown_summary(report, repo_name=custom_name)
    assert custom_name in md
    assert "Overall Quality Score:" in md

    html_out = ExportService.generate_printable_html(report, repo_name=custom_name)
    assert custom_name in html_out
    assert "<!DOCTYPE html>" in html_out
    assert "Executive Report" in html_out
