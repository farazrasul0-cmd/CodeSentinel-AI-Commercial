"""Pluggable Static Analysis Engine Coordinator."""

import ast
from dataclasses import dataclass

from app.infrastructure.ast_parser.metrics_calc import (
    calculate_maintainability_index,
    estimate_halstead_metrics,
)
from app.infrastructure.db.models.file_metric import FileMetric
from app.infrastructure.db.models.issue import Issue
from app.infrastructure.static_analysis.complexity import (
    ComplexityReport,
    analyze_complexity,
)
from app.infrastructure.static_analysis.security import SecurityScanner
from app.infrastructure.static_analysis.smells import CodeSmellScanner


@dataclass
class FileAnalysisResult:
    file_path: str
    metric: FileMetric
    issues: list[Issue]
    complexity_report: ComplexityReport


class StaticAnalysisEngine:
    """Orchestrates AST parsing, complexity calculation, code smell detection, and security analysis."""

    @classmethod
    def analyze_python_file(cls, file_path: str, code_str: str) -> FileAnalysisResult:
        # Strip UTF-8 BOM if present
        code_str = code_str.lstrip("\ufeff")
        # 1. Parse AST
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            # Handle invalid syntax gracefully without crashing
            empty_report = ComplexityReport(
                module_cyclomatic_complexity=1,
                max_cyclomatic_complexity=1,
                module_cognitive_complexity=0,
            )
            metric = FileMetric(
                report_id="",
                file_path=file_path,
                language="Python",
                sloc=len(code_str.splitlines()),
                cyclomatic_complexity=1,
                cognitive_complexity=0,
                function_count=0,
                class_count=0,
                maintainability_index=50.0,
                halstead_metrics={},
            )
            syntax_issue = Issue(
                report_id="",
                rule_id="PARSE-SYNTAX-ERROR",
                category="CODE_SMELL",  # type: ignore
                severity="HIGH",  # type: ignore
                file_path=file_path,
                line_start=e.lineno or 1,
                line_end=e.lineno or 1,
                title=f"Python Syntax Error: {e.msg}",
                description=f"Source file could not be parsed: {e.msg}",
                remediation="Correct the Python syntax error.",
            )
            return FileAnalysisResult(
                file_path=file_path,
                metric=metric,
                issues=[syntax_issue],
                complexity_report=empty_report,
            )

        # 2. Complexity & Halstead Metrics
        complexity_report = analyze_complexity(tree)
        halstead = estimate_halstead_metrics(code_str)

        non_empty_lines = [
            line
            for line in code_str.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        sloc = len(non_empty_lines)

        mi = calculate_maintainability_index(
            sloc=sloc,
            cyclomatic_complexity=complexity_report.max_cyclomatic_complexity,
            halstead_volume=halstead["volume"],
        )

        total_functions = len(complexity_report.functions) + sum(
            len(c.methods) for c in complexity_report.classes
        )

        metric = FileMetric(
            report_id="",
            file_path=file_path,
            language="Python",
            sloc=sloc,
            cyclomatic_complexity=complexity_report.max_cyclomatic_complexity,
            cognitive_complexity=complexity_report.module_cognitive_complexity,
            function_count=total_functions,
            class_count=len(complexity_report.classes),
            maintainability_index=mi,
            halstead_metrics=halstead,
        )

        # 3. Code Smell Detection
        smell_issues = CodeSmellScanner.scan_file(
            file_path=file_path,
            code_str=code_str,
            tree=tree,
            complexity_report=complexity_report,
        )

        # 4. Security Vulnerability Detection (CWEs)
        security_issues = SecurityScanner.scan_file(
            file_path=file_path,
            code_str=code_str,
            tree=tree,
        )

        all_issues = smell_issues + security_issues

        return FileAnalysisResult(
            file_path=file_path,
            metric=metric,
            issues=all_issues,
            complexity_report=complexity_report,
        )
