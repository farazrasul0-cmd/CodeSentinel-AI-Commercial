"""Python AST Analyzer for extracting classes, functions, and McCabe Cyclomatic Complexity."""

import ast
from dataclasses import dataclass, field


@dataclass
class FunctionInfo:
    name: str
    line_start: int
    line_end: int
    cyclomatic_complexity: int
    arg_count: int
    has_docstring: bool


@dataclass
class ClassInfo:
    name: str
    line_start: int
    line_end: int
    methods: list[FunctionInfo] = field(default_factory=list)


@dataclass
class ModuleMetrics:
    sloc: int
    function_count: int
    class_count: int
    total_cyclomatic_complexity: int
    max_cyclomatic_complexity: int
    average_cyclomatic_complexity: float
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)


class ComplexityVisitor(ast.NodeVisitor):
    """Calculates McCabe Cyclomatic Complexity for AST subtrees."""

    def __init__(self) -> None:
        self.complexity = 1  # Base complexity

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # Each boolean operator adds a decision branch
        self.complexity += len(node.values) - 1
        self.generic_visit(node)


def analyze_python_source(code_str: str) -> ModuleMetrics:
    """Parses Python source code and computes detailed structural and complexity metrics."""
    code_str = code_str.lstrip("\ufeff")
    non_empty_lines = [
        line for line in code_str.splitlines() if line.strip() and not line.strip().startswith("#")
    ]
    sloc = len(non_empty_lines)

    try:
        tree = ast.parse(code_str)
    except SyntaxError:
        return ModuleMetrics(
            sloc=sloc,
            function_count=0,
            class_count=0,
            total_cyclomatic_complexity=1,
            max_cyclomatic_complexity=1,
            average_cyclomatic_complexity=1.0,
        )

    functions: list[FunctionInfo] = []
    classes: list[ClassInfo] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            visitor = ComplexityVisitor()
            visitor.visit(node)
            fn_info = FunctionInfo(
                name=node.name,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno),
                cyclomatic_complexity=visitor.complexity,
                arg_count=len(node.args.args),
                has_docstring=ast.get_docstring(node) is not None,
            )
            functions.append(fn_info)

        elif isinstance(node, ast.ClassDef):
            class_methods: list[FunctionInfo] = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    visitor = ComplexityVisitor()
                    visitor.visit(item)
                    m_info = FunctionInfo(
                        name=item.name,
                        line_start=item.lineno,
                        line_end=getattr(item, "end_lineno", item.lineno),
                        cyclomatic_complexity=visitor.complexity,
                        arg_count=len(item.args.args),
                        has_docstring=ast.get_docstring(item) is not None,
                    )
                    class_methods.append(m_info)

            cls_info = ClassInfo(
                name=node.name,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno),
                methods=class_methods,
            )
            classes.append(cls_info)

    all_complexities = [f.cyclomatic_complexity for f in functions]
    for c in classes:
        all_complexities.extend([m.cyclomatic_complexity for m in c.methods])

    total_cc = sum(all_complexities) if all_complexities else 1
    max_cc = max(all_complexities) if all_complexities else 1
    avg_cc = (total_cc / len(all_complexities)) if all_complexities else 1.0

    total_functions = len(functions) + sum(len(c.methods) for c in classes)

    return ModuleMetrics(
        sloc=sloc,
        function_count=total_functions,
        class_count=len(classes),
        total_cyclomatic_complexity=total_cc,
        max_cyclomatic_complexity=max_cc,
        average_cyclomatic_complexity=round(avg_cc, 2),
        functions=functions,
        classes=classes,
    )
