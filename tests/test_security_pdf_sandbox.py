"""Tests for src.core.security.pdf_sandbox — sandboxed PDF text extraction.

extract_pdf_text_safe runs the parser in a spawned child process and must ALWAYS
return a result dict (never raise), reporting failure gracefully on bad input.
Security-critical, previously untested (SAGE self-improvement loop, issue #23).
"""

from src.core.security.pdf_sandbox import extract_pdf_text_safe


def test_garbage_bytes_returns_failure_dict_not_exception():
    result = extract_pdf_text_safe(b"this is definitely not a pdf")
    assert isinstance(result, dict)
    assert result.get("ok") is False
    assert "error" in result


def test_empty_bytes_returns_failure_dict():
    result = extract_pdf_text_safe(b"")
    assert isinstance(result, dict)
    assert result.get("ok") is False


def test_result_always_has_ok_key():
    # Truncated PDF header — parser should fail cleanly inside the sandbox.
    result = extract_pdf_text_safe(b"%PDF-1.4\n%broken")
    assert "ok" in result
    if not result["ok"]:
        assert "error" in result
