"""Code Smells AST Analyzer."""

import ast

from app.domain.enums import FindingCategory, FindingSeverity
from app.infrastructure.db.models.issue import Issue
from app.infrastructure.static_analysis.complexity import ComplexityReport


class CodeSmellScanner:
    """Detects software maintainability smells using AST traversal."""

    @classmethod
    def scan_file(
        cls,
        file_path: str,
        code_str: str,
        tree: ast.AST,
        complexity_report: ComplexityReport,
    ) -> list[Issue]:
        issues: list[Issue] = []

        # 1. High Complexity Smells (McCabe & Cognitive)
        for fn in complexity_report.functions:
            cls._check_function_complexity(file_path, fn, issues)

        for cls_comp in complexity_report.classes:
            # 2. Large Class Smell
            if cls_comp.sloc > 300 or len(cls_comp.methods) > 10:
                issues.append(
                    Issue(
                        report_id="",
                        rule_id="SMELL-LARGE-CLASS",
                        category=FindingCategory.CODE_SMELL,
                        severity=FindingSeverity.MEDIUM,
                        file_path=file_path,
                        line_start=cls_comp.line_start,
                        line_end=cls_comp.line_end,
                        title=f"Large Class '{cls_comp.name}' Detected",
                        description=f"Class '{cls_comp.name}' has {cls_comp.sloc} lines and {len(cls_comp.methods)} methods (threshold: 300 lines / 10 methods).",
                        snippet=f"class {cls_comp.name}: ...",
                        remediation="Apply Single Responsibility Principle (SRP) to decompose into cohesive smaller classes.",
                        cwe_id="CWE-1060",
                    )
                )

            for m in cls_comp.methods:
                cls._check_function_complexity(file_path, m, issues)

        # 3. Deep Nesting and Dead Code Scanners
        cls._scan_nesting_and_dead_code(file_path, tree, issues)

        return issues

    @classmethod
    def _check_function_complexity(cls, file_path: str, fn, issues: list[Issue]) -> None:
        # Long Method (> 50 lines)
        if fn.sloc > 50:
            issues.append(
                Issue(
                    report_id="",
                    rule_id="SMELL-LONG-METHOD",
                    category=FindingCategory.CODE_SMELL,
                    severity=FindingSeverity.MEDIUM,
                    file_path=file_path,
                    line_start=fn.line_start,
                    line_end=fn.line_end,
                    title=f"Long Method '{fn.name}' ({fn.sloc} lines)",
                    description=f"Function '{fn.name}' spans {fn.sloc} lines of code (recommended maximum: 50 lines).",
                    snippet=f"def {fn.name}(...)",
                    remediation="Extract independent blocks into focused private helper methods.",
                    cwe_id="CWE-1074",
                )
            )

        # Too Many Parameters (> 5 arguments)
        if fn.param_count > 5:
            issues.append(
                Issue(
                    report_id="",
                    rule_id="SMELL-TOO-MANY-PARAMS",
                    category=FindingCategory.CODE_SMELL,
                    severity=FindingSeverity.LOW,
                    file_path=file_path,
                    line_start=fn.line_start,
                    line_end=fn.line_start,
                    title=f"Too Many Parameters in '{fn.name}' ({fn.param_count} params)",
                    description=f"Function '{fn.name}' accepts {fn.param_count} parameters (threshold: 5).",
                    snippet=f"def {fn.name}(...)",
                    remediation="Group related parameters into a parameter object, dataclass, or Pydantic schema.",
                    cwe_id="CWE-1060",
                )
            )

        # High Cyclomatic Complexity
        if fn.cyclomatic_complexity > 10:
            severity = (
                FindingSeverity.HIGH if fn.cyclomatic_complexity > 15 else FindingSeverity.MEDIUM
            )
            issues.append(
                Issue(
                    report_id="",
                    rule_id="SMELL-HIGH-CYCLOMATIC-COMPLEXITY",
                    category=FindingCategory.MAINTAINABILITY,
                    severity=severity,
                    file_path=file_path,
                    line_start=fn.line_start,
                    line_end=fn.line_end,
                    title=f"High Cyclomatic Complexity in '{fn.name}' (CC = {fn.cyclomatic_complexity})",
                    description=f"Function '{fn.name}' has {fn.cyclomatic_complexity} decision branches (threshold: 10). High branch density increases defect risk.",
                    snippet=f"def {fn.name}(...)",
                    remediation="Reduce nesting and branching logic; consider polymorphism or lookup tables.",
                    cwe_id="CWE-1075",
                )
            )

        # Cognitive Complexity
        if fn.cognitive_complexity > 15:
            issues.append(
                Issue(
                    report_id="",
                    rule_id="SMELL-HIGH-COGNITIVE-COMPLEXITY",
                    category=FindingCategory.MAINTAINABILITY,
                    severity=FindingSeverity.MEDIUM,
                    file_path=file_path,
                    line_start=fn.line_start,
                    line_end=fn.line_end,
                    title=f"High Cognitive Complexity in '{fn.name}' (Score = {fn.cognitive_complexity})",
                    description=f"Function '{fn.name}' has a cognitive complexity of {fn.cognitive_complexity} (threshold: 15). Code is difficult for human reviewers to reason about.",
                    snippet=f"def {fn.name}(...)",
                    remediation="Flatten nested control flow and break into smaller, self-documenting sub-routines.",
                    cwe_id="CWE-1075",
                )
            )

    @classmethod
    def _scan_nesting_and_dead_code(
        cls, file_path: str, tree: ast.AST, issues: list[Issue]
    ) -> None:
        """Finds deeply nested control structures (> 3 levels) and dead code after returns."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cls._check_block_nesting(file_path, node, 0, issues)
                cls._check_dead_code(file_path, node.body, issues)

    @classmethod
    def _check_block_nesting(
        cls, file_path: str, node: ast.AST, current_depth: int, issues: list[Issue]
    ) -> None:
        if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
            if current_depth >= 4:
                line_no = getattr(node, "lineno", 1)
                issues.append(
                    Issue(
                        report_id="",
                        rule_id="SMELL-DEEP-NESTING",
                        category=FindingCategory.CODE_SMELL,
                        severity=FindingSeverity.MEDIUM,
                        file_path=file_path,
                        line_start=line_no,
                        line_end=line_no,
                        title=f"Deeply Nested Control Flow (Depth = {current_depth})",
                        description=f"Control block exceeds 3 levels of nesting (depth: {current_depth}). Deep nesting impedes readability and testability.",
                        snippet=None,
                        remediation="Invert conditionals and use early guard return statements.",
                        cwe_id="CWE-1075",
                    )
                )
            new_depth = current_depth + 1
        else:
            new_depth = current_depth

        if isinstance(node, ast.If):
            for child in node.body:
                cls._check_block_nesting(file_path, child, new_depth, issues)
            # Handle elif ladder: an elif branch is a flat sequential branch, keep current_depth
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                cls._check_block_nesting(file_path, node.orelse[0], current_depth, issues)
            else:
                for child in node.orelse:
                    cls._check_block_nesting(file_path, child, new_depth, issues)
        else:
            for child in ast.iter_child_nodes(node):
                cls._check_block_nesting(file_path, child, new_depth, issues)

    @classmethod
    def _check_dead_code(
        cls, file_path: str, statements: list[ast.stmt], issues: list[Issue]
    ) -> None:
        has_terminator = False
        for stmt in statements:
            if has_terminator:
                issues.append(
                    Issue(
                        report_id="",
                        rule_id="SMELL-UNREACHABLE-CODE",
                        category=FindingCategory.CODE_SMELL,
                        severity=FindingSeverity.LOW,
                        file_path=file_path,
                        line_start=stmt.lineno,
                        line_end=getattr(stmt, "end_lineno", stmt.lineno),
                        title="Unreachable Code Detected",
                        description="Statement follows a terminal statement (return, raise, break, continue) and will never be executed.",
                        snippet=None,
                        remediation="Remove or relocate dead statements.",
                        cwe_id="CWE-561",
                    )
                )
                break

            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                has_terminator = True

            # Recursively inspect child blocks
            if hasattr(stmt, "body") and isinstance(stmt.body, list):
                cls._check_dead_code(file_path, stmt.body, issues)
            if hasattr(stmt, "orelse") and isinstance(stmt.orelse, list):
                cls._check_dead_code(file_path, stmt.orelse, issues)
