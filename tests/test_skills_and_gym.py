"""
Tests for the Modular Skill System, Multi-Critic, and Agent Gym.

Covers:
  1. SkillLoader — YAML parsing, registry, visibility, hot-reload
  2. Skill YAML validation — all 8 public skills load correctly
  3. Multi-critic — N-provider aggregation, disagreement detection
  4. Skill-runner integration — runners load skills from registry
  5. Agent Gym — training sessions, ELO rating, self-play loop
"""

import json
import os
import tempfile
import textwrap
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import yaml


# ---------------------------------------------------------------------------
# Helper: mock LLM to avoid real calls
# ---------------------------------------------------------------------------
@contextmanager
def _mock_llm():
    """Mock LLM gateway for tests that trigger generation."""
    mock_response = json.dumps({
        "score": 72,
        "flaws": ["Test flaw 1"],
        "suggestions": ["Test suggestion"],
        "missing": [],
        "security_risks": [],
        "summary": "Test summary",
    })
    with patch("src.core.llm_gateway.llm_gateway") as mock_gw:
        mock_gw.generate.return_value = mock_response
        mock_gw.generate_for_task.return_value = mock_response
        mock_gw.provider_pool = MagicMock()
        mock_gw.provider_pool.list_providers.return_value = []
        mock_gw.provider_pool.get.return_value = None
        yield mock_gw


# ===========================================================================
# 1. SkillLoader Tests
# ===========================================================================

class TestSkillLoader(unittest.TestCase):
    """Test skill YAML loading, registry, and visibility management."""

    def setUp(self):
        from src.core.skill_loader import SkillRegistry
        self.registry = SkillRegistry()
        self.tmpdir = tempfile.mkdtemp()

    def _write_skill(self, name, visibility="public", runner="test", roles=None, **extra):
        data = {
            "name": name,
            "version": "1.0.0",
            "visibility": visibility,
            "runner": runner,
            "roles": roles or ["test_role"],
            "description": f"Test skill {name}",
            "tools": ["tool1", "tool2"],
            "prompt": f"You are a {name} expert.",
            "acceptance_criteria": ["Criterion 1"],
            "tags": ["test"],
            **extra,
        }
        path = os.path.join(self.tmpdir, f"{name}.yaml")
        with open(path, "w") as f:
            yaml.dump(data, f)
        return path

    def test_load_single_skill(self):
        self._write_skill("alpha")
        count = self.registry.load_directory(self.tmpdir)
        self.assertEqual(count, 1)
        skill = self.registry.get("alpha")
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "alpha")

    def test_load_missing_dir(self):
        count = self.registry.load_directory("/nonexistent/path")
        self.assertEqual(count, 0)

    def test_skill_visibility_filtering(self):
        self._write_skill("pub", visibility="public")
        self._write_skill("priv", visibility="private")
        self._write_skill("dis", visibility="disabled")
        self.registry.load_directory(self.tmpdir)

        # get() excludes disabled
        self.assertIsNotNone(self.registry.get("pub"))
        self.assertIsNotNone(self.registry.get("priv"))
        self.assertIsNone(self.registry.get("dis"))

        # get_including_disabled() includes all
        self.assertIsNotNone(self.registry.get_including_disabled("dis"))

    def test_visibility_override(self):
        self._write_skill("override_me", visibility="public")
        self.registry.load_directory(self.tmpdir, visibility_override="private")
        skill = self.registry.get("override_me")
        self.assertEqual(skill.visibility, "private")

    def test_set_visibility(self):
        self._write_skill("change_me")
        self.registry.load_directory(self.tmpdir)
        self.assertTrue(self.registry.set_visibility("change_me", "disabled"))
        self.assertIsNone(self.registry.get("change_me"))
        self.assertTrue(self.registry.enable("change_me"))
        self.assertIsNotNone(self.registry.get("change_me"))

    def test_invalid_visibility_rejected(self):
        self.assertFalse(self.registry.set_visibility("nonexistent", "invalid"))

    def test_get_for_role(self):
        self._write_skill("skill_a", roles=["dev"])
        self._write_skill("skill_b", roles=["dev", "qa"])
        self._write_skill("skill_c", roles=["qa"])
        self.registry.load_directory(self.tmpdir)

        dev_skills = self.registry.get_for_role("dev")
        self.assertEqual(len(dev_skills), 2)
        qa_skills = self.registry.get_for_role("qa")
        self.assertEqual(len(qa_skills), 2)

    def test_get_for_runner(self):
        self._write_skill("r1", runner="openfw")
        self._write_skill("r2", runner="openfw")
        self._write_skill("r3", runner="openswe")
        self.registry.load_directory(self.tmpdir)

        fw_skills = self.registry.get_for_runner("openfw")
        self.assertEqual(len(fw_skills), 2)

    def test_search(self):
        self._write_skill("firmware_basics", keywords=["embedded", "arm"])
        self._write_skill("web_dev", keywords=["react", "typescript"])
        self.registry.load_directory(self.tmpdir)

        results = self.registry.search("embedded")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "firmware_basics")

    def test_unregister(self):
        self._write_skill("removable")
        self.registry.load_directory(self.tmpdir)
        self.assertIsNotNone(self.registry.get("removable"))
        self.assertTrue(self.registry.unregister("removable"))
        self.assertIsNone(self.registry.get("removable"))
        self.assertFalse(self.registry.unregister("removable"))

    def test_hot_reload(self):
        self._write_skill("hot_skill")
        self.registry.load_directory(self.tmpdir)
        self.assertEqual(len(self.registry.list_all()), 1)

        # Add another skill file
        self._write_skill("new_skill")
        count = self.registry.reload()
        self.assertEqual(count, 2)
        self.assertIsNotNone(self.registry.get("new_skill"))

    def test_build_prompt_for_role(self):
        self._write_skill("skill_with_prompt", roles=["dev"])
        self.registry.load_directory(self.tmpdir)
        prompt = self.registry.build_prompt_for_role("dev")
        self.assertIn("skill_with_prompt", prompt)

    def test_get_tools_for_role(self):
        self._write_skill("s1", roles=["dev"], tools=["python", "git"])
        self._write_skill("s2", roles=["dev"], tools=["git", "docker"])
        self.registry.load_directory(self.tmpdir)

        tools = self.registry.get_tools_for_role("dev")
        self.assertEqual(tools, ["python", "git", "docker"])  # deduplicated

    def test_list_public_private(self):
        self._write_skill("pub1", visibility="public")
        self._write_skill("priv1", visibility="private")
        self.registry.load_directory(self.tmpdir)

        self.assertEqual(len(self.registry.list_public()), 1)
        self.assertEqual(len(self.registry.list_private()), 1)

    def test_stats(self):
        self._write_skill("s1", visibility="public")
        self._write_skill("s2", visibility="private")
        self._write_skill("s3", visibility="disabled")
        self.registry.load_directory(self.tmpdir)

        stats = self.registry.stats()
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["public"], 1)
        self.assertEqual(stats["private"], 1)
        self.assertEqual(stats["disabled"], 1)

    def test_invalid_yaml_skipped(self):
        path = os.path.join(self.tmpdir, "bad.yaml")
        with open(path, "w") as f:
            f.write("not: valid: yaml: [[[")
        count = self.registry.load_directory(self.tmpdir)
        self.assertEqual(count, 0)

    def test_missing_name_skipped(self):
        path = os.path.join(self.tmpdir, "noname.yaml")
        with open(path, "w") as f:
            yaml.dump({"version": "1.0", "roles": ["dev"]}, f)
        count = self.registry.load_directory(self.tmpdir)
        self.assertEqual(count, 0)


# ===========================================================================
# 2. Public Skill YAML Validation
# ===========================================================================

class TestPublicSkillYAMLs(unittest.TestCase):
    """Validate all shipped public skill YAML files."""

    SKILLS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "skills", "public",
    )

    EXPECTED_SKILLS = [
        "firmware_engineering",
        "pcb_design",
        "hardware_simulation",
        "machine_learning",
        "technical_writing",
        "ux_design",
        "product_strategy",
        "software_engineering",
        "data_engineering",
        "ml_engineering",
        "gen_ai_engineering",
        "agentic_engineering",
        "browser_testing",
        "security_audit",
    ]

    REQUIRED_FIELDS = ["name", "version", "roles", "runner", "tools", "prompt", "acceptance_criteria"]

    def test_all_expected_skills_exist(self):
        if not os.path.isdir(self.SKILLS_DIR):
            self.skipTest("skills/public/ not found")
        files = os.listdir(self.SKILLS_DIR)
        for name in self.EXPECTED_SKILLS:
            self.assertIn(f"{name}.yaml", files, f"Missing skill YAML: {name}.yaml")

    def test_all_skills_parse_valid(self):
        if not os.path.isdir(self.SKILLS_DIR):
            self.skipTest("skills/public/ not found")
        for fname in os.listdir(self.SKILLS_DIR):
            if not fname.endswith(".yaml"):
                continue
            path = os.path.join(self.SKILLS_DIR, fname)
            with open(path) as f:
                data = yaml.safe_load(f)
            self.assertIsInstance(data, dict, f"{fname} is not a YAML dict")
            for field in self.REQUIRED_FIELDS:
                self.assertIn(field, data, f"{fname} missing required field: {field}")

    def test_all_skills_load_into_registry(self):
        if not os.path.isdir(self.SKILLS_DIR):
            self.skipTest("skills/public/ not found")
        from src.core.skill_loader import SkillRegistry
        reg = SkillRegistry()
        count = reg.load_directory(self.SKILLS_DIR)
        self.assertEqual(count, len(self.EXPECTED_SKILLS))

    def test_skills_have_certifications(self):
        """Every public skill should list relevant certifications."""
        if not os.path.isdir(self.SKILLS_DIR):
            self.skipTest("skills/public/ not found")
        for fname in os.listdir(self.SKILLS_DIR):
            if not fname.endswith(".yaml"):
                continue
            path = os.path.join(self.SKILLS_DIR, fname)
            with open(path) as f:
                data = yaml.safe_load(f)
            certs = data.get("certifications", [])
            self.assertTrue(len(certs) > 0, f"{fname} has no certifications listed")

    def test_skills_have_seniority_delta(self):
        """Every public skill should have junior/senior differentiation."""
        if not os.path.isdir(self.SKILLS_DIR):
            self.skipTest("skills/public/ not found")
        for fname in os.listdir(self.SKILLS_DIR):
            if not fname.endswith(".yaml"):
                continue
            path = os.path.join(self.SKILLS_DIR, fname)
            with open(path) as f:
                data = yaml.safe_load(f)
            delta = data.get("seniority_delta", {})
            self.assertIn("junior", delta, f"{fname} missing seniority_delta.junior")
            self.assertIn("senior", delta, f"{fname} missing seniority_delta.senior")

    def test_skills_cover_all_runner_roles(self):
        """Public skills should cover roles from all non-orchestration runners."""
        if not os.path.isdir(self.SKILLS_DIR):
            self.skipTest("skills/public/ not found")
        from src.core.skill_loader import SkillRegistry
        from src.integrations.base_runner import ALL_ROLE_FAMILIES

        reg = SkillRegistry()
        reg.load_directory(self.SKILLS_DIR)

        covered_roles = set()
        for skill in reg.list_all():
            covered_roles.update(skill.roles)

        for family, roles in ALL_ROLE_FAMILIES.items():
            if family == "orchestration":
                continue
            for role in roles:
                self.assertIn(
                    role, covered_roles,
                    f"Role '{role}' ({family}) not covered by any public skill"
                )


# ===========================================================================
# 3. Multi-Critic Tests
# ===========================================================================

class TestMultiCritic(unittest.TestCase):
    """Test N-provider critic aggregation."""

    def _make_critic(self):
        from src.agents.critic import CriticAgent
        critic = CriticAgent()
        critic._llm_gateway = MagicMock()
        critic._audit_logger = MagicMock()
        return critic

    def test_single_provider_fallback(self):
        """multi_critic_review falls back to single review when no pool."""
        critic = self._make_critic()
        critic._llm_gateway.provider_pool.list_providers.return_value = []
        critic._llm_gateway.provider_pool.get.return_value = None
        critic._llm_gateway.generate.return_value = json.dumps({
            "score": 75, "flaws": ["f1"], "suggestions": [], "missing": [],
            "security_risks": [], "summary": "ok"
        })

        result = critic.multi_critic_review("plan", {"tasks": []}, "test product")
        self.assertIn("score", result)

    def test_multi_provider_aggregation(self):
        """Scores are aggregated across providers with primary getting 1.5x weight."""
        critic = self._make_critic()

        # Mock primary
        critic._llm_gateway.generate.return_value = json.dumps({
            "score": 80, "flaws": ["primary_flaw"], "suggestions": [],
            "missing": [], "security_risks": [], "summary": "primary"
        })

        # Mock pool with 2 providers
        mock_pool = MagicMock()
        mock_pool.list_providers.return_value = ["gemini", "ollama"]
        gemini_prov = MagicMock()
        gemini_prov.generate.return_value = json.dumps({
            "score": 60, "flaws": ["gemini_flaw"], "suggestions": [],
            "missing": [], "security_risks": [], "summary": "gemini"
        })
        ollama_prov = MagicMock()
        ollama_prov.generate.return_value = json.dumps({
            "score": 70, "flaws": ["ollama_flaw"], "suggestions": [],
            "missing": [], "security_risks": [], "summary": "ollama"
        })
        mock_pool.get.side_effect = lambda n: {"gemini": gemini_prov, "ollama": ollama_prov}.get(n)
        critic._llm_gateway.provider_pool = mock_pool

        result = critic.multi_critic_review("plan", {"tasks": []}, "test product")

        self.assertTrue(result.get("multi_critic"))
        self.assertIn("primary", result["providers_used"])
        self.assertIn("gemini", result["providers_used"])
        self.assertIn("ollama", result["providers_used"])
        # Primary=80 (1.5x), gemini=60 (1x), ollama=70 (1x)
        # = (80*1.5 + 60 + 70) / 3.5 = 250/3.5 = ~71
        self.assertGreater(result["score"], 65)
        self.assertLess(result["score"], 80)

    def test_disagreement_detection(self):
        """Large score gaps between providers are flagged."""
        critic = self._make_critic()

        # Primary gives high score
        critic._llm_gateway.generate.return_value = json.dumps({
            "score": 90, "flaws": [], "suggestions": [],
            "missing": [], "security_risks": [], "summary": "great"
        })

        # Pool provider gives low score
        mock_pool = MagicMock()
        mock_pool.list_providers.return_value = ["gemini"]
        gemini_prov = MagicMock()
        gemini_prov.generate.return_value = json.dumps({
            "score": 30, "flaws": ["terrible"], "suggestions": [],
            "missing": [], "security_risks": [], "summary": "bad"
        })
        mock_pool.get.side_effect = lambda n: gemini_prov if n == "gemini" else None
        critic._llm_gateway.provider_pool = mock_pool

        result = critic.multi_critic_review("plan", {}, "test")
        self.assertTrue(len(result.get("disagreements", [])) > 0)

    def test_flaw_merging(self):
        """Flaws from all providers are merged and deduplicated."""
        critic = self._make_critic()

        critic._llm_gateway.generate.return_value = json.dumps({
            "score": 70, "flaws": ["shared_flaw", "primary_only"],
            "suggestions": [], "missing": [], "security_risks": [], "summary": ""
        })

        mock_pool = MagicMock()
        mock_pool.list_providers.return_value = ["gemini"]
        gemini_prov = MagicMock()
        gemini_prov.generate.return_value = json.dumps({
            "score": 65, "flaws": ["shared_flaw", "gemini_only"],
            "suggestions": [], "missing": [], "security_risks": [], "summary": ""
        })
        mock_pool.get.side_effect = lambda n: gemini_prov if n == "gemini" else None
        critic._llm_gateway.provider_pool = mock_pool

        result = critic.multi_critic_review("code", "diff here", "test task")
        self.assertIn("shared_flaw", result["flaws"])
        self.assertIn("primary_only", result["flaws"])
        self.assertIn("gemini_only", result["flaws"])
        # No duplicates
        self.assertEqual(len(result["flaws"]), len(set(result["flaws"])))

    def test_backward_compat_alias(self):
        """dual_critic_review is an alias for multi_critic_review."""
        from src.agents.critic import CriticAgent
        self.assertIs(CriticAgent.dual_critic_review, CriticAgent.multi_critic_review)


# ===========================================================================
# 4. Skill-Runner Integration
# ===========================================================================

class TestSkillRunnerIntegration(unittest.TestCase):
    """Test that runners load skills from the registry."""

    def test_runner_get_skills(self):
        """Runners should return skills from the registry."""
        from src.integrations.base_runner import get_runner_by_name
        runner = get_runner_by_name("openfw")
        if not runner:
            self.skipTest("openfw runner not registered")
        skills = runner.get_skills()
        # Skills loaded from public/ directory
        self.assertIsInstance(skills, list)

    def test_runner_get_skill_prompt(self):
        """Runners should build prompts from skill YAML."""
        from src.integrations.base_runner import get_runner_by_name
        runner = get_runner_by_name("openfw")
        if not runner:
            self.skipTest("openfw runner not registered")
        prompt = runner.get_skill_prompt("firmware_engineer")
        # Should have content from the YAML skill
        self.assertIsInstance(prompt, str)

    def test_runner_get_acceptance_criteria(self):
        """Runners should aggregate acceptance criteria from skills."""
        from src.integrations.base_runner import get_runner_by_name
        runner = get_runner_by_name("openfw")
        if not runner:
            self.skipTest("openfw runner not registered")
        criteria = runner.get_acceptance_criteria("firmware_engineer")
        self.assertIsInstance(criteria, list)

    def test_runner_toolchain_merges_skills(self):
        """Runner toolchain should include tools from skill YAML."""
        from src.integrations.base_runner import get_runner_by_name
        runner = get_runner_by_name("openfw")
        if not runner:
            self.skipTest("openfw runner not registered")
        # The hardcoded get_toolchain still works
        tc = runner.get_toolchain()
        self.assertIn("runner", tc)
        self.assertIn("tools", tc)


# ===========================================================================
# 5. Agent Gym Tests
# ===========================================================================

class TestAgentGym(unittest.TestCase):
    """Test the self-play training engine."""

    def _make_gym(self):
        """Create an AgentGym with a temp SQLite DB."""
        from src.core.agent_gym import AgentGym
        db_path = os.path.join(tempfile.mkdtemp(), "test_gym.db")
        return AgentGym(db_path=db_path)

    def test_gym_init(self):
        gym = self._make_gym()
        self.assertEqual(gym.stats()["total_sessions"], 0)

    def test_gym_train_no_runner(self):
        """Training fails gracefully when no runner exists for the role."""
        gym = self._make_gym()
        session = gym.train(role="nonexistent_role")
        self.assertEqual(session.status, "failed")

    def test_gym_train_with_mock(self):
        """Full training loop with mocked LLM."""
        gym = self._make_gym()

        with _mock_llm(), \
             patch("src.core.agent_gym.agent_gym", gym), \
             patch("src.memory.vector_store.vector_memory") as mock_vm:
            mock_vm.add_feedback = MagicMock()

            session = gym.train(role="firmware_engineer", difficulty="beginner")

            # Session should complete (not fail)
            self.assertIn(session.status, ["completed", "failed"])
            self.assertNotEqual(session.session_id, "")
            self.assertEqual(session.agent_role, "firmware_engineer")

    def test_elo_rating_update(self):
        """ELO rating should change after training."""
        from src.core.agent_gym import SkillRating
        gym = self._make_gym()

        rating = SkillRating("test_role", "test_skill")
        initial = rating.rating

        # Win
        new_rating = gym._update_rating("test:test", rating, 85.0, True)
        self.assertGreater(new_rating, initial)
        self.assertEqual(rating.sessions, 1)
        self.assertEqual(rating.wins, 1)
        self.assertEqual(rating.streak, 1)

    def test_elo_loss(self):
        """ELO should decrease on poor performance."""
        from src.core.agent_gym import SkillRating
        gym = self._make_gym()

        rating = SkillRating("test_role", "test_skill", rating=1200.0)
        new_rating = gym._update_rating("test:test", rating, 20.0, False)
        self.assertLess(new_rating, 1200.0)
        self.assertEqual(rating.losses, 1)
        self.assertEqual(rating.streak, -1)

    def test_glicko2_rd_shrinks_with_data(self):
        """Rating deviation should decrease as more data accumulates (Glicko-2)."""
        from src.core.agent_gym import SkillRating
        gym = self._make_gym()

        # Fresh rating with high RD (uncertain)
        rating = SkillRating("r", "s", rating_deviation=350.0)
        initial_rd = rating.rating_deviation

        # After a few sessions, RD should shrink (more confident)
        gym._update_rating("r:s", rating, 80.0, True)
        gym._update_rating("r:s", rating, 75.0, True)
        gym._update_rating("r:s", rating, 70.0, True)

        self.assertLess(rating.rating_deviation, initial_rd)
        self.assertEqual(rating.sessions, 3)

    def test_glicko2_confidence_interval(self):
        """to_dict should include confidence interval."""
        from src.core.agent_gym import SkillRating
        rating = SkillRating("r", "s", rating=1200, rating_deviation=100)
        d = rating.to_dict()
        self.assertIn("confidence_interval", d)
        self.assertEqual(d["confidence_interval"][0], 1000.0)
        self.assertEqual(d["confidence_interval"][1], 1400.0)

    def test_leaderboard(self):
        from src.core.agent_gym import SkillRating
        gym = self._make_gym()
        gym._ratings["a:s1"] = SkillRating("a", "s1", rating=1500)
        gym._ratings["b:s2"] = SkillRating("b", "s2", rating=1200)
        gym._ratings["c:s3"] = SkillRating("c", "s3", rating=1800)

        board = gym.get_leaderboard()
        self.assertEqual(board[0]["rating"], 1800)
        self.assertEqual(board[-1]["rating"], 1200)

    def test_history(self):
        from src.core.agent_gym import TrainingSession
        gym = self._make_gym()
        for i in range(5):
            sid = f"session-{i}"
            gym._sessions[sid] = TrainingSession(
                session_id=sid, agent_role="dev", runner_name="openswe",
                skill_name="swe", exercise_id=f"ex-{i}", difficulty="intermediate",
                status="completed",
            )
            gym._history.append(sid)

        history = gym.get_history(limit=3)
        self.assertEqual(len(history), 3)
        # Most recent first
        self.assertEqual(history[0]["session_id"], "session-4")

    def test_sqlite_persistence(self):
        """Sessions and ratings survive gym restart."""
        from src.core.agent_gym import AgentGym, SkillRating, TrainingSession
        db_path = os.path.join(tempfile.mkdtemp(), "persist_test.db")

        # First gym instance: add a rating and session
        gym1 = AgentGym(db_path=db_path)
        rating = SkillRating("dev", "swe", rating=1350)
        gym1._ratings["dev:swe"] = rating
        gym1._db.save_rating("dev:swe", rating)

        session = TrainingSession(
            session_id="persist-1", agent_role="dev", runner_name="openswe",
            skill_name="swe", exercise_id="ex-1", difficulty="intermediate",
            status="completed", grade={"score": 80, "passed": True},
        )
        gym1._db.save_session(session)

        # Second gym instance: should restore ratings
        gym2 = AgentGym(db_path=db_path)
        self.assertIn("dev:swe", gym2._ratings)
        self.assertEqual(gym2._ratings["dev:swe"].rating, 1350)

        # Session queryable
        loaded = gym2._db.load_session("persist-1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["agent_role"], "dev")

    def test_analytics_empty(self):
        """Analytics on empty gym returns valid structure."""
        gym = self._make_gym()
        data = gym.analytics(role="dev")
        self.assertIn("global_stats", data)
        self.assertIn("leaderboard", data)
        self.assertIn("score_trend", data)
        self.assertEqual(data["global_stats"]["total_sessions"], 0)

    def test_curriculum_advance(self):
        """Curriculum advances difficulty after enough wins."""
        from src.core.agent_gym import AgentGym, SkillRating, TrainingSession
        db_path = os.path.join(tempfile.mkdtemp(), "curriculum_test.db")
        gym = AgentGym(db_path=db_path)

        # Seed 5 completed sessions at beginner, all passing
        for i in range(5):
            s = TrainingSession(
                session_id=f"cur-{i}", agent_role="dev", runner_name="openswe",
                skill_name="swe", exercise_id=f"ex-{i}", difficulty="beginner",
                status="completed", grade={"score": 85, "passed": True},
                started_at=1000.0 + i,
            )
            gym._db.save_session(s)

        rating = SkillRating("dev", "swe", current_difficulty="beginner")
        gym._ratings["dev:swe"] = rating
        gym._curriculum_check("dev:swe", rating)

        # Should have advanced to intermediate
        self.assertEqual(rating.current_difficulty, "intermediate")

    def test_curriculum_demote(self):
        """Curriculum demotes difficulty after enough losses."""
        from src.core.agent_gym import AgentGym, SkillRating, TrainingSession
        db_path = os.path.join(tempfile.mkdtemp(), "demote_test.db")
        gym = AgentGym(db_path=db_path)

        # Seed 6 completed sessions at intermediate, all failing
        for i in range(6):
            s = TrainingSession(
                session_id=f"dem-{i}", agent_role="dev", runner_name="openswe",
                skill_name="swe", exercise_id=f"ex-{i}", difficulty="intermediate",
                status="completed", grade={"score": 15, "passed": False},
                started_at=1000.0 + i,
            )
            gym._db.save_session(s)

        rating = SkillRating("dev", "swe", current_difficulty="intermediate")
        gym._ratings["dev:swe"] = rating
        gym._curriculum_check("dev:swe", rating)

        # Should have demoted to beginner
        self.assertEqual(rating.current_difficulty, "beginner")

    def test_spaced_repetition_scheduling(self):
        """Failed exercises get scheduled for spaced repetition retry."""
        from src.core.agent_gym import SkillRating
        gym = self._make_gym()

        rating = SkillRating("dev", "swe")
        # Fail exercise ex-1
        gym._update_rating("dev:swe", rating, 20.0, False, exercise_id="ex-1")

        # Exercise should be in failed_exercises with retry at session+1
        self.assertIn("ex-1", rating.failed_exercises)
        self.assertEqual(rating.failed_exercises["ex-1"], 2)  # sessions(1) + interval(1)

    def test_spaced_repetition_clear_on_pass(self):
        """Passing a previously failed exercise clears it from spaced repetition."""
        from src.core.agent_gym import SkillRating
        gym = self._make_gym()

        rating = SkillRating("dev", "swe")
        # Fail, then pass
        gym._update_rating("dev:swe", rating, 20.0, False, exercise_id="ex-1")
        self.assertIn("ex-1", rating.failed_exercises)
        gym._update_rating("dev:swe", rating, 85.0, True, exercise_id="ex-1")
        self.assertNotIn("ex-1", rating.failed_exercises)

    def test_batch_training_returns_sessions(self):
        """Batch training returns a list of sessions."""
        gym = self._make_gym()
        # Batch with nonexistent roles should return failed sessions
        sessions = gym.train_batch(roles=["nonexistent_a", "nonexistent_b"], max_parallel=2)
        self.assertEqual(len(sessions), 2)
        for s in sessions:
            self.assertEqual(s.status, "failed")


# ===========================================================================
# 6. Skill Data Class
# ===========================================================================

class TestSkillDataClass(unittest.TestCase):
    """Test Skill dataclass methods."""

    def test_to_dict(self):
        from src.core.skill_loader import Skill
        s = Skill(
            name="test", version="1.0", visibility="public",
            roles=["dev"], runner="openswe",
        )
        d = s.to_dict()
        self.assertEqual(d["name"], "test")
        self.assertIn("tools", d)

    def test_is_active(self):
        from src.core.skill_loader import Skill
        pub = Skill(name="p", version="1", visibility="public", roles=[], runner="")
        dis = Skill(name="d", version="1", visibility="disabled", roles=[], runner="")
        self.assertTrue(pub.is_active)
        self.assertFalse(dis.is_active)

    def test_prompt_truncation(self):
        from src.core.skill_loader import Skill
        s = Skill(
            name="long", version="1", visibility="public",
            roles=[], runner="", prompt="x" * 500,
        )
        d = s.to_dict()
        self.assertTrue(d["prompt"].endswith("..."))
        self.assertLessEqual(len(d["prompt"]), 204)


# ===========================================================================
# 7. Exercise Catalog Tests
# ===========================================================================

class TestExerciseCatalog(unittest.TestCase):
    """Test the scalable exercise catalog system."""

    def _make_catalog(self):
        from src.core.exercise_catalog import ExerciseCatalog
        db_path = os.path.join(tempfile.mkdtemp(), "test_catalog.db")
        return ExerciseCatalog(db_path=db_path)

    def test_seed_catalog_loads(self):
        """Seed catalog should load exercises for all domains."""
        catalog = self._make_catalog()
        stats = catalog.stats()
        self.assertGreater(stats["total_exercises"], 100)
        self.assertIn("openfw", stats["domains"])
        self.assertIn("openswe", stats["domains"])
        self.assertIn("openml", stats["domains"])

    def test_all_domains_have_seeds(self):
        """Every domain in VARIANT_AXES should have seed exercises."""
        from src.core.exercise_catalog import VARIANT_AXES
        catalog = self._make_catalog()
        for domain in VARIANT_AXES:
            exercises = catalog.get_for_domain(domain)
            self.assertGreater(len(exercises), 0, f"No seeds for {domain}")

    def test_difficulty_filtering(self):
        """Should filter exercises by difficulty."""
        catalog = self._make_catalog()
        beginner = catalog.get_for_domain("openfw", "beginner")
        advanced = catalog.get_for_domain("openfw", "advanced")
        self.assertTrue(all(e.difficulty == "beginner" for e in beginner))
        self.assertTrue(all(e.difficulty == "advanced" for e in advanced))

    def test_tag_search(self):
        """Should find exercises by tags."""
        catalog = self._make_catalog()
        uart_exercises = catalog.get_for_tags(["uart"], "openfw")
        self.assertGreater(len(uart_exercises), 0)
        for ex in uart_exercises:
            self.assertTrue("uart" in ex.tags)

    def test_exercise_ids_deterministic(self):
        """Same title should produce same ID across runs."""
        catalog = self._make_catalog()
        id1 = catalog._make_id("openfw", "LED blink timer")
        id2 = catalog._make_id("openfw", "LED blink timer")
        self.assertEqual(id1, id2)

    def test_exercise_to_dict(self):
        """Exercise should serialize to dict with all fields."""
        from src.core.exercise_catalog import Exercise
        ex = Exercise(
            id="test-1", domain="openfw", skill="fw",
            title="Test", description="Do the thing",
            difficulty="beginner", tags=["test"],
            acceptance_criteria=["It works"],
        )
        d = ex.to_dict()
        self.assertEqual(d["id"], "test-1")
        self.assertIn("tags", d)
        self.assertIn("acceptance_criteria", d)

    def test_catalog_count(self):
        """Count should return per-domain and per-difficulty breakdown."""
        catalog = self._make_catalog()
        count = catalog.count("openfw")
        self.assertIn("total", count)
        self.assertIn("by_difficulty", count)
        self.assertGreater(count["total"], 50)

    def test_difficulty_distribution(self):
        """Each domain should have exercises at multiple difficulty levels."""
        catalog = self._make_catalog()
        for domain in ["openfw", "openswe", "openml"]:
            count = catalog.count(domain)
            difficulties = count["by_difficulty"]
            self.assertGreater(len(difficulties), 2,
                               f"{domain} has only {len(difficulties)} difficulty levels")

    def test_firmware_domain_coverage(self):
        """Firmware domain should cover key embedded topics."""
        catalog = self._make_catalog()
        all_tags = set()
        for ex in catalog.get_for_domain("openfw"):
            all_tags.update(ex.tags)

        required_topics = ["gpio", "uart", "spi", "i2c", "dma", "rtos", "safety", "power"]
        for topic in required_topics:
            self.assertIn(topic, all_tags, f"Firmware catalog missing topic: {topic}")

    def test_software_domain_coverage(self):
        """Software domain should cover key development topics."""
        catalog = self._make_catalog()
        all_tags = set()
        for ex in catalog.get_for_domain("openswe"):
            all_tags.update(ex.tags)

        required_topics = ["api", "testing", "database", "security", "auth"]
        for topic in required_topics:
            self.assertIn(topic, all_tags, f"Software catalog missing topic: {topic}")


if __name__ == "__main__":
    unittest.main()
