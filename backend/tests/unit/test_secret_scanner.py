"""Unit tests for commercial SecretScanner pattern detection and false-positive filtering."""

from app.domain.enums import FindingSeverity
from app.services.secret_scanner import SecretScanner, calculate_shannon_entropy


def test_shannon_entropy_calculation():
    assert calculate_shannon_entropy("aaaaaaaa") == 0.0
    high_ent = calculate_shannon_entropy("aB8$kL9#mZ2!pQ5&")
    assert high_ent > 3.5


def test_secret_scanner_real_pattern_detections():
    # Dynamically build tokens to prevent GitHub push protection false-positives
    aws_token = "AKIA" + "0123456789ABCDEF"
    gh_token = "ghp_" + ("a1b2c3d4e5f6g7h8i9j0" * 2)[:36]
    slack_webhook = "https://" + "hooks." + "slack.com/services/" + "T01234567/" + "B01234567/" + "aBcDeFgHiJkLmNoPqRsTuVwX"
    rsa_block = "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----"

    code = f"""
AWS_KEY = '{aws_token}'
GITHUB_PAT = '{gh_token}'
SLACK_URL = '{slack_webhook}'
RSA_KEY = '''{rsa_block}'''
"""

    findings = SecretScanner.scan_file("src/security_config.py", code)
    assert len(findings) == 4

    types = {f.secret_type for f in findings}
    assert "AWS-ACCESS-KEY" in types
    assert "GITHUB-TOKEN" in types
    assert "SLACK-WEBHOOK" in types
    assert "PRIVATE-KEY" in types

    for f in findings:
        assert f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
        assert not f.masked_value.startswith(aws_token)


def test_secret_scanner_suppression_and_test_paths():
    code = """
mock_secret = "test"
dummy_key = "example_dummy_placeholder"
uuid_str = "123e4567-e89b-12d3-a456-426614174000"
md5_hash = "5d41402abc4b2a76b9719d911017c592"
"""
    prod_findings = SecretScanner.scan_file("src/utils.py", code)
    assert len(prod_findings) == 0

    test_code_with_token = "AWS_KEY = 'AKIA0123456789ABCDEF'"
    test_findings = SecretScanner.scan_file("tests/unit/test_app.py", test_code_with_token)
    assert len(test_findings) == 0

def test_openai_api_key_detection():
    """Confirms OpenAI sk- token signatures are detected."""
    fake_token = "sk-" + ("a1b2c3d4e5f6g7h8i9j0" * 3)[:48]
    code = f"OPENAI_API_KEY = '{fake_token}'"
    findings = SecretScanner.scan_file("src/ai_agent.py", code)
    assert len(findings) == 1
    assert findings[0].secret_type == "OPENAI-API-KEY"
    assert findings[0].line_number == 1
    assert not findings[0].masked_value.startswith(fake_token)


def test_entropy_threshold_behavior():
    """Confirms low-entropy strings are ignored while high-entropy candidates are flagged."""
    low_entropy = "1111222233334444"
    assert calculate_shannon_entropy(low_entropy) < 2.5

    high_entropy_token = "K9#xL2$vM8!qP4*zW1&y"
    assert calculate_shannon_entropy(high_entropy_token) > 3.8


def test_secret_finding_attributes():
    """Verifies SecretFinding entity structure and attributes."""
    findings = SecretScanner.scan_file(
        "config/creds.py",
        "AWS_SECRET = 'AKIA0123456789ABCDEF'",
    )
    assert len(findings) == 1
    finding = findings[0]
    assert finding.secret_type == "AWS-ACCESS-KEY"
    assert finding.file_path == "config/creds.py"
    assert finding.line_number == 1
    assert finding.severity == FindingSeverity.CRITICAL
    assert finding.entropy > 2.5
