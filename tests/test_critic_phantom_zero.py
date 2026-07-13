"""A critic that could not ANSWER must not be recorded as a critic scoring zero.

Observed live in an Agent Gym session:

    critic_reviews = {'gemini': 0, 'primary': 35, 'ollama': 61}

Gemini had not judged the work worthless — it had failed to return parseable JSON (it was
timing out at the old 30s gemini_timeout). That phantom 0 was then aggregated as a genuine
verdict, dragging the median down and able to fail work that no critic actually rejected.

This is the same class of bug as the evaluator-optimizer's flat-0.0 runs: a silent panel
must look SILENT, not HARSH.
"""
from __future__ import annotations

import pytest

from src.agents.critic import CriticAgent

pytestmark = pytest.mark.unit


def _reviews(**by_provider):
    """Build a reviews dict the way _parse_critic_json does."""
    out = {}
    for name, score in by_provider.items():
        if score == "failed":
            out[name] = {
                "score": 0,
                "summary": "Multi-LLM critic parse error — manual review required",
                "flaws": ["Could not parse LLM output"],
                "llm_parse_error": True,
            }
        else:
            out[name] = {"score": score, "flaws": [], "suggestions": []}
    return out


def _aggregate(agent: CriticAgent, reviews: dict):
    """Mirror multi_critic_review's step 4 exactly."""
    scored = {
        n: r.get("score", 0)
        for n, r in reviews.items()
        if "error" not in r and not r.get("llm_parse_error")
    }
    weights = {n: (1.5 if n == "primary" else 1.0) for n in scored}
    return scored, agent._robust_aggregate(scored, weights)


def test_failed_critic_is_excluded_not_scored_zero():
    agent = CriticAgent()
    scored, final = _aggregate(agent, _reviews(gemini="failed", primary=35, ollama=61))

    assert "gemini" not in scored, "a critic that never answered must not be scored"
    assert set(scored) == {"primary", "ollama"}
    # With the phantom 0 included the weighted median collapsed toward 0/35; excluding it
    # the verdict reflects the critics that actually spoke.
    assert final >= 35, f"phantom zero still dragging the verdict: {final}"


def test_single_phantom_is_absorbed_by_the_median_but_still_excluded():
    """Honest scoping of the bug: with ONE non-answer the weighted median already absorbs
    the phantom (that is the whole point of a median). Excluding it is still correct — the
    reported provider_scores must not show a 0 that nobody voted — but the verdict is
    unchanged. Do not overclaim: this case is a reporting bug, not a scoring bug."""
    agent = CriticAgent()
    _, honest = _aggregate(agent, _reviews(gemini="failed", primary=70, ollama=80))
    with_phantom = agent._robust_aggregate(
        {"gemini": 0, "primary": 70, "ollama": 80},
        {"gemini": 1.0, "primary": 1.5, "ollama": 1.0},
    )
    assert honest == with_phantom == 70


def test_two_phantoms_collapse_the_verdict_to_zero():
    """THIS is the scoring bug. Two non-answers out-weigh the one critic that actually
    spoke, and the median lands on a 0 that no critic ever gave — failing work that was
    rated 70. A panel is only robust to failures it does not COUNT."""
    agent = CriticAgent()
    _, honest = _aggregate(agent, _reviews(gemini="failed", ollama="failed", primary=70))

    with_phantoms = agent._robust_aggregate(
        {"gemini": 0, "ollama": 0, "primary": 70},
        {"gemini": 1.0, "ollama": 1.0, "primary": 1.5},
    )
    assert with_phantoms == 0, "precondition: phantoms collapse the median"
    assert honest == 70, f"the one critic that answered said 70, got {honest}"


def test_a_genuine_zero_is_still_counted():
    """The fix must not let a real, parseable 0 escape — that IS a verdict."""
    agent = CriticAgent()
    scored, final = _aggregate(agent, _reviews(gemini=0, primary=60, ollama=70))

    assert "gemini" in scored, "a genuine parseable 0 is a real verdict and must count"
    assert final < 70


def test_all_critics_failing_yields_no_score_not_zero():
    agent = CriticAgent()
    scored, final = _aggregate(agent, _reviews(gemini="failed", primary="failed",
                                               ollama="failed"))
    assert scored == {}, "a panel-wide outage must produce NO score"
    # _robust_aggregate({}) returns 0 — which is exactly why callers must read
    # panel_unscored rather than trust `score`.
    assert final == 0
