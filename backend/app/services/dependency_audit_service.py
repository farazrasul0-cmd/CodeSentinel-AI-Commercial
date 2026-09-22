"""Commercial Dependency and Supply Chain Vulnerability Auditing Engine."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.domain.enums import FindingSeverity


@dataclass
class DependencyVulnerability:
    package_name: str
    installed_version: str
    vulnerability_id: str
    severity: FindingSeverity
    title: str
    fixed_version: str
    advisory_url: str
    manifest_file: str


# Offline curated advisory database mapping package -> list of vulnerabilities
OFFLINE_ADVISORY_DB: dict[str, list[dict[str, Any]]] = {
    "requests": [
        {
            "id": "CVE-2023-32681",
            "title": "Unintended leak of Proxy-Authorization header in redirects",
            "severity": FindingSeverity.HIGH,
            "vulnerable_below": "2.31.0",
            "fixed_version": "2.31.0",
            "url": "https://nvd.nist.gov/vuln/detail/CVE-2023-32681",
        }
    ],
    "urllib3": [
        {
            "id": "CVE-2023-45803",
            "title": "HTTP request body not stripped on redirect cross-origin",
            "severity": FindingSeverity.HIGH,
            "vulnerable_below": "2.0.7",
            "fixed_version": "2.0.7",
            "url": "https://nvd.nist.gov/vuln/detail/CVE-2023-45803",
        }
    ],
    "lodash": [
        {
            "id": "CVE-2021-23337",
            "title": "Command Injection in lodash via template",
            "severity": FindingSeverity.CRITICAL,
            "vulnerable_below": "4.17.21",
            "fixed_version": "4.17.21",
            "url": "https://nvd.nist.gov/vuln/detail/CVE-2021-23337",
        }
    ],
    "axios": [
        {
            "id": "CVE-2023-45857",
            "title": "Cross-Site Request Forgery / SSRF bypass in Axios",
            "severity": FindingSeverity.HIGH,
            "vulnerable_below": "1.6.0",
            "fixed_version": "1.6.0",
            "url": "https://nvd.nist.gov/vuln/detail/CVE-2023-45857",
        }
    ],
    "gin-gonic/gin": [
        {
            "id": "CVE-2020-28483",
            "title": "Uncontrolled Resource Consumption in Gin Web Framework",
            "severity": FindingSeverity.HIGH,
            "vulnerable_below": "1.7.0",
            "fixed_version": "1.7.0",
            "url": "https://nvd.nist.gov/vuln/detail/CVE-2020-28483",
        }
    ],
    "log4j-core": [
        {
            "id": "CVE-2021-44228",
            "title": "Remote Code Execution in Apache Log4j (Log4Shell)",
            "severity": FindingSeverity.CRITICAL,
            "vulnerable_below": "2.15.0",
            "fixed_version": "2.17.1",
            "url": "https://nvd.nist.gov/vuln/detail/CVE-2021-44228",
        }
    ],
}


def _parse_semver(ver_str: str) -> tuple[int, ...]:
    """Extracts numeric tuple (major, minor, patch) from version string."""
    clean = re.sub(r"[^0-9.]", "", ver_str).strip(".")
    parts = clean.split(".")
    nums = []
    for p in parts[:3]:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def _is_version_vulnerable(installed_version: str, vulnerable_below: str) -> bool:
    """Compares semver tuples to check if installed version is below the fix."""
    try:
        inst = _parse_semver(installed_version)
        fix = _parse_semver(vulnerable_below)
        return inst < fix
    except Exception:
        return False


class DependencyAuditService:
    """Scans repository package manifests and matches dependencies against advisory databases."""

    @classmethod
    def audit_requirements_txt(cls, manifest_path: str, content: str) -> list[DependencyVulnerability]:
        """Parses requirements.txt for pinned versions."""
        vulnerabilities: list[DependencyVulnerability] = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            match = re.match(r"^([a-zA-Z0-9_\-\.]+)\s*(?:==|<=|<|>=|>)\s*([0-9a-zA-Z\.\-]+)", line)
            if match:
                pkg_name = match.group(1).lower()
                version = match.group(2)
                cls._match_advisories(pkg_name, version, manifest_path, vulnerabilities)

        return vulnerabilities

    @classmethod
    def audit_package_json(cls, manifest_path: str, content: str) -> list[DependencyVulnerability]:
        """Parses package.json dependencies and devDependencies."""
        vulnerabilities: list[DependencyVulnerability] = []
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return vulnerabilities

        all_deps: dict[str, str] = {}
        all_deps.update(data.get("dependencies", {}))
        all_deps.update(data.get("devDependencies", {}))

        for pkg, ver_spec in all_deps.items():
            clean_ver = re.sub(r"[\^~>=<]", "", ver_spec).strip()
            cls._match_advisories(pkg.lower(), clean_ver, manifest_path, vulnerabilities)

        return vulnerabilities

    @classmethod
    def audit_go_mod(cls, manifest_path: str, content: str) -> list[DependencyVulnerability]:
        """Parses go.mod require directives."""
        vulnerabilities: list[DependencyVulnerability] = []
        seen_advisories = set()

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("//"):
                continue

            match = re.search(r"^\s*([a-zA-Z0-9_\-\./]+)\s+v([0-9a-zA-Z\.\-]+)", line)
            if match:
                full_pkg = match.group(1).lower()
                ver = match.group(2)
                short_name = full_pkg.split("/")[-1]
                path_no_host = "/".join(full_pkg.split("/")[1:]) if "/" in full_pkg else full_pkg

                for candidate in (path_no_host, full_pkg, short_name):
                    advisories = OFFLINE_ADVISORY_DB.get(candidate, [])
                    for adv in advisories:
                        adv_key = (adv["id"], candidate)
                        if adv_key not in seen_advisories and _is_version_vulnerable(ver, adv["vulnerable_below"]):
                            seen_advisories.add(adv_key)
                            vulnerabilities.append(
                                DependencyVulnerability(
                                    package_name=candidate,
                                    installed_version=ver,
                                    vulnerability_id=adv["id"],
                                    severity=adv["severity"],
                                    title=adv["title"],
                                    fixed_version=adv["fixed_version"],
                                    advisory_url=adv["url"],
                                    manifest_file=manifest_path,
                                )
                            )

        return vulnerabilities

    @classmethod
    def audit_manifest(cls, file_path: str, content: str) -> list[DependencyVulnerability]:
        """Convenience dispatcher routing file paths to the appropriate manifest parser."""
        filename = Path(file_path).name.lower()
        if filename == "requirements.txt":
            return cls.audit_requirements_txt(file_path, content)
        elif filename == "package.json":
            return cls.audit_package_json(file_path, content)
        elif filename == "go.mod":
            return cls.audit_go_mod(file_path, content)
        return []

    @classmethod
    def _match_advisories(
        cls,
        pkg: str,
        version: str,
        manifest_path: str,
        findings: list[DependencyVulnerability],
    ) -> None:
        """Matches a package and version against the curated advisory database."""
        advisories = OFFLINE_ADVISORY_DB.get(pkg, [])
        for adv in advisories:
            if _is_version_vulnerable(version, adv["vulnerable_below"]):
                findings.append(
                    DependencyVulnerability(
                        package_name=pkg,
                        installed_version=version,
                        vulnerability_id=adv["id"],
                        severity=adv["severity"],
                        title=adv["title"],
                        fixed_version=adv["fixed_version"],
                        advisory_url=adv["url"],
                        manifest_file=manifest_path,
                    )
                )