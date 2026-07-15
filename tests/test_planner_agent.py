"""
SAGE Framework — Planner Agent Tests (TDD)
=============================================
Tests for:
  - PlannerAgent.create_plan() default behaviour (beam_width=1, single-shot)
  - PlannerAgent.create_plan(beam_width=N) — game-theory Phase 2: PlanSelector
    wiring generates N candidate plans, scores each via CriticAgent, and
    returns the best-scoring, fully-validated plan.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

TASK_TYPES = {"DEVELOP": "Write or modify code", "TEST": "Write or run tests"}


def _fresh_planner():
    from src.agents.planner import PlannerAgent

    planner = PlannerAgent()
    planner._llm_gateway = MagicMock()
    planner._audit_logger = MagicMock()
    return planner


def _plan_response(steps):
    return json.dumps(steps)


# ---------------------------------------------------------------------------
# create_plan() — default (beam_width=1) behaviour is unchanged
# ---------------------------------------------------------------------------


class TestCreatePlanDefaultBehaviour:
    def test_single_llm_call_when_beam_width_omitted(self):
        planner = _fresh_planner()
        planner.llm.generate.return_value = _plan_response(
            [{"step": 1, "task_type": "DEVELOP", "description": "do it", "payload": {}}]
        )
        plan = planner.create_plan("build a widget", override_task_types=TASK_TYPES)

        assert planner.llm.generate.call_count == 1
        assert len(plan) == 1
        assert plan[0]["task_type"] == "DEVELOP"

    def test_beam_width_1_is_explicitly_single_shot(self):
        planner = _fresh_planner()
        planner.llm.generate.return_value = _plan_response(
            [{"step": 1, "task_type": "DEVELOP", "description": "do it", "payload": {}}]
        )
        plan = planner.create_plan(
            "build a widget", override_task_types=TASK_TYPES, beam_width=1
        )

        assert planner.llm.generate.call_count == 1
        assert len(plan) == 1

    def test_unparseable_response_returns_empty_list(self):
        planner = _fresh_planner()
        planner.llm.generate.return_value = "not json at all"
        plan = planner.create_plan("build a widget", override_task_types=TASK_TYPES)
        assert plan == []


# ---------------------------------------------------------------------------
# create_plan(beam_width=N) — PlanSelector wiring (game-theory Phase 2)
# ---------------------------------------------------------------------------


class TestCreatePlanBeamSearch:
    def test_generates_n_candidates_and_scores_each(self):
        planner = _fresh_planner()
        # Each generator call returns a distinct one-step plan.
        planner.llm.generate.side_effect = [
            _plan_response(
                [
                    {
                        "step": 1,
                        "task_type": "DEVELOP",
                        "description": f"variant {i}",
                        "payload": {},
                    }
                ]
            )
            for i in range(3)
        ]

        with patch("src.agents.critic.critic_agent") as mock_critic:
            mock_critic.multi_critic_review.side_effect = [
                {"score": 40, "summary": "weak"},
                {"score": 90, "summary": "strong"},
                {"score": 60, "summary": "ok"},
            ]
            plan = planner.create_plan(
                "build a widget", override_task_types=TASK_TYPES, beam_width=3
            )

        assert planner.llm.generate.call_count == 3
        assert mock_critic.multi_critic_review.call_count == 3
        # The highest-scored candidate ("strong", variant 1) must win.
        assert plan[0]["description"] == "variant 1"

    def test_falls_back_to_empty_list_when_all_candidates_fail_to_parse(self):
        planner = _fresh_planner()
        planner.llm.generate.side_effect = ["not json"] * 3

        with patch("src.agents.critic.critic_agent") as mock_critic:
            mock_critic.multi_critic_review.return_value = {"score": 0, "summary": ""}
            plan = planner.create_plan(
                "build a widget", override_task_types=TASK_TYPES, beam_width=3
            )

        assert plan == []

    def test_validates_and_filters_steps_in_every_candidate(self):
        planner = _fresh_planner()
        planner.llm.generate.side_effect = [
            _plan_response(
                [
                    {
                        "step": 1,
                        "task_type": "DEVELOP",
                        "description": "ok",
                        "payload": {},
                    },
                    {
                        "step": 2,
                        "task_type": "BOGUS_TYPE",
                        "description": "bad",
                        "payload": {},
                    },
                ]
            ),
            _plan_response(
                [
                    {
                        "step": 1,
                        "task_type": "TEST",
                        "description": "also ok",
                        "payload": {},
                    }
                ]
            ),
        ]

        with patch("src.agents.critic.critic_agent") as mock_critic:
            mock_critic.multi_critic_review.side_effect = [
                {"score": 95, "summary": "best"},
                {"score": 50, "summary": "meh"},
            ]
            plan = planner.create_plan(
                "build a widget", override_task_types=TASK_TYPES, beam_width=2
            )

        # Winning candidate (score 95) had a BOGUS_TYPE step filtered out.
        assert len(plan) == 1
        assert plan[0]["task_type"] == "DEVELOP"
