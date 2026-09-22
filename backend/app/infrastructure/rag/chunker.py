"""Grammar-Aware Semantic AST Chunker for Python and TypeScript/JavaScript.

Decomposes source code files into semantically cohesive chunks aligned with
syntactic AST boundaries (classes, functions, methods, interfaces) while
preserving enclosing scopes, parameter signatures, and structural metadata.
"""

import ast
import hashlib
import re
from dataclasses import dataclass, field


@dataclass
class CodeChunk:
    """Represents a syntactically cohesive code unit."""

    chunk_id: str
    file_path: str
    language: str
    symbol_name: str
    symbol_type: str  # FUNCTION, METHOD, CLASS, INTERFACE, MODULE_TOP_LEVEL
    scope_path: list[str]
    start_line: int
    end_line: int
    content: str
    docstring: str | None = None
    parameters: list[str] = field(default_factory=list)
    return_type: str | None = None
    imported_symbols: list[str] = field(default_factory=list)


def generate_chunk_id(file_path: str, symbol_name: str, start_line: int, end_line: int) -> str:
    """Generates a deterministic SHA256 identifier for a code chunk."""
    raw = f"{file_path}:{symbol_name}:{start_line}:{end_line}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _extract_python_imports(tree: ast.AST) -> list[str]:
    """Extracts top-level and imported symbol names from a Python AST."""
    imported_symbols: list[str] = []
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_symbols.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imported_symbols.append(f"{mod}.{alias.name}" if mod else alias.name)
    return imported_symbols


def _extract_function_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[list[str], str | None]:
    """Extracts typed parameter signatures and return type from a function node."""
    params: list[str] = []
    for arg in node.args.args:
        arg_name = arg.arg
        if arg.annotation:
            arg_name += f": {ast.unparse(arg.annotation)}"
        params.append(arg_name)

    ret_type = ast.unparse(node.returns) if node.returns else None
    return params, ret_type


def _extract_typescript_imports(lines: list[str]) -> list[str]:
    """Extracts imported identifiers from TypeScript / JavaScript source lines."""
    imported_symbols: list[str] = []
    import_pattern = re.compile(
        r"import\s+(?:\{([^}]+)\}|([a-zA-Z0-9_$]+))\s+from\s+['\"]([^'\"]+)['\"]"
    )
    for line in lines:
        match = import_pattern.search(line)
        if not match:
            continue
        destructured = match.group(1)
        default_import = match.group(2)
        if destructured:
            for sym in destructured.split(","):
                cleaned = sym.strip().split(" as ")[0].strip()
                if cleaned:
                    imported_symbols.append(cleaned)
        elif default_import:
            imported_symbols.append(default_import.strip())
    return imported_symbols


def _is_statement_end(char: str, found_open: bool, kind: str) -> bool:
    """Checks for semicolon termination in variable declarations."""
    if found_open:
        return False
    return char == ";" and kind in ("const", "let", "var")


def _find_ts_block_end(
    content: str,
    search_start: int,
    kind: str,
    next_match_start: int | None = None,
) -> int:
    """Finds the ending character index of a TypeScript block by balancing braces."""
    brace_count = 0
    found_open = False
    content_len = len(content)

    for idx in range(search_start, content_len):
        char = content[idx]
        if char == "{":
            brace_count += 1
            found_open = True
        elif char == "}":
            brace_count -= 1
            if found_open and brace_count == 0:
                return idx + 1
        elif _is_statement_end(char, found_open, kind):
            return idx + 1

    if not found_open and next_match_start is not None:
        return next_match_start

    return content_len


@dataclass
class AstExtractionContext:
    """Carries contextual metadata and output chunk list during AST traversal."""

    file_path: str
    lines: list[str]
    imported_symbols: list[str]
    chunks: list[CodeChunk]


@dataclass
class TsChunkContext:
    """Carries contextual source data during TypeScript chunk extraction."""

    file_path: str
    content: str
    lines: list[str]
    imported_symbols: list[str]



class PythonSemanticChunker:
    """AST-driven semantic chunker for Python source files."""

    @classmethod
    def chunk(cls, file_path: str, content: str) -> list[CodeChunk]:
        """Parses Python source code and extracts AST enclosing scope chunks."""
        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError:
            return [cls._create_module_chunk(file_path, content, max(1, total_lines))]

        imported_symbols = _extract_python_imports(tree)
        chunks: list[CodeChunk] = []

        ctx = AstExtractionContext(
            file_path=file_path,
            lines=lines,
            imported_symbols=imported_symbols,
            chunks=chunks,
        )

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                cls._extract_class(node, ctx)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cls._extract_function(node, ctx, parent_scope=[])

        if not chunks and content.strip():
            chunks.append(cls._create_module_chunk(file_path, content, total_lines, imported_symbols))

        return chunks

    @classmethod
    def _create_module_chunk(
        cls,
        file_path: str,
        content: str,
        total_lines: int,
        imported_symbols: list[str] | None = None,
    ) -> CodeChunk:
        return CodeChunk(
            chunk_id=generate_chunk_id(file_path, "module", 1, max(1, total_lines)),
            file_path=file_path,
            language="python",
            symbol_name="module",
            symbol_type="MODULE_TOP_LEVEL",
            scope_path=["module"],
            start_line=1,
            end_line=max(1, total_lines),
            content=content,
            imported_symbols=imported_symbols or [],
        )

    @classmethod
    def _extract_class(
        cls,
        node: ast.ClassDef,
        ctx: AstExtractionContext,
    ) -> None:
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)
        content = "".join(ctx.lines[start_line - 1 : end_line])

        ctx.chunks.append(
            CodeChunk(
                chunk_id=generate_chunk_id(ctx.file_path, node.name, start_line, end_line),
                file_path=ctx.file_path,
                language="python",
                symbol_name=node.name,
                symbol_type="CLASS",
                scope_path=[node.name],
                start_line=start_line,
                end_line=end_line,
                content=content,
                docstring=ast.get_docstring(node),
                imported_symbols=ctx.imported_symbols,
            )
        )

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cls._extract_function(
                    item,
                    ctx,
                    parent_scope=[node.name],
                )

    @classmethod
    def _extract_function(
        cls,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        ctx: AstExtractionContext,
        parent_scope: list[str] | None = None,
    ) -> None:
        scope = parent_scope or []
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line)
        content = "".join(ctx.lines[start_line - 1 : end_line])
        params, ret_type = _extract_function_signature(node)

        symbol_name = f"{scope[0]}.{node.name}" if scope else node.name
        symbol_type = "METHOD" if scope else "FUNCTION"

        ctx.chunks.append(
            CodeChunk(
                chunk_id=generate_chunk_id(ctx.file_path, symbol_name, start_line, end_line),
                file_path=ctx.file_path,
                language="python",
                symbol_name=symbol_name,
                symbol_type=symbol_type,
                scope_path=scope + [node.name],
                start_line=start_line,
                end_line=end_line,
                content=content,
                docstring=ast.get_docstring(node),
                parameters=params,
                return_type=ret_type,
                imported_symbols=ctx.imported_symbols,
            )
        )


class TypeScriptSemanticChunker:
    """Syntax-aware semantic chunker for TypeScript and JavaScript files."""

    DECLARATION_PATTERN = re.compile(
        r"^(?:export\s+)?(?:async\s+)?(?:default\s+)?(class|interface|function|const|let|var)\s+([a-zA-Z0-9_$]+)",
        re.MULTILINE,
    )

    @classmethod
    def _create_match_chunk(
        cls,
        ctx: TsChunkContext,
        match: re.Match,
        next_start: int | None,
    ) -> CodeChunk:
        """Constructs an individual TypeScript AST chunk from a regex match."""
        kind, name = match.group(1), match.group(2)
        start_line = ctx.content[: match.start()].count("\n") + 1
        end_char = _find_ts_block_end(ctx.content, match.end(), kind, next_start)
        end_line = ctx.content[:end_char].count("\n") + 1
        chunk_content = "".join(ctx.lines[start_line - 1 : end_line])
        symbol_type = "CLASS" if kind == "class" else ("INTERFACE" if kind == "interface" else "FUNCTION")

        return CodeChunk(
            chunk_id=generate_chunk_id(ctx.file_path, name, start_line, end_line),
            file_path=ctx.file_path,
            language="typescript",
            symbol_name=name,
            symbol_type=symbol_type,
            scope_path=[name],
            start_line=start_line,
            end_line=end_line,
            content=chunk_content,
            imported_symbols=ctx.imported_symbols,
        )

    @classmethod
    def chunk(cls, file_path: str, content: str) -> list[CodeChunk]:
        """Extracts top-level classes, interfaces, and functions using balanced block traversal."""
        lines = content.splitlines(keepends=True)
        total_lines = len(lines)
        if total_lines == 0:
            return []

        imported_symbols = _extract_typescript_imports(lines)
        matches = list(cls.DECLARATION_PATTERN.finditer(content))
        chunks: list[CodeChunk] = []

        ts_ctx = TsChunkContext(
            file_path=file_path,
            content=content,
            lines=lines,
            imported_symbols=imported_symbols,
        )
        for idx, match in enumerate(matches):
            next_start = matches[idx + 1].start() if idx + 1 < len(matches) else None
            chunks.append(
                cls._create_match_chunk(ts_ctx, match, next_start)
            )

        if not chunks and content.strip():
            chunks.append(
                CodeChunk(
                    chunk_id=generate_chunk_id(file_path, "module", 1, total_lines),
                    file_path=file_path,
                    language="typescript",
                    symbol_name="module",
                    symbol_type="MODULE_TOP_LEVEL",
                    scope_path=["module"],
                    start_line=1,
                    end_line=total_lines,
                    content=content,
                    imported_symbols=imported_symbols,
                )
            )

        return chunks


class UnifiedSemanticChunker:
    """Universal router for syntax-aware code chunking across languages."""

    @classmethod
    def chunk_file(cls, file_path: str, content: str, language: str | None = None) -> list[CodeChunk]:
        """Routes file to language-specific semantic chunker."""
        lower_path = file_path.lower()

        if language == "python" or lower_path.endswith((".py", ".pyw")):
            return PythonSemanticChunker.chunk(file_path, content)

        if language in ("typescript", "javascript") or lower_path.endswith(
            (".ts", ".tsx", ".js", ".jsx", ".mjs")
        ):
            return TypeScriptSemanticChunker.chunk(file_path, content)

        lines = content.splitlines(keepends=True)
        total_lines = max(1, len(lines))
        return [
            CodeChunk(
                chunk_id=generate_chunk_id(file_path, "generic_module", 1, total_lines),
                file_path=file_path,
                language=language or "generic",
                symbol_name="generic_module",
                symbol_type="MODULE_TOP_LEVEL",
                scope_path=["module"],
                start_line=1,
                end_line=total_lines,
                content=content,
            )
        ]
