"""Universal Polyglot AST Parser utilizing precompiled Tree-sitter wheels."""

import math
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from tree_sitter import Language, Node, Parser

_LANG_CACHE: dict[str, Language] = {}


def _get_language(lang_name: str) -> Language:
    if lang_name in _LANG_CACHE:
        return _LANG_CACHE[lang_name]

    if lang_name == "python":
        import tree_sitter_python
        lang = Language(tree_sitter_python.language())
    elif lang_name == "javascript":
        import tree_sitter_javascript
        lang = Language(tree_sitter_javascript.language())
    elif lang_name == "typescript":
        import tree_sitter_typescript
        lang = Language(tree_sitter_typescript.language_typescript())
    elif lang_name == "go":
        import tree_sitter_go
        lang = Language(tree_sitter_go.language())
    elif lang_name == "java":
        import tree_sitter_java
        lang = Language(tree_sitter_java.language())
    elif lang_name == "rust":
        import tree_sitter_rust
        lang = Language(tree_sitter_rust.language())
    else:
        raise ValueError(f"Unsupported language: {lang_name}")

    _LANG_CACHE[lang_name] = lang
    return lang


class SupportedLanguage(StrEnum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    JAVA = "java"
    RUST = "rust"


EXTENSION_MAP: dict[str, SupportedLanguage] = {
    ".py": SupportedLanguage.PYTHON,
    ".js": SupportedLanguage.JAVASCRIPT,
    ".jsx": SupportedLanguage.JAVASCRIPT,
    ".mjs": SupportedLanguage.JAVASCRIPT,
    ".cjs": SupportedLanguage.JAVASCRIPT,
    ".ts": SupportedLanguage.TYPESCRIPT,
    ".tsx": SupportedLanguage.TYPESCRIPT,
    ".go": SupportedLanguage.GO,
    ".java": SupportedLanguage.JAVA,
    ".rs": SupportedLanguage.RUST,
}

DECISION_NODE_TYPES = {
    "if_statement",
    "elif_clause",
    "conditional_expression",
    "ternary_expression",
    "if_expression",
    "for_statement",
    "for_in_statement",
    "while_statement",
    "do_statement",
    "loop_expression",
    "case_clause",
    "switch_case",
    "expression_case",
    "type_case",
    "communication_case",
    "match_arm",
    "catch_clause",
    "except_clause",
}

FUNCTION_NODE_TYPES = {
    "function_definition",
    "function_declaration",
    "arrow_function",
    "method_definition",
    "method_declaration",
    "constructor_declaration",
    "function_item",
}


@dataclass
class FunctionBoundary:
    name: str
    start_line: int
    end_line: int
    cyclomatic_complexity: int


@dataclass
class PolyglotFileMetrics:
    language: str
    sloc: int
    total_lines: int
    cyclomatic_complexity: int
    max_function_complexity: int
    functions: list[FunctionBoundary] = field(default_factory=list)
    halstead_metrics: dict[str, float] = field(default_factory=dict)


class PolyglotParser:
    """Parses source code across Python, JS, TS, Go, Java, and Rust to compute normalized metrics."""

    @classmethod
    def detect_language(cls, file_path: str | Path) -> SupportedLanguage | None:
        ext = Path(file_path).suffix.lower()
        return EXTENSION_MAP.get(ext)

    @classmethod
    def parse_code(cls, file_path: str, code_str: str) -> PolyglotFileMetrics:
        lang = cls.detect_language(file_path)
        if not lang:
            lines = code_str.splitlines()
            return PolyglotFileMetrics(
                language="unknown",
                sloc=len([l for l in lines if l.strip()]),
                total_lines=len(lines),
                cyclomatic_complexity=1,
                max_function_complexity=1,
            )

        parser = Parser(_get_language(lang.value))
        source_bytes = code_str.encode("utf-8")
        tree = parser.parse(source_bytes)

        total_cc = 1
        functions: list[FunctionBoundary] = []
        operators: list[str] = []
        operands: list[str] = []

        def traverse(node: Node, curr_fn: FunctionBoundary | None = None) -> None:
            nonlocal total_cc
            node_type = node.type

            is_decision = node_type in DECISION_NODE_TYPES
            if node_type in ("binary_expression", "boolean_operator"):
                op_node = node.child_by_field_name("operator")
                if op_node:
                    op_text = op_node.text.decode("utf-8", errors="ignore")
                    if op_text in ("&&", "||", "and", "or"):
                        is_decision = True

            if is_decision:
                total_cc += 1
                if curr_fn:
                    curr_fn.cyclomatic_complexity += 1

            if node_type in FUNCTION_NODE_TYPES:
                fn_name = cls._extract_function_name(node, source_bytes)
                fn_boundary = FunctionBoundary(
                    name=fn_name,
                    start_line=node.start_point.row + 1,
                    end_line=node.end_point.row + 1,
                    cyclomatic_complexity=1,
                )
                functions.append(fn_boundary)
                curr_fn = fn_boundary

            if not node.children:
                text = node.text.decode("utf-8", errors="ignore").strip()
                if text:
                    if text in ("+", "-", "*", "/", "%", "=", "==", "!=", "<", ">", "<=", ">=", "&&", "||", "!", "?", ":"):
                        operators.append(text)
                    elif node_type in ("identifier", "string", "number", "integer", "float", "true", "false"):
                        operands.append(text)

            for child in node.children:
                traverse(child, curr_fn)

        traverse(tree.root_node)

        lines = code_str.splitlines()
        non_empty = [l for l in lines if l.strip() and not l.strip().startswith(("#", "//", "/*", "*"))]
        sloc = len(non_empty)

        n1 = len(set(operators))
        n2 = len(set(operands))
        N1 = len(operators)
        N2 = len(operands)
        vocab = n1 + n2
        length = N1 + N2
        volume = length * math.log2(vocab) if vocab > 0 else 0.0
        difficulty = (n1 / 2) * (N2 / n2) if n2 > 0 and n1 > 0 else 0.0
        effort = difficulty * volume

        halstead = {
            "vocabulary": float(vocab),
            "length": float(length),
            "volume": round(volume, 2),
            "difficulty": round(difficulty, 2),
            "effort": round(effort, 2),
        }

        max_fn_cc = max((f.cyclomatic_complexity for f in functions), default=1)

        return PolyglotFileMetrics(
            language=lang.value,
            sloc=sloc,
            total_lines=len(lines),
            cyclomatic_complexity=total_cc,
            max_function_complexity=max_fn_cc,
            functions=functions,
            halstead_metrics=halstead,
        )

    @staticmethod
    def _extract_function_name(node: Node, source: bytes) -> str:
        name_node = node.child_by_field_name("name")
        if name_node:
            return name_node.text.decode("utf-8", errors="ignore")
        for c in node.children:
            if c.type in ("identifier", "property_identifier"):
                return c.text.decode("utf-8", errors="ignore")
        return "anonymous"