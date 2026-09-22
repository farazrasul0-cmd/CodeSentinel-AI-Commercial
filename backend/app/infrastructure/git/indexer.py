"""Repository file indexing and tree walking with ignore filters."""

from collections.abc import Generator
from pathlib import Path

IGNORED_DIRS = {
    ".git",
    ".github",
    ".idea",
    ".vscode",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "target",
    "bin",
    "obj",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "temp_repos",
}

IGNORED_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".dll",
    ".so",
    ".dylib",
    ".exe",
    ".bin",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".webp",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".7z",
    ".rar",
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".sqlite",
    ".db",
    ".lock",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}


class FileIndexer:
    @staticmethod
    def is_text_source_file(file_path: Path) -> bool:
        if file_path.suffix.lower() in IGNORED_EXTENSIONS:
            return False
        # Quick check for null bytes to avoid binary files
        try:
            with file_path.open("rb") as f:
                chunk = f.read(1024)
                if b"\x00" in chunk:
                    return False
            return True
        except Exception:
            return False

    @staticmethod
    def _load_ignore_patterns(repo_root: Path) -> list[str]:
        """Parses patterns from .codesentinelignore file if present."""
        patterns: list[str] = []
        ignore_file = repo_root / ".codesentinelignore"
        if ignore_file.exists() and ignore_file.is_file():
            try:
                for line in ignore_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    cleaned = line.strip()
                    if cleaned and not cleaned.startswith("#"):
                        patterns.append(cleaned[:-1] if cleaned.endswith("/") else cleaned)
            except Exception:
                pass
        return patterns

    @classmethod
    def _is_path_ignored(cls, path: Path, repo_root: Path, patterns: list[str]) -> bool:
        """Determines if a path matches standard directory exclusions or custom ignore globs."""
        import fnmatch
        rel_parts = path.relative_to(repo_root).parts
        if any(part in IGNORED_DIRS for part in rel_parts[:-1]):
            return True

        rel_str = "/".join(rel_parts)
        for pat in patterns:
            if (
                fnmatch.fnmatch(rel_str, pat)
                or fnmatch.fnmatch(rel_str, f"{pat}/*")
                or any(fnmatch.fnmatch(part, pat) for part in rel_parts[:-1])
            ):
                return True
        return False

    @classmethod
    def walk_repository(cls, repo_root: Path) -> Generator[Path, None, None]:
        """Walks repository and yields only analyzable source files respecting ignore rules."""
        patterns = cls._load_ignore_patterns(repo_root)
        for path in repo_root.rglob("*"):
            if path.is_file() and not cls._is_path_ignored(path, repo_root, patterns) and cls.is_text_source_file(path):
                yield path

    @classmethod
    def index_all(cls, repo_root: Path) -> list[Path]:
        return list(cls.walk_repository(repo_root))
