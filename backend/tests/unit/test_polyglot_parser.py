"""Unit tests for universal PolyglotParser across Python, TS/JS, Go, Java, and Rust."""

import pytest
from app.infrastructure.parsers.polyglot import PolyglotParser, SupportedLanguage


def test_language_detection_by_extension():
    assert PolyglotParser.detect_language("main.py") == SupportedLanguage.PYTHON
    assert PolyglotParser.detect_language("index.ts") == SupportedLanguage.TYPESCRIPT
    assert PolyglotParser.detect_language("app.jsx") == SupportedLanguage.JAVASCRIPT
    assert PolyglotParser.detect_language("server.go") == SupportedLanguage.GO
    assert PolyglotParser.detect_language("Service.java") == SupportedLanguage.JAVA
    assert PolyglotParser.detect_language("lib.rs") == SupportedLanguage.RUST
    assert PolyglotParser.detect_language("data.csv") is None


def test_python_parsing_and_metrics():
    code = """
def calculate_discount(price, is_vip, coupon):
    if price <= 0:
        return 0
    if is_vip and coupon:
        return price * 0.3
    elif is_vip:
        return price * 0.15
    return 0
"""
    metrics = PolyglotParser.parse_code("discount.py", code)
    assert metrics.language == "python"
    assert metrics.sloc > 0
    # Base 1 + 3 if/elif + 1 'and' operator = 5
    assert metrics.cyclomatic_complexity >= 4
    assert len(metrics.functions) == 1
    assert metrics.functions[0].name == "calculate_discount"
    assert metrics.halstead_metrics["volume"] > 0


def test_typescript_parsing_and_functions():
    code = """
export function authenticate(user: User, token: string): boolean {
    if (!user || !token) {
        return false;
    }
    for (const role of user.roles) {
        if (role === 'admin') {
            return true;
        }
    }
    return false;
}
"""
    metrics = PolyglotParser.parse_code("auth.ts", code)
    assert metrics.language == "typescript"
    # Base 1 + if + || + for + if = 5
    assert metrics.cyclomatic_complexity >= 4
    assert len(metrics.functions) == 1
    assert metrics.functions[0].name == "authenticate"


def test_go_parsing_and_metrics():
    code = """
package main

func HandleRequest(status int) string {
    switch status {
    case 200:
        return "OK"
    case 404:
        return "Not Found"
    default:
        return "Error"
    }
}
"""
    metrics = PolyglotParser.parse_code("handler.go", code)
    assert metrics.language == "go"
    assert metrics.cyclomatic_complexity >= 3
    assert len(metrics.functions) == 1
    assert metrics.functions[0].name == "HandleRequest"


def test_java_parsing_and_metrics():
    code = """
public class Calculator {
    public int divide(int a, int b) {
        if (b == 0) {
            throw new IllegalArgumentException("Division by zero");
        }
        return a / b;
    }
}
"""
    metrics = PolyglotParser.parse_code("Calculator.java", code)
    assert metrics.language == "java"
    assert metrics.cyclomatic_complexity >= 2
    assert len(metrics.functions) == 1
    assert metrics.functions[0].name == "divide"


def test_rust_parsing_and_metrics():
    code = """
fn evaluate(score: i32) -> &'static str {
    match score {
        90..=100 => "A",
        80..=89 => "B",
        _ => "C",
    }
}
"""
    metrics = PolyglotParser.parse_code("eval.rs", code)
    assert metrics.language == "rust"
    assert metrics.cyclomatic_complexity >= 3
    assert len(metrics.functions) == 1
    assert metrics.functions[0].name == "evaluate"


def test_unknown_language_fallback():
    code = "header1,header2\nval1,val2\n"
    metrics = PolyglotParser.parse_code("data.xyz", code)
    assert metrics.language == "unknown"
    assert metrics.cyclomatic_complexity == 1