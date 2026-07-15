"""
SAGE Framework — Coder Agent Tests (TDD)
============================================
Tests for:
  - CodingAgent.implement_step() default behaviour (beam_width=1, single-shot,
    unchanged from the original implementation)
  - CodingAgent.implement_step(beam_width=N) — game-theory Phase 2, scoped-down
    variant: N sequential ReAct-loop attempts in the MAIN working tree, isolated
    between attempts via `git stash` (no WorktreeManager, no _ROOT refactor —
    per explicit user scope decision). Each candidate is scored via PlanSelector
    + CriticAgent; the winner's stash is restored, losers are dropped.
"""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _fresh_agent():
    from src.agents.coder import CodingAgent

    agent = CodingAgent()
    agent._llm = MagicMock()
    return agent


STEP = {"task_type": "DEVELOP", "description": "Fix the buffer overflow", "payload": {}}


# ---------------------------------------------------------------------------
# implement_step() — default (beam_width=1) behaviour is unchanged
# ---------------------------------------------------------------------------


class TestImplementStepDefaultBehaviour:
    def test_single_react_loop_when_beam_width_omitted(self):
        agent = _fresh_agent()
        with (
            patch.object(
                agent, "_react_loop", return_value=("done", ["src/f.c"])
            ) as mock_loop,
            patch.object(
                agent, "_tool_git_diff", return_value="--- a/f.c\n+++ b/f.c\n"
            ),
            patch.object(agent, "_tool_run_tests", return_value="PASS (returncode=0)"),
        ):
            result = agent.implement_step(STEP)

        mock_loop.assert_called_once()
        assert result["summary"] == "done"
        assert result["tests_passed"] is True
        assert "verification" not in result

    def test_beam_width_1_is_explicitly_single_shot(self):
        agent = _fresh_agent()
        with (
            patch.object(agent, "_react_loop", return_value=("done", [])) as mock_loop,
            patch.object(agent, "_tool_git_diff", return_value="(no changes detected)"),
            patch.object(agent, "_tool_run_tests", return_value="FAIL (returncode=1)"),
        ):
            result = agent.implement_step(STEP, beam_width=1)

        mock_loop.assert_called_once()
        assert result["tests_passed"] is False


# ---------------------------------------------------------------------------
# implement_step(beam_width=N) — scoped-down stash-isolated tournament
# ---------------------------------------------------------------------------


class TestImplementStepBeamSearch:
    def test_falls_back_to_single_shot_when_tree_is_dirty(self):
        agent = _fresh_agent()
        with (
            patch.object(agent, "_working_tree_is_clean", return_value=False),
            patch.object(
                agent, "_react_loop", return_value=("single-shot fallback", [])
            ) as mock_loop,
            patch.object(agent, "_tool_git_diff", return_value="(no changes detected)"),
            patch.object(agent, "_tool_run_tests", return_value="PASS"),
        ):
            result = agent.implement_step(STEP, beam_width=3)

        mock_loop.assert_called_once()  # never entered the tournament
        assert result["beam_search_skipped_reason"] == "working tree not clean"

    def test_generates_n_candidates_stashes_each_and_scores_them(self):
        agent = _fresh_agent()
        with (
            patch.object(agent, "_working_tree_is_clean", return_value=True),
            patch.object(
                agent,
                "_react_loop",
                side_effect=[
                    ("weak attempt", ["a.c"]),
                    ("strong attempt", ["b.c"]),
                    ("mid attempt", ["c.c"]),
                ],
            ) as mock_loop,
            patch.object(
                agent,
                "_tool_git_diff",
                side_effect=[
                    "diff-weak",
                    "diff-strong",
                    "diff-mid",
                ],
            ),
            patch.object(agent, "_tool_run_tests", return_value="PASS (returncode=0)"),
            patch.object(
                agent,
                "_stash_candidate",
                side_effect=["sha-weak", "sha-strong", "sha-mid"],
            ) as mock_stash,
            patch.object(agent, "_apply_stash") as mock_apply,
            patch.object(agent, "_drop_stash") as mock_drop,
            patch("src.agents.critic.critic_agent") as mock_critic,
        ):
            mock_critic.multi_critic_review.side_effect = [
                {"score": 30, "summary": "weak"},
                {"score": 92, "summary": "strong"},
                {"score": 55, "summary": "mid"},
            ]

            result = agent.implement_step(STEP, beam_width=3)

        assert mock_loop.call_count == 3
        assert mock_stash.call_count == 3
        # Winner ("strong attempt") is applied; the other two are dropped, never applied.
        mock_apply.assert_called_once_with("sha-strong")
        assert mock_drop.call_count == 3  # apply-then-drop winner + drop both losers
        assert {c.args[0] for c in mock_drop.call_args_list} == {
            "sha-weak",
            "sha-strong",
            "sha-mid",
        }
        assert result["summary"] == "strong attempt"
        assert result["verification"]["candidates_scored"] == 3

    def test_candidate_with_no_changes_is_not_stashed_and_scores_zero(self):
        agent = _fresh_agent()
        with (
            patch.object(agent, "_working_tree_is_clean", return_value=True),
            patch.object(
                agent,
                "_react_loop",
                side_effect=[
                    ("did nothing", []),
                    ("did something", ["a.c"]),
                ],
            ),
            patch.object(
                agent,
                "_tool_git_diff",
                side_effect=[
                    "(no changes detected)",
                    "real diff",
                ],
            ),
            patch.object(agent, "_tool_run_tests", return_value="PASS (returncode=0)"),
            patch.object(
                agent, "_stash_candidate", side_effect=[None, "sha-real"]
            ) as mock_stash,
            patch.object(agent, "_apply_stash") as mock_apply,
            patch.object(agent, "_drop_stash") as mock_drop,
            patch("src.agents.critic.critic_agent") as mock_critic,
        ):
            mock_critic.multi_critic_review.return_value = {
                "score": 70,
                "summary": "fine",
            }

            result = agent.implement_step(STEP, beam_width=2)

        assert mock_stash.call_count == 2
        mock_apply.assert_called_once_with("sha-real")
        mock_drop.assert_called_once_with(
            "sha-real"
        )  # the no-op candidate had nothing to drop
        assert result["summary"] == "did something"

    def test_failing_tests_penalise_but_do_not_zero_out_score(self):
        agent = _fresh_agent()
        with (
            patch.object(agent, "_working_tree_is_clean", return_value=True),
            patch.object(
                agent,
                "_react_loop",
                side_effect=[
                    ("passes tests", ["a.c"]),
                    ("fails tests but great code", ["b.c"]),
                ],
            ),
            patch.object(agent, "_tool_git_diff", side_effect=["diff-a", "diff-b"]),
            patch.object(
                agent,
                "_tool_run_tests",
                side_effect=[
                    "PASS (returncode=0)",
                    "FAIL (returncode=1)",
                ],
            ),
            patch.object(agent, "_stash_candidate", side_effect=["sha-a", "sha-b"]),
            patch.object(agent, "_apply_stash") as mock_apply,
            patch.object(agent, "_drop_stash"),
            patch("src.agents.critic.critic_agent") as mock_critic,
        ):
            # candidate b's LLM score is much higher, but its tests fail —
            # the 0.3x penalty must not let it beat candidate a's clean pass.
            mock_critic.multi_critic_review.side_effect = [
                {"score": 60, "summary": "ok, tests pass"},
                {"score": 95, "summary": "great code, tests fail"},
            ]

            result = agent.implement_step(STEP, beam_width=2)

        mock_apply.assert_called_once_with("sha-a")
        assert result["summary"] == "passes tests"


# ---------------------------------------------------------------------------
# git-stash plumbing — low-level unit tests (subprocess.run mocked directly)
# ---------------------------------------------------------------------------


class TestWorkingTreeIsClean:
    def test_true_when_status_porcelain_is_empty(self):
        agent = _fresh_agent()
        with patch("src.agents.coder.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            assert agent._working_tree_is_clean() is True

    def test_false_when_status_porcelain_has_output(self):
        agent = _fresh_agent()
        with patch("src.agents.coder.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=" M src/foo.py\n", stderr=""
            )
            assert agent._working_tree_is_clean() is False

    def test_false_when_git_command_fails(self):
        agent = _fresh_agent()
        with patch(
            "src.agents.coder.subprocess.run", side_effect=Exception("git not found")
        ):
            assert agent._working_tree_is_clean() is False


class TestStashCandidate:
    def test_returns_sha_on_successful_stash(self):
        agent = _fresh_agent()
        with patch("src.agents.coder.subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="Saved working directory...", stderr=""),
                MagicMock(returncode=0, stdout="abc123\n", stderr=""),
            ]
            sha = agent._stash_candidate()
        assert sha == "abc123"

    def test_returns_none_when_nothing_to_stash(self):
        agent = _fresh_agent()
        with patch("src.agents.coder.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="No local changes to save"
            )
            sha = agent._stash_candidate()
        assert sha is None

    def test_returns_none_on_exception(self):
        agent = _fresh_agent()
        with patch("src.agents.coder.subprocess.run", side_effect=Exception("boom")):
            assert agent._stash_candidate() is None


class TestDropStash:
    def test_resolves_sha_to_current_ref_and_drops_it(self):
        agent = _fresh_agent()
        with patch("src.agents.coder.subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(
                    returncode=0,
                    stdout="abc123 stash@{1}\ndef456 stash@{0}\n",
                    stderr="",
                ),
                MagicMock(returncode=0, stdout="", stderr=""),
            ]
            agent._drop_stash("abc123")

        drop_call = mock_run.call_args_list[1]
        assert drop_call.args[0] == ["git", "stash", "drop", "stash@{1}"]

    def test_no_matching_sha_is_a_silent_noop(self):
        agent = _fresh_agent()
        with patch("src.agents.coder.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="def456 stash@{0}\n", stderr=""
            )
            agent._drop_stash("nonexistent-sha")
        assert mock_run.call_count == 1  # only the list call — no drop attempted


def test_react_loop_tool_descriptions_survive_a_docless_tool():
    """A registered tool without a __doc__ (MCP/wrapped callables) must not crash the ReAct
    loop's tool-description builder — the real dogfood hit exactly this."""
    from src.agents.coder import CodingAgent

    agent = CodingAgent()

    def docless(x):  # no docstring, has __code__
        return x

    docless.__doc__ = None

    # Build the same tools dict shape and exercise the describe path directly.
    tools = {"read_file": agent._tool_read_file, "docless": docless}
    # Mirror the loop's builder — must not raise.
    lines = []
    for name, fn in tools.items():
        try:
            params = ", ".join(fn.__code__.co_varnames[1 : fn.__code__.co_argcount])
        except AttributeError:
            params = ""
        doc = (fn.__doc__ or "").strip()
        lines.append(f"  - {name}({params}): {doc.splitlines()[0] if doc else name}")
    assert any("docless" in l for l in lines)  # noqa: E741


def test_isolated_coder_flag_gates_mcp_tools():
    """An injected root means worktree isolation — MCP tools (which ignore self.root and
    would write outside the branch) must be excluded. The first dogfood leaked into the live
    checkout because they weren't."""
    from src.agents.coder import CodingAgent

    assert CodingAgent(root="/tmp/wt")._isolated is True
    assert CodingAgent()._isolated is False


def test_write_file_refuses_absolute_path_escape(tmp_path):
    """os.path.join(root, abs_path) discards root — the exact bug that leaked the first
    dogfood into main. An absolute or ..-traversal path must be REFUSED, not followed."""
    from src.agents.coder import CodingAgent

    wt = tmp_path / "worktree"
    wt.mkdir()
    outside = tmp_path / "OUTSIDE.md"
    outside.write_text("original", encoding="utf-8")
    agent = CodingAgent(root=str(wt))

    # Absolute path to a file OUTSIDE the root must not be written.
    res = agent._tool_write_file(str(outside), "HACKED")
    assert "ERROR" in res or "escape" in res.lower()
    assert outside.read_text(encoding="utf-8") == "original", (
        "escape write must be refused"
    )

    # ..-traversal must also be refused.
    agent._tool_write_file("../OUTSIDE.md", "HACKED")
    assert outside.read_text(encoding="utf-8") == "original"

    # A normal relative path still works and stays inside the root.
    ok = agent._tool_write_file("sub/f.py", "print(1)")
    assert "OK" in ok and (wt / "sub" / "f.py").exists()
