"""Tests for src.core.role_generator._make_role_id.

Previously untested (SAGE self-improvement loop, issue #23).
"""

from src.core.role_generator import _make_role_id


def test_slugifies_title():
    assert _make_role_id("VP of Marketing") == "vp_of_marketing"


def test_strips_punctuation():
    assert _make_role_id("Q&A / Support!") == "qa_support"


def test_collapses_whitespace():
    assert _make_role_id("  Lead   Engineer  ") == "lead_engineer"


def test_empty_falls_back_to_custom_role():
    assert _make_role_id("") == "custom_role"
    assert _make_role_id("!!!") == "custom_role"
