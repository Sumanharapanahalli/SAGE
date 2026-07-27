"""Tests for onboarding_analyzer + onboarding_session (non-LLM surfaces).

Previously untested (SAGE self-improvement loop, issue #23).
"""

from src.core.onboarding_analyzer import OnboardingAnalyzer, ProjectSignals
from src.core.onboarding_session import create_session, get_session


def test_analyze_text_returns_project_signals():
    signals = OnboardingAnalyzer().analyze_text(
        "We build embedded firmware for a Class II medical device in C."
    )
    assert isinstance(signals, ProjectSignals)
    assert isinstance(signals.to_dict(), dict)


def test_session_create_and_retrieve_roundtrip():
    session = create_session()
    assert session.session_id
    assert get_session(session.session_id) is session


def test_get_unknown_session_returns_none():
    assert get_session("does-not-exist") is None
