"""OASIS SARIF v2.1.0 log file exporter."""

from app.api.v1.schemas.export import (
    SarifArtifactChange,
    SarifArtifactLocation,
    SarifFix,
    SarifLocation,
    SarifLog,
    SarifMessage,
    SarifPhysicalLocation,
    SarifRegion,
    SarifReplacement,
    SarifReportingDescriptor,
    SarifResult,
    SarifRun,
    SarifTool,
    SarifToolComponent,
)
from app.domain.enums import CommentStatus, FindingSeverity
from app.infrastructure.db.models.analysis_report import AnalysisReport
from app.infrastructure.db.models.defect_prediction import DefectPrediction
from app.infrastructure.db.models.issue import Issue
from app.infrastructure.db.models.review_comment import ReviewComment
from app.services.scoring_service import QualityScorecard


class SarifExporter:
    """Builder for OASIS SARIF v2.1.0 log files."""

    @classmethod
    def export(cls, report: AnalysisReport, scorecard: QualityScorecard | None = None) -> SarifLog:
        """Serializes static findings, ML predictions, and review suggestions into OASIS SARIF v2.1.0."""
        rules_map: dict[str, SarifReportingDescriptor] = {}
        results: list[SarifResult] = []

        # 1. Map Static Analysis Issues
        for issue in report.issues:
            cls._map_issue(issue, rules_map, results)

        # 2. Map ML Defect Predictions (High and Critical risk tiers)
        for dp in report.defect_predictions:
            cls._map_defect_prediction(dp, rules_map, results)

        # 3. Map Confirmed Hybrid AI Review Comments & Suggested Patches
        for rev in report.review_comments or []:
            cls._map_review_comment(rev, rules_map, results)

        tool = SarifTool(
            driver=SarifToolComponent(
                name="CodeSentinel AI",
                version="1.0.0",
                rules=list(rules_map.values()),
            )
        )

        return SarifLog(runs=[SarifRun(tool=tool, results=results)])

    @staticmethod
    def _map_issue(
        issue: Issue,
        rules_map: dict[str, SarifReportingDescriptor],
        results: list[SarifResult],
    ) -> None:
        rule_id = issue.rule_id or f"RULE-{issue.category}"
        if rule_id not in rules_map:
            cwe_uri = (
                f"https://cwe.mitre.org/data/definitions/{issue.cwe_id.replace('CWE-', '')}.html"
                if issue.cwe_id
                else None
            )
            is_error = issue.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
            rules_map[rule_id] = SarifReportingDescriptor(
                id=rule_id,
                name=issue.title,
                shortDescription=SarifMessage(text=issue.title),
                fullDescription=SarifMessage(text=issue.description or issue.title),
                helpUri=cwe_uri,
                defaultConfiguration={"level": "error" if is_error else "warning"},
            )

        level = (
            "error"
            if issue.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
            else ("warning" if issue.severity == FindingSeverity.MEDIUM else "note")
        )

        results.append(
            SarifResult(
                ruleId=rule_id,
                level=level,  # type: ignore[arg-type]
                message=SarifMessage(text=f"[{issue.severity}] {issue.title}: {issue.description}"),
                locations=[
                    SarifLocation(
                        physicalLocation=SarifPhysicalLocation(
                            artifactLocation=SarifArtifactLocation(uri=issue.file_path),
                            region=SarifRegion(
                                startLine=max(1, issue.line_start),
                                endLine=max(issue.line_start, issue.line_end),
                            ),
                        )
                    )
                ],
            )
        )

    @staticmethod
    def _map_defect_prediction(
        dp: DefectPrediction,
        rules_map: dict[str, SarifReportingDescriptor],
        results: list[SarifResult],
    ) -> None:
        prob = float(dp.defect_probability or 0.0)
        tier = str(dp.risk_tier)
        if tier not in ("CRITICAL", "HIGH") and prob < 0.65:
            return

        rule_id = "ML-DEFECT-PROBABILITY-HIGH"
        if rule_id not in rules_map:
            rules_map[rule_id] = SarifReportingDescriptor(
                id=rule_id,
                name="High Defect Probability",
                shortDescription=SarifMessage(text="High Defect Probability Predicted by ML"),
                fullDescription=SarifMessage(
                    text="The module has high complexity and change churn, indicating high likelihood of containing software defects."
                ),
                defaultConfiguration={"level": "warning"},
            )

        results.append(
            SarifResult(
                ruleId=rule_id,
                level="error" if tier == "CRITICAL" else "warning",
                message=SarifMessage(
                    text=f"TreeSHAP Defect Predictor: {prob:.0%} defect probability (Risk Tier: {tier})."
                ),
                locations=[
                    SarifLocation(
                        physicalLocation=SarifPhysicalLocation(
                            artifactLocation=SarifArtifactLocation(uri=dp.file_path),
                            region=SarifRegion(startLine=1, endLine=1),
                        )
                    )
                ],
            )
        )

    @classmethod
    def _map_review_comment(
        cls,
        rev: ReviewComment,
        rules_map: dict[str, SarifReportingDescriptor],
        results: list[SarifResult],
    ) -> None:
        if rev.status == CommentStatus.DISMISSED or "FALSE_POSITIVE" in (rev.comment or ""):
            return

        rule_id = "AI-HYBRID-CODE-REVIEW"
        if rule_id not in rules_map:
            rules_map[rule_id] = SarifReportingDescriptor(
                id=rule_id,
                name="AI Code Review Finding",
                shortDescription=SarifMessage(text="Triangulated AI Code Review Finding"),
                fullDescription=SarifMessage(
                    text="Identified by hybrid AST, ML risk, and LLM semantic triangulation."
                ),
                defaultConfiguration={"level": "warning"},
            )

        fixes = cls._create_fixes(rev)

        results.append(
            SarifResult(
                ruleId=rule_id,
                level="warning",
                message=SarifMessage(text=rev.comment[:500]),
                locations=[
                    SarifLocation(
                        physicalLocation=SarifPhysicalLocation(
                            artifactLocation=SarifArtifactLocation(uri=rev.file_path),
                            region=SarifRegion(
                                startLine=max(1, rev.line_number),
                                endLine=max(1, rev.line_number),
                            ),
                        )
                    )
                ],
                fixes=fixes,
            )
        )

    @staticmethod
    def _create_fixes(rev: ReviewComment) -> list[SarifFix] | None:
        """Constructs automated SARIF remediation fixes if patch is available."""
        if not rev.suggested_patch:
            return None
        return [
            SarifFix(
                description=SarifMessage(text="Suggested code patch from hybrid review"),
                artifactChanges=[
                    SarifArtifactChange(
                        artifactLocation=SarifArtifactLocation(uri=rev.file_path),
                        replacements=[
                            SarifReplacement(
                                deletedRegion=SarifRegion(
                                    startLine=max(1, rev.line_number),
                                    endLine=max(1, rev.line_number),
                                ),
                                insertedContent=SarifMessage(text=rev.suggested_patch),
                            )
                        ],
                    )
                ],
            )
        ]
