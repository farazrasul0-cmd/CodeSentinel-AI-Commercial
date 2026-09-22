"""AST-Based Security Pattern Scanner (CWE Vulnerability Rules)."""

import ast
import re

from app.domain.enums import FindingCategory, FindingSeverity
from app.infrastructure.db.models.issue import Issue

SECRET_KEYWORD_REGEX = re.compile(
    r"(?i)\b(api_key|apikey|secret|password|passwd|auth_token|access_token|private_key)\b"
)
DUMMY_VALUE_REGEX = re.compile(
    r"(?i)^(none|null|dummy|test|example|default|true|false|changeme|\$\{.+\}|\{.*\}|)$"
)


def _extract_call_name(node: ast.Call) -> tuple[str, str]:
    """Returns (module_name, function_name) for a call node."""
    if isinstance(node.func, ast.Attribute):
        mod_name = getattr(node.func.value, "id", "")
        return mod_name, node.func.attr
    if isinstance(node.func, ast.Name):
        return "", node.func.id
    return "", ""


def _is_tainted_sql_arg(arg: ast.AST) -> bool:
    """Checks if an argument contains unparameterized string formatting."""
    if isinstance(arg, ast.JoinedStr):
        return True
    if isinstance(arg, ast.BinOp) and isinstance(arg.op, (ast.Add, ast.Mod)):
        return True
    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute):
        return arg.func.attr == "format"
    return False


def _is_hardcoded_secret_assign(node: ast.Assign) -> tuple[bool, str]:
    """Determines if an assignment node binds a literal secret string."""
    if not (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
        return False, ""

    val = node.value.value.strip()
    if len(val) < 6 or DUMMY_VALUE_REGEX.match(val):
        return False, ""

    for target in node.targets:
        var_name = getattr(target, "id", None) or getattr(target, "attr", "")
        if var_name and SECRET_KEYWORD_REGEX.search(var_name):
            return True, var_name

    return False, ""


def _has_safe_yaml_loader(keywords: list[ast.keyword]) -> bool:
    """Checks whether yaml.load includes a SafeLoader keyword argument."""
    for kw in keywords:
        if kw.arg != "Loader":
            continue
        if isinstance(kw.value, ast.Attribute) and "Safe" in kw.value.attr:
            return True
        if isinstance(kw.value, ast.Name) and "Safe" in kw.value.id:
            return True
    return False


def _has_shell_true_keyword(keywords: list[ast.keyword]) -> bool:
    """Checks whether shell=True is passed in keyword arguments."""
    for kw in keywords:
        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    return False


class SecurityScanner:
    """Scans Python AST for Common Weakness Enumeration (CWE) security vulnerabilities."""

    @classmethod
    def scan_file(cls, file_path: str, code_str: str, tree: ast.AST) -> list[Issue]:
        issues: list[Issue] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                cls._check_sqli(file_path, node, issues)
                cls._check_insecure_deserialization(file_path, node, issues)
                cls._check_command_injection(file_path, node, issues)
                cls._check_weak_crypto(file_path, node, issues)
            elif isinstance(node, ast.Assign):
                cls._check_hardcoded_secrets(file_path, node, issues)

        return issues

    @classmethod
    def _check_sqli(cls, file_path: str, node: ast.Call, issues: list[Issue]) -> None:
        """Detects raw string formatting or f-strings passed into database execute methods."""
        # Exclude migration DDL schema scripts from SQLi check
        normalized_path = file_path.replace("\\", "/")
        if "migrations/" in normalized_path or "alembic" in normalized_path:
            return

        _, func_name = _extract_call_name(node)
        if func_name not in {"execute", "executemany", "raw_sql", "raw"} or not node.args:
            return

        if not _is_tainted_sql_arg(node.args[0]):
            return

        issues.append(
            Issue(
                report_id="",
                rule_id="SEC-CWE-89-SQLI",
                category=FindingCategory.SECURITY,
                severity=FindingSeverity.CRITICAL,
                file_path=file_path,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno),
                title="SQL Injection Risk Detected (CWE-89)",
                description="Direct dynamic string formatting or interpolation detected inside SQL execute call.",
                snippet=f".{func_name}(...)",
                remediation="Use parameterized queries with prepared statements.",
                cwe_id="CWE-89",
            )
        )

    @classmethod
    def _check_hardcoded_secrets(
        cls, file_path: str, node: ast.Assign, issues: list[Issue]
    ) -> None:
        """Detects assignment of literal non-trivial strings to sensitive variable names."""
        # Suppress unit/integration test files, while preserving intentional vulnerability test fixtures
        normalized_path = file_path.replace("\\", "/").lower()
        filename = normalized_path.split("/")[-1]
        is_test_runner = (
            (normalized_path.startswith("tests/") or "/tests/" in normalized_path)
            and (filename.startswith("test_") or filename.endswith("_test.py"))
            and "/fixtures/" not in normalized_path
            and not filename.startswith("sec_")
        )
        if is_test_runner:
            return
        is_secret, var_name = _is_hardcoded_secret_assign(node)
        if not is_secret:
            return

        issues.append(
            Issue(
                report_id="",
                rule_id="SEC-CWE-798-SECRET",
                category=FindingCategory.SECURITY,
                severity=FindingSeverity.CRITICAL,
                file_path=file_path,
                line_start=node.lineno,
                line_end=node.lineno,
                title="Hardcoded Credential or Token Detected (CWE-798)",
                description=f"Variable '{var_name}' appears to be assigned a hardcoded plaintext secret.",
                snippet=f"{var_name} = '***'",
                remediation="Store secrets in external environment variables or a secrets manager.",
                cwe_id="CWE-798",
            )
        )

    @classmethod
    def _check_insecure_deserialization(
        cls, file_path: str, node: ast.Call, issues: list[Issue]
    ) -> None:
        """Detects unsafe deserialization via pickle or pyyaml without SafeLoader."""
        mod_name, method_name = _extract_call_name(node)

        if mod_name == "pickle" and method_name in {"load", "loads"}:
            issues.append(
                Issue(
                    report_id="",
                    rule_id="SEC-CWE-502-PICKLE",
                    category=FindingCategory.SECURITY,
                    severity=FindingSeverity.HIGH,
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=node.lineno,
                    title="Insecure Deserialization via pickle (CWE-502)",
                    description="Unpickling untrusted data can lead to arbitrary remote code execution (RCE).",
                    snippet=f"pickle.{method_name}(...)",
                    remediation="Use secure serialization formats like JSON or Protocol Buffers.",
                    cwe_id="CWE-502",
                )
            )
        elif mod_name == "yaml" and method_name == "load" and not _has_safe_yaml_loader(node.keywords):
            issues.append(
                Issue(
                    report_id="",
                    rule_id="SEC-CWE-502-YAML",
                    category=FindingCategory.SECURITY,
                    severity=FindingSeverity.HIGH,
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=node.lineno,
                    title="Insecure YAML Deserialization (CWE-502)",
                    description="Using yaml.load() without SafeLoader allows arbitrary object instantiation.",
                    snippet="yaml.load(...)",
                    remediation="Replace with yaml.safe_load(...).",
                    cwe_id="CWE-502",
                )
            )

    @classmethod
    def _check_command_injection(
        cls, file_path: str, node: ast.Call, issues: list[Issue]
    ) -> None:
        """Detects subprocess execution with shell=True or os.system."""
        mod_name, attr_name = _extract_call_name(node)

        if mod_name == "os" and attr_name in {"system", "popen"}:
            issues.append(
                Issue(
                    report_id="",
                    rule_id="SEC-CWE-78-OS-SYSTEM",
                    category=FindingCategory.SECURITY,
                    severity=FindingSeverity.HIGH,
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=node.lineno,
                    title="OS Command Execution Detected (CWE-78)",
                    description=f"Direct invocation of `os.{attr_name}()` exposes system to command injection.",
                    snippet=f"os.{attr_name}(...)",
                    remediation="Use subprocess.run with argument vectors (shell=False).",
                    cwe_id="CWE-78",
                )
            )
        elif (
            mod_name == "subprocess"
            and attr_name in {"run", "Popen", "call", "check_output", "check_call"}
            and _has_shell_true_keyword(node.keywords)
        ):
            issues.append(
                Issue(
                    report_id="",
                    rule_id="SEC-CWE-78-SHELL-TRUE",
                    category=FindingCategory.SECURITY,
                    severity=FindingSeverity.HIGH,
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=node.lineno,
                    title="Subprocess with shell=True Detected (CWE-78)",
                    description="Running subprocess with `shell=True` allows shell metacharacter injection.",
                    snippet=f"subprocess.{attr_name}(..., shell=True)",
                    remediation="Set shell=False and pass arguments as an explicit array.",
                    cwe_id="CWE-78",
                )
            )

    @classmethod
    def _check_weak_crypto(cls, file_path: str, node: ast.Call, issues: list[Issue]) -> None:
        """Detects broken cryptographic algorithms (MD5, SHA1, DES)."""
        mod_name, attr_name = _extract_call_name(node)

        if mod_name == "hashlib" and attr_name.lower() in {"md5", "sha1"}:
            issues.append(
                Issue(
                    report_id="",
                    rule_id="SEC-CWE-327-WEAK-HASH",
                    category=FindingCategory.SECURITY,
                    severity=FindingSeverity.MEDIUM,
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=node.lineno,
                    title=f"Weak / Broken Hash Algorithm Detected ({attr_name.upper()}) (CWE-327)",
                    description=f"`hashlib.{attr_name}()` is vulnerable to collision attacks.",
                    snippet=f"hashlib.{attr_name}(...)",
                    remediation="Upgrade to collision-resistant hash functions like SHA-256 or SHA-512.",
                    cwe_id="CWE-327",
                )
            )
        elif (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Attribute)
            and getattr(node.func.value.value, "id", "") == "Crypto"
            and node.func.value.attr == "Cipher"
            and node.func.attr.lower() in {"des", "arc4", "blowfish"}
        ):
            issues.append(
                Issue(
                    report_id="",
                    rule_id="SEC-CWE-327-WEAK-CIPHER",
                    category=FindingCategory.SECURITY,
                    severity=FindingSeverity.HIGH,
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=node.lineno,
                    title=f"Obsolete Symmetric Cipher Detected ({node.func.attr}) (CWE-327)",
                    description=f"`Crypto.Cipher.{node.func.attr}` provides inadequate encryption strength.",
                    snippet=f"Cipher.{node.func.attr}(...)",
                    remediation="Use AES-GCM or ChaCha20-Poly1305 with modern authenticated encryption.",
                    cwe_id="CWE-327",
                )
            )
