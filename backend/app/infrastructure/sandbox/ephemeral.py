"""Ephemeral Worker Sandbox for Untrusted Code Isolation."""

import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from types import TracebackType
from typing import Self

from app.core.config import settings
from app.core.logging import logger


class SandboxSecurityError(Exception):
    """Raised when an operation violates sandbox boundaries (e.g. symlink traversal)."""
    pass


class SandboxLimitExceededError(Exception):
    """Raised when repository disk usage exceeds configured quota."""
    pass


class EphemeralSandbox:
    """Provides an isolated temporary directory for cloning, parsing, and metric calculation.
    
    Guarantees automatic cleanup on completion or unexpected exceptions,
    neutralizes malicious .git/hooks, and rejects symlink traversal attacks.
    """

    def __init__(
        self,
        base_dir: str | Path | None = None,
        prefix: str = "cs_sandbox_",
        max_size_mb: int | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.base_dir = Path(base_dir or settings.TEMP_STORAGE_PATH)
        self.prefix = prefix
        self.max_size_mb = max_size_mb or settings.MAX_REPO_SIZE_MB
        self.timeout_seconds = timeout_seconds or settings.GIT_CLONE_TIMEOUT_SECONDS
        self._path: Path | None = None

    @property
    def path(self) -> Path:
        if not self._path:
            raise RuntimeError("Sandbox has not been initialized. Use inside a context manager.")
        return self._path

    def __enter__(self) -> Self:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._path = Path(tempfile.mkdtemp(prefix=self.prefix, dir=self.base_dir))
        logger.debug(f"[Sandbox] Initialized ephemeral workspace at {self._path}")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.cleanup()

    async def __aenter__(self) -> Self:
        return self.__enter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.cleanup()

    def validate_safe_path(self, rel_or_abs_path: str | Path) -> Path:
        """Validates that a path stays strictly within the sandbox boundary.
        
        Guards against directory traversal (e.g. `../../etc/passwd`) and malicious symlinks.
        """
        root_resolved = self.path.resolve()
        candidate = (self.path / rel_or_abs_path).resolve()

        try:
            candidate.relative_to(root_resolved)
        except ValueError:
            raise SandboxSecurityError(
                f"Path traversal detected: '{rel_or_abs_path}' escapes sandbox root '{root_resolved}'"
            )

        # Check if any path segment is a symlink pointing outside
        curr = candidate
        while curr != root_resolved and curr != curr.parent:
            if curr.is_symlink():
                target_resolved = curr.readlink().resolve()
                try:
                    target_resolved.relative_to(root_resolved)
                except ValueError:
                    raise SandboxSecurityError(
                        f"Symlink escape detected: '{curr}' targets '{target_resolved}' outside sandbox."
                    )
            curr = curr.parent

        return candidate

    def neutralize_git_hooks(self) -> int:
        """Removes or disables any executable hooks in .git/hooks to prevent malicious RCE."""
        hooks_dir = self.path / ".git" / "hooks"
        if not hooks_dir.exists() or not hooks_dir.is_dir():
            return 0

        neutralized = 0
        for item in hooks_dir.iterdir():
            try:
                if item.is_file() or item.is_symlink():
                    item.unlink(missing_ok=True)
                    neutralized += 1
            except Exception as e:
                logger.warning(f"[Sandbox] Failed to neutralize hook {item}: {e}")

        logger.info(f"[Sandbox] Neutralized {neutralized} git hooks in {hooks_dir}")
        return neutralized

    def check_disk_usage(self) -> int:
        """Calculates total disk usage in bytes; raises exception if over limit."""
        total_bytes = 0
        for root, _, files in os.walk(self.path):
            for file in files:
                fp = Path(root) / file
                try:
                    if not fp.is_symlink():
                        total_bytes += fp.stat().st_size
                except OSError:
                    pass

        max_bytes = self.max_size_mb * 1024 * 1024
        if total_bytes > max_bytes:
            raise SandboxLimitExceededError(
                f"Sandbox disk usage ({total_bytes // (1024*1024)}MB) exceeds limit of {self.max_size_mb}MB"
            )
        return total_bytes

    def run_command(
        self,
        cmd: list[str],
        timeout: int | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """Executes a command strictly within the sandbox root directory."""
        effective_timeout = timeout or self.timeout_seconds
        return subprocess.run(
            cmd,
            cwd=str(self.path),
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            check=check,
        )

    def cleanup(self) -> None:
        """Removes the sandbox directory completely, safely handling read-only git metadata."""
        if not self._path or not self._path.exists():
            return

        def _remove_readonly(func, path, _):
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        try:
            shutil.rmtree(self._path, onerror=_remove_readonly)
            logger.debug(f"[Sandbox] Cleaned up ephemeral workspace at {self._path}")
        except Exception as e:
            logger.error(f"[Sandbox] Failed to cleanup {self._path}: {e}")
        finally:
            self._path = None