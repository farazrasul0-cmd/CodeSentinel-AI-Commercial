"""Unit tests for DependencyAuditService supply chain vulnerability scanning."""

from app.domain.enums import FindingSeverity
from app.services.dependency_audit_service import DependencyAuditService


def test_requirements_txt_vulnerability_detection():
    reqs_content = """
# Pinned dependencies
requests==2.26.0
urllib3==1.25.10
fastapi==0.110.0
"""
    findings = DependencyAuditService.audit_manifest("requirements.txt", reqs_content)
    assert len(findings) == 2

    pkgs = {f.package_name for f in findings}
    assert "requests" in pkgs
    assert "urllib3" in pkgs

    for f in findings:
        assert f.severity == FindingSeverity.HIGH
        assert f.vulnerability_id.startswith("CVE-")
        assert f.fixed_version != ""


def test_package_json_vulnerability_detection():
    package_json = """
{
  "name": "enterprise-web",
  "dependencies": {
    "lodash": "^4.17.19",
    "axios": "0.21.1",
    "react": "^18.2.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0"
  }
}
"""
    findings = DependencyAuditService.audit_manifest("package.json", package_json)
    assert len(findings) == 2

    pkgs = {f.package_name for f in findings}
    assert "lodash" in pkgs
    assert "axios" in pkgs

    lodash_vuln = next(f for f in findings if f.package_name == "lodash")
    assert lodash_vuln.severity == FindingSeverity.CRITICAL


def test_go_mod_vulnerability_detection():
    go_mod = """
module myapp

go 1.22

require (
    github.com/gin-gonic/gin v1.6.3
    github.com/google/uuid v1.6.0
)
"""
    findings = DependencyAuditService.audit_manifest("go.mod", go_mod)
    assert len(findings) >= 1
    assert any("gin" in f.package_name for f in findings)


def test_safe_dependencies_zero_findings():
    safe_reqs = """
requests==2.32.0
urllib3==2.1.0
fastapi==0.110.0
"""
    findings = DependencyAuditService.audit_manifest("requirements.txt", safe_reqs)
    assert len(findings) == 0