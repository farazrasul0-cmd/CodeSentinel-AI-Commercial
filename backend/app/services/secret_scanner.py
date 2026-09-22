"""Commercial Secret Scanner with Dual-Layer Regex Signatures and Shannon Entropy Filtering."""

import math
import re
from dataclasses import dataclass
from pathlib import Path

from app.domain.enums import FindingSeverity


@dataclass
class SecretFinding:
    file_path: str
    line_number: int
    secret_type: str
    severity: FindingSeverity
    masked_value: str
    entropy: float
    description: str


# High-confidence pattern signatures
SECRET_PATTERNS: list[tuple[str, str, FindingSeverity, re.Pattern]] = [
    (
        "AWS-ACCESS-KEY",
        "AWS Access Key ID",
        FindingSeverity.CRITICAL,
        re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
    ),
    (
        "GITHUB-TOKEN",
        "GitHub Personal Access Token",
        FindingSeverity.CRITICAL,
        re.compile(r"\b(ghp_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36})\b"),
    ),
    (
        "OPENAI-API-KEY",
        "OpenAI API Secret Key",
        FindingSeverity.CRITICAL,
        re.compile(r"\b(sk-[a-zA-Z0-9]{32,64})\b"),
    ),
    (
        "SLACK-WEBHOOK",
        "Slack Incoming Webhook URL",
        FindingSeverity.HIGH,
        re.compile(r"(https://hooks\.slack\.com/services/T[0-9a-zA-Z_]+/B[0-9a-zA-Z_]+/[0-9a-zA-Z_]+)"),
    ),
    (
        "PRIVATE-KEY",
        "Unencrypted Private Key Block",
        FindingSeverity.CRITICAL,
        re.compile(r"-----BEGIN (?:RSA|OPENSSH|DSA|EC|PGP)? ?PRIVATE KEY-----"),
    ),
    (
        "GENERIC-API-TOKEN",
        "High-Entropy Generic API Key Assignment",
        FindingSeverity.HIGH,
        re.compile(r"""(?i)\b(?:api_key|secret_key|auth_token|client_secret)\s*[:=]\s*["']([A-Za-z0-9_\-\.]{24,})["']"""),
    ),
]

IGNORE_PATH_PATTERNS = [
    r"(?i)(^|[\\/])(tests?|fixtures?|__tests__|mocks?|specs?)[\\/]",
    r"(?i)\.(test|spec)\.[a-z0-9]+$",
]

DUMMY_VALUE_REGEX = re.compile(
    r"(?i)^(none|null|dummy|test|example|default|true|false|changeme|\$\{.+\}|\{.*\}|placeholder|sample|abcdef.*|123456.*)$"
)

UUID_REGEX = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
HEX_HASH_REGEX = re.compile(r"^[0-9a-fA-F]{32,64}$")


def calculate_shannon_entropy(data: str) -> float:
    """Calculates Shannon entropy: H(X) = -sum(P(x) * log2(P(x)))."""
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    char_counts: dict[str, int] = {}
    for c in data:
        char_counts[c] = char_counts.get(c, 0) + 1

    for count in char_counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return round(entropy, 2)


def mask_secret(value: str) -> str:
    """Masks secret to prevent exposing credentials in reports."""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


class SecretScanner:
    """Enterprise secret detection engine combining signatures, Shannon entropy, and heuristic filtering."""

    @classmethod
    def scan_file(cls, file_path: str, content: str) -> list[SecretFinding]:
        norm_path = file_path.replace("\\", "/")

        # 1. Skip test paths to minimize noise
        for pattern in IGNORE_PATH_PATTERNS:
            if re.search(pattern, norm_path):
                return []

        findings: list[SecretFinding] = []
        lines = content.splitlines()

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "//", "*")):
                continue

            # Layer 1: Pattern Signatures
            for rule_id, rule_name, severity, regex in SECRET_PATTERNS:
                for match in regex.finditer(line):
                    matched_val = match.group(1) if match.groups() else match.group(0)

                    # Filter dummy or test placeholders
                    if DUMMY_VALUE_REGEX.match(matched_val) or UUID_REGEX.match(matched_val):
                        continue

                    # Filter lower-entropy hashes for generic token rules
                    entropy = calculate_shannon_entropy(matched_val)
                    if rule_id == "GENERIC-API-TOKEN" and (entropy < 3.8 or HEX_HASH_REGEX.match(matched_val)):
                        continue

                    findings.append(
                        SecretFinding(
                            file_path=file_path,
                            line_number=line_idx,
                            secret_type=rule_id,
                            severity=severity,
                            masked_value=mask_secret(matched_val),
                            entropy=entropy,
                            description=f"{rule_name} exposed in source code (entropy: {entropy}).",
                        )
                    )

        return findings