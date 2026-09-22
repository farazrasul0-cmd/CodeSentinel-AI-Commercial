"""Composite Multi-Dimensional Software Quality Scoring Algorithm.

Calculates normalized 0-100 scores across four architectural pillars:
Security, Maintainability, Architecture, and Testing.
Produces actionable recommendations, technical debt estimation, and percentile rankings.
"""

from dataclasses import dataclass
from typing import Any
from pydantic import BaseModel, Field

from app.api.v1.schemas.review import CodeReviewFinding, FindingCategoryEnum
from app.domain.enums import CommentStatus, FindingCategory, FindingSeverity
from app.infrastructure.db.models.file_metric import FileMetric
from app.infrastructure.db.models.issue import Issue
from app.infrastructure.db.models.review_comment import ReviewComment

EXEMPT_TOKENS = ("/schemas/", "/dto/", "/types/", "enum", "migration", "test", "benchmark")


class QualityScorecard(BaseModel):
    """Synthesized multi-dimensional quality scorecard output."""

    overall_score: float = Field(..., description="Composite Quality Index [0-100]")
    maintainability_score: float = Field(..., description="Maintainability Pillar Score [0-100]")
    security_score: float = Field(..., description="Security Pillar Score [0-100]")
    testing_score: float = Field(..., description="Testing Coverage Pillar Score [0-100]")
    architecture_score: float = Field(..., description="Architecture and Reliability Score [0-100]")
    technical_debt_minutes: int = Field(..., description="Remediation technical debt in minutes")
    grade: str = Field(..., description="Standard letter grade")
    radar_data: list[dict[str, Any]] = Field(default_factory=list)
    pillars: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    false_positives_suppressed: int = Field(0)


@dataclass
class ScorecardMetrics:
    """Aggregated metrics container for radar and pillar generation."""

    security: float
    maintainability: float
    architecture: float
    testing: float
    avg_mi: float
    total_files: int
    validated_sec_issues: list[Issue]
    fp_count: int
    num_cycles: int
    high_coupling_count: int
    test_files: list[FileMetric]


def _parse_review_item(rev: Any) -> tuple[Any, str, int, str]:
    """Normalizes review item attributes across dict, ReviewComment, or CodeReviewFinding."""
    if isinstance(rev, dict):
        return rev.get("category"), rev.get("file_path", ""), rev.get("line_start", 0), rev.get("rule_id", "")
    if isinstance(rev, ReviewComment):
        cat = FindingCategoryEnum.FALSE_POSITIVE_OVERRIDE if ("FALSE_POSITIVE" in (rev.comment or "") or rev.status == CommentStatus.DISMISSED) else None
        return cat, rev.file_path, rev.line_number, ""
    return getattr(rev, "category", None), getattr(rev, "file_path", ""), getattr(rev, "line_start", 0), getattr(rev, "rule_id", "")


def _is_exempt_from_coupling(path: str) -> bool:
    """Exempts data transfer objects, schemas, enums, migrations, and test suites from coupling caps."""
    p = path.replace("\\", "/").lower()
    return p.endswith("__init__.py") or any(t in p for t in EXEMPT_TOKENS)


def _calc_defect_risk(defect_predictions: list[Any] | None, total_files: int) -> float:
    """Calculates defect risk penalty based on ML predictions."""
    if not defect_predictions or total_files <= 0:
        return 0.0
    probs = [
        float(getattr(dp, "defect_probability", 0.0) if hasattr(dp, "defect_probability") else dp.get("defect_probability", 0.0))
        for dp in defect_predictions
    ]
    crit_count = sum(1 for p in probs if p >= 0.70)
    avg_prob = sum(probs) / len(probs) if probs else 0.0
    return min(35.0, (30.0 * avg_prob) + (20.0 * (crit_count / total_files)))


def _calc_arch_smells_penalty(issues: list[Issue]) -> float:
    """Calculates architecture-level smell penalty (excluding maintainability smells)."""
    arch_issues = [i for i in issues if i.category == FindingCategory.ARCHITECTURE]
    p_smells = sum(8.0 if i.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH) else 3.0 for i in arch_issues)
    return min(30.0, p_smells)


def _collect_operational_candidates(
    val_sec: list[Issue],
    defect_preds: list[Any] | None,
    cycles: list[list[str]] | None,
) -> list[dict[str, Any]]:
    """Synthesizes security, defect risk, and architectural cycle recommendations."""
    cands: list[dict[str, Any]] = []
    crit = [i for i in val_sec if i.severity == FindingSeverity.CRITICAL]
    high = [i for i in val_sec if i.severity == FindingSeverity.HIGH]
    if crit or high:
        t = crit[0] if crit else high[0]
        cnt = len(crit) + len(high)
        cands.append({
            "pillar": "Security",
            "title": f"Remediate {cnt} Critical/High Security Vulnerabilities",
            "description": f"Patch security exposure such as {t.title} in {t.file_path}:{t.line_start}.",
            "effort_minutes": 120 * cnt,
            "potential_score_impact": round(min(25.0, cnt * 15.0), 1),
            "priority_weight": 100,
        })
    if defect_preds:
        crit_f = [dp for dp in defect_preds if float(getattr(dp, "defect_probability", 0.0) if hasattr(dp, "defect_probability") else dp.get("defect_probability", 0.0)) >= 0.70]
        if crit_f:
            top = crit_f[0]
            fp = getattr(top, "file_path", "") if hasattr(top, "file_path") else top.get("file_path", "module")
            prob = float(getattr(top, "defect_probability", 0.0) if hasattr(top, "defect_probability") else top.get("defect_probability", 0.0))
            cands.append({
                "pillar": "Architecture",
                "title": f"Refactor Defect-Prone Module ({fp})",
                "description": f"Targeted refactoring for module with {int(prob * 100)}% defect probability identified by TreeSHAP.",
                "effort_minutes": 90,
                "potential_score_impact": 12.0,
                "priority_weight": 85,
            })
    if cycles:
        cands.append({
            "pillar": "Architecture",
            "title": f"Break {len(cycles)} Circular Import Cycle(s)",
            "description": f"Decouple cyclic dependency loop: {' -> '.join(cycles[0][:3])}.",
            "effort_minutes": 150,
            "potential_score_impact": 15.0,
            "priority_weight": 80,
        })
    return cands


def _collect_code_candidates(
    file_metrics: list[FileMetric],
    test_score: float,
) -> list[dict[str, Any]]:
    """Synthesizes maintainability and test coverage recommendations."""
    cands: list[dict[str, Any]] = []
    complex_f = [m for m in file_metrics if (m.cyclomatic_complexity or 0) > 15]
    if complex_f:
        tf = max(complex_f, key=lambda m: (m.cyclomatic_complexity or 0))
        cands.append({
            "pillar": "Maintainability",
            "title": f"Decompose Complex Functions (CC={tf.cyclomatic_complexity})",
            "description": f"Extract sub-routines in {tf.file_path} to reduce cyclomatic and cognitive complexity.",
            "effort_minutes": 60,
            "potential_score_impact": 8.5,
            "priority_weight": 70,
        })
    if test_score < 60.0:
        cands.append({
            "pillar": "Testing",
            "title": "Expand Unit & Integration Test Coverage",
            "description": "Increase test-to-code ratio to exceed 30% of total lines of code.",
            "effort_minutes": 180,
            "potential_score_impact": 14.0,
            "priority_weight": 65,
        })
    return cands


def _calc_percentile(score: float, baseline: float) -> float:
    """Calculates approximate percentile ranking against baseline distribution."""
    return max(5.0, min(99.0, round(50.0 + ((score - baseline) * 1.5), 1)))


def _build_radar(m: ScorecardMetrics) -> list[dict[str, Any]]:
    """Constructs radar axes data points."""
    rel_score = round(min(100.0, (m.security + m.architecture) / 2.0), 1)
    return [
        {"axis": "Security", "value": round(m.security, 1), "benchmark_value": 85.0},
        {"axis": "Maintainability", "value": round(m.maintainability, 1), "benchmark_value": 78.0},
        {"axis": "Architecture", "value": round(m.architecture, 1), "benchmark_value": 75.0},
        {"axis": "Testing", "value": round(m.testing, 1), "benchmark_value": 70.0},
        {"axis": "Reliability", "value": rel_score, "benchmark_value": 80.0},
    ]


def _build_pillars(m: ScorecardMetrics) -> list[dict[str, Any]]:
    """Constructs pillar score descriptors."""
    sec_desc = f"{len(m.validated_sec_issues)} active security findings; {m.fp_count} suppressed false alarms."
    maint_desc = f"Average MI {m.avg_mi:.1f} across {m.total_files} files." if m.total_files else "No files analyzed."
    arch_desc = f"{m.num_cycles} circular cycles; {m.high_coupling_count} high-coupling modules."
    test_desc = f"{len(m.test_files)} test files detected in repository."

    return [
        {
            "name": "Security",
            "score": round(m.security, 1),
            "weight": 0.35,
            "weighted_contribution": round(0.35 * m.security, 1),
            "grade": ScoringService._assign_grade(m.security),
            "benchmark_percentile": _calc_percentile(m.security, 85.0),
            "summary": sec_desc,
        },
        {
            "name": "Maintainability",
            "score": round(m.maintainability, 1),
            "weight": 0.30,
            "weighted_contribution": round(0.30 * m.maintainability, 1),
            "grade": ScoringService._assign_grade(m.maintainability),
            "benchmark_percentile": _calc_percentile(m.maintainability, 78.0),
            "summary": maint_desc,
        },
        {
            "name": "Architecture",
            "score": round(m.architecture, 1),
            "weight": 0.20,
            "weighted_contribution": round(0.20 * m.architecture, 1),
            "grade": ScoringService._assign_grade(m.architecture),
            "benchmark_percentile": _calc_percentile(m.architecture, 75.0),
            "summary": arch_desc,
        },
        {
            "name": "Testing",
            "score": round(m.testing, 1),
            "weight": 0.15,
            "weighted_contribution": round(0.15 * m.testing, 1),
            "grade": ScoringService._assign_grade(m.testing),
            "benchmark_percentile": _calc_percentile(m.testing, 70.0),
            "summary": test_desc,
        },
    ]


class ScoringService:
    """Multi-dimensional code quality scoring engine with false-positive filtering."""

    @staticmethod
    def calculate_scores(
        file_metrics: list[FileMetric],
        issues: list[Issue],
        reviews: list[CodeReviewFinding] | list[ReviewComment] | list[dict[str, Any]] | None = None,
        circular_dependencies: list[list[str]] | None = None,
        defect_predictions: list[Any] | None = None,
    ) -> QualityScorecard:
        """Calculates 4 pillar scores (0-100), composite RQI (0-100), grade, and recommendations."""
        total_files = len(file_metrics)
        suppressed_rules, suppressed_locations, fp_count = ScoringService._extract_suppressions(reviews)
        maint, avg_mi = ScoringService._calculate_maintainability(file_metrics, total_files)
        security, val_sec = ScoringService._calculate_security(issues, suppressed_rules, suppressed_locations)
        arch, cycles, high_coupling = ScoringService._calculate_architecture(
            file_metrics, issues, circular_dependencies, defect_predictions, total_files
        )
        testing, test_files = ScoringService._calculate_testing(file_metrics, total_files)
        debt = ScoringService._calculate_technical_debt(issues, suppressed_rules, suppressed_locations)

        overall = (0.35 * security) + (0.30 * maint) + (0.20 * arch) + (0.15 * testing)
        grade = ScoringService._assign_grade(overall)

        metrics = ScorecardMetrics(
            security=security, maintainability=maint, architecture=arch, testing=testing,
            avg_mi=avg_mi, total_files=total_files, validated_sec_issues=val_sec,
            fp_count=fp_count, num_cycles=cycles, high_coupling_count=high_coupling, test_files=test_files,
        )
        radar_data, pillars = _build_radar(metrics), _build_pillars(metrics)
        recs = ScoringService._generate_recommendations(val_sec, file_metrics, circular_dependencies, defect_predictions, testing)

        return QualityScorecard(
            overall_score=round(overall, 1),
            maintainability_score=round(maint, 1),
            security_score=round(security, 1),
            testing_score=round(testing, 1),
            architecture_score=round(arch, 1),
            technical_debt_minutes=debt,
            grade=grade,
            radar_data=radar_data,
            pillars=pillars,
            recommendations=recs,
            false_positives_suppressed=fp_count,
        )

    @staticmethod
    def _extract_suppressions(
        reviews: list[CodeReviewFinding] | list[ReviewComment] | list[dict[str, Any]] | None,
    ) -> tuple[set[str], set[tuple[str, int]], int]:
        """Extracts suppressed rule IDs and locations from code review overrides."""
        suppressed_rules: set[str] = set()
        suppressed_locations: set[tuple[str, int]] = set()
        fp_count = 0
        if not reviews:
            return suppressed_rules, suppressed_locations, 0

        for rev in reviews:
            cat, fp_file, fp_line, rule_id = _parse_review_item(rev)
            if cat in (FindingCategoryEnum.FALSE_POSITIVE_OVERRIDE, "FALSE_POSITIVE_OVERRIDE"):
                fp_count += 1
                if rule_id:
                    suppressed_rules.add(rule_id)
                if fp_file and fp_line:
                    suppressed_locations.add((fp_file, fp_line))

        return suppressed_rules, suppressed_locations, fp_count

    @staticmethod
    def _calculate_maintainability(file_metrics: list[FileMetric], total_files: int) -> tuple[float, float]:
        """Calculates Maintainability pillar score and average maintainability index."""
        if total_files <= 0:
            return 85.0, 85.0

        avg_mi = sum((m.maintainability_index or 100.0) for m in file_metrics) / total_files
        excess_cog = sum(max(0, (m.cognitive_complexity or 0) - 12) for m in file_metrics)
        p_cog = min(5.0, 0.5 * (excess_cog / total_files))

        maintainability = max(0.0, min(100.0, avg_mi - p_cog))
        return maintainability, avg_mi

    @staticmethod
    def _calculate_security(
        issues: list[Issue],
        suppressed_rules: set[str],
        suppressed_locations: set[tuple[str, int]],
    ) -> tuple[float, list[Issue]]:
        """Calculates Security score subtracting penalties for validated vulnerabilities."""
        security = 100.0
        validated: list[Issue] = []

        for issue in issues:
            if issue.category != FindingCategory.SECURITY:
                continue
            if (issue.rule_id and issue.rule_id in suppressed_rules) or ((issue.file_path, issue.line_start) in suppressed_locations):
                continue
            validated.append(issue)
            penalties = {
                FindingSeverity.CRITICAL: 25.0,
                FindingSeverity.HIGH: 15.0,
                FindingSeverity.MEDIUM: 8.0,
                FindingSeverity.LOW: 3.0,
            }
            security -= penalties.get(issue.severity, 0.0)

        return max(0.0, security), validated

    @staticmethod
    def _calculate_architecture(
        file_metrics: list[FileMetric],
        issues: list[Issue],
        circular_dependencies: list[list[str]] | None,
        defect_predictions: list[Any] | None,
        total_files: int,
    ) -> tuple[float, int, int]:
        """Calculates Architecture score based on coupling, cycles, and defects."""
        num_cycles = len(circular_dependencies) if circular_dependencies else 0
        p_circular = 15.0 * num_cycles

        high_coupling_count = sum(
            1 for m in file_metrics
            if not _is_exempt_from_coupling(m.file_path) and ((m.function_count or 0) > 20 or (m.class_count or 0) > 6)
        )
        p_coupling = min(25.0, 3.0 * high_coupling_count)
        p_defect_risk = _calc_defect_risk(defect_predictions, total_files)
        p_smells = _calc_arch_smells_penalty(issues)

        architecture = max(0.0, 100.0 - p_circular - p_coupling - p_defect_risk - p_smells)
        return architecture, num_cycles, high_coupling_count

    @staticmethod
    def _calculate_testing(
        file_metrics: list[FileMetric], total_files: int
    ) -> tuple[float, list[FileMetric]]:
        """Calculates Testing pillar score based on test-to-code ratio."""
        test_files = [
            m for m in file_metrics if ("test" in m.file_path.lower() or "spec" in m.file_path.lower())
        ]
        if total_files <= 0:
            return 75.0, []

        total_loc = sum((m.sloc or 0) for m in file_metrics)
        test_loc = sum((m.sloc or 0) for m in test_files)
        prod_loc = max(1, total_loc - test_loc)

        if total_loc > 0 and len(test_files) > 0:
            loc_ratio = test_loc / prod_loc
            file_ratio = len(test_files) / total_files
            testing = min(100.0, max(30.0, (200.0 * loc_ratio) + (50.0 * file_ratio)))
        elif len(test_files) > 0:
            testing = min(100.0, max(35.0, (len(test_files) / total_files) * 300.0))
        else:
            testing = 30.0

        return testing, test_files

    @staticmethod
    def _calculate_technical_debt(
        issues: list[Issue],
        suppressed_rules: set[str],
        suppressed_locations: set[tuple[str, int]],
    ) -> int:
        """Estimates total technical debt remediation time in minutes based on unsuppressed findings."""
        debt = 0
        severity_minutes = {
            FindingSeverity.CRITICAL: 180,
            FindingSeverity.HIGH: 90,
            FindingSeverity.MEDIUM: 45,
            FindingSeverity.LOW: 15,
        }
        for issue in issues:
            if (issue.rule_id and issue.rule_id in suppressed_rules) or ((issue.file_path, issue.line_start) in suppressed_locations):
                continue
            debt += severity_minutes.get(issue.severity, 15)

        return debt

    @staticmethod
    def _assign_grade(score: float) -> str:
        """Translates numeric score [0-100] to standard letter grade."""
        if score >= 90.0:
            return "A"
        if score >= 80.0:
            return "B"
        if score >= 70.0:
            return "C"
        if score >= 60.0:
            return "D"
        return "F"

    @staticmethod
    def _calculate_percentile(score: float, baseline: float) -> float:
        """Calculates approximate percentile ranking against baseline distribution."""
        return _calc_percentile(score, baseline)

    @staticmethod
    def _generate_recommendations(
        validated_sec_issues: list[Issue],
        file_metrics: list[FileMetric],
        circular_dependencies: list[list[str]] | None,
        defect_predictions: list[Any] | None,
        testing_score: float,
    ) -> list[dict[str, Any]]:
        """Synthesizes top 3 high-leverage refactoring actions."""
        candidates = _collect_operational_candidates(validated_sec_issues, defect_predictions, circular_dependencies)
        candidates.extend(_collect_code_candidates(file_metrics, testing_score))
        candidates.sort(key=lambda x: x["priority_weight"], reverse=True)
        return [
            {
                "rank": idx,
                "pillar": rec["pillar"],
                "title": rec["title"],
                "description": rec["description"],
                "effort_minutes": rec["effort_minutes"],
                "potential_score_impact": rec["potential_score_impact"],
            }
            for idx, rec in enumerate(candidates[:3], start=1)
        ]
