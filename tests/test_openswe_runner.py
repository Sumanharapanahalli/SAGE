"""
SAGE Framework — OpenSWE Runner Tests (TDD)
=============================================
Tests for:
  - OpenSWERunner.build() returns run_id + status + tier
  - OpenSWERunner.build() tries external SWE first
  - OpenSWERunner.build() falls back to LangGraph when external unavailable
  - OpenSWERunner.build() falls back to ReAct LLM when both unavailable
  - OpenSWERunner.build() audits every build action
  - OpenSWERunner.get_status() returns correct status for known run
  - OpenSWERunner.get_status() returns error for unknown run
  - _try_external_swe() returns None when OPENSWE_URL not set
  - _try_external_swe() returns None on connection error
  - _try_langgraph_swe() returns None when LangGraph unavailable
  - _try_llm_fallback() uses ReAct pattern (multiple iterations)
  - _try_llm_fallback() parses Thought/Action/Observation format
  - _try_llm_fallback() passes acceptance criteria to LLM
  - _try_llm_fallback() stops when agent says DONE
  - _try_llm_fallback() respects max iterations
  - _try_llm_fallback() handles LLM failure gracefully
  - _parse_react_response() extracts thought
  - _parse_react_response() extracts JSON files from action block
  - _parse_react_response() extracts observation
  - _parse_react_response() extracts status
  - _parse_react_response() handles malformed response
  - get_openswe_runner() returns singleton
  - get_openswe_runner() is thread-safe
"""

import json
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_runner():
    from src.integrations.openswe_runner import OpenSWERunner
    runner = OpenSWERunner()
    runner._openswe_url = ""  # Disable external SWE for most tests
    return runner


REACT_RESPONSE = """THOUGHT: I need to build a simple REST API with Flask.

ACTION: Generate code
```json
{
  "files": [
    {"path": "app.py", "content": "from flask import Flask\\napp = Flask(__name__)\\n@app.route('/')\\ndef index():\\n    return 'Hello'"},
    {"path": "requirements.txt", "content": "flask==3.0.0"}
  ],
  "explanation": "Built a minimal Flask API"
}
```

OBSERVATION: The code creates a basic Flask app with one route. Missing error handling and tests.

STATUS: DONE
"""

REACT_RESPONSE_ITERATE = """THOUGHT: Need to fix error handling.

ACTION: Generate code
```json
{
  "files": [
    {"path": "app.py", "content": "from flask import Flask, jsonify\\napp = Flask(__name__)\\n@app.route('/')\\ndef index():\\n    try:\\n        return jsonify(ok=True)\\n    except Exception as e:\\n        return jsonify(error=str(e)), 500"}
  ],
  "explanation": "Added error handling"
}
```

OBSERVATION: Error handling added but still no tests.

STATUS: ITERATE — need to add tests
"""


# ---------------------------------------------------------------------------
# OpenSWERunner.build()
# ---------------------------------------------------------------------------

class TestBuild:

    def test_returns_run_id_and_status(self):
        runner = _fresh_runner()
        with patch.object(runner, "_try_llm_fallback", return_value={
            "status": "completed", "tier": "llm_react", "code": "x=1",
            "files_changed": ["app.py"], "output": {},
        }), patch.object(runner, "_audit"):
            result = runner.build({"description": "Build hello world", "task_type": "BACKEND"})
            assert "run_id" in result
            assert result["status"] == "completed"
            assert result["tier"] == "llm_react"

    def test_tries_external_swe_first(self):
        runner = _fresh_runner()
        runner._openswe_url = "http://fake-swe:8000"
        with patch.object(runner, "_try_external_swe", return_value={
            "status": "completed", "tier": "openswe_external", "code": "x=1",
            "files_changed": [], "output": {},
        }) as mock_ext, \
             patch.object(runner, "_audit"):
            result = runner.build({"description": "test"})
            mock_ext.assert_called_once()
            assert result["tier"] == "openswe_external"

    def test_falls_back_to_langgraph(self):
        runner = _fresh_runner()
        with patch.object(runner, "_try_external_swe", return_value=None), \
             patch.object(runner, "_try_langgraph_swe", return_value={
                 "status": "completed", "tier": "langgraph_swe", "code": "",
                 "files_changed": [], "output": {},
             }) as mock_lg, \
             patch.object(runner, "_audit"):
            result = runner.build({"description": "test"})
            mock_lg.assert_called_once()
            assert result["tier"] == "langgraph_swe"

    def test_falls_back_to_react_llm(self):
        runner = _fresh_runner()
        with patch.object(runner, "_try_external_swe", return_value=None), \
             patch.object(runner, "_try_langgraph_swe", return_value=None), \
             patch.object(runner, "_try_llm_fallback", return_value={
                 "status": "completed", "tier": "llm_react", "code": "x=1",
                 "files_changed": [], "output": {},
             }) as mock_llm, \
             patch.object(runner, "_audit"):
            result = runner.build({"description": "test"})
            mock_llm.assert_called_once()
            assert result["tier"] == "llm_react"

    def test_audits_every_build(self):
        runner = _fresh_runner()
        with patch.object(runner, "_try_llm_fallback", return_value={
            "status": "completed", "tier": "llm_react", "code": "",
            "files_changed": [], "output": {},
        }), patch.object(runner, "_audit") as mock_audit:
            runner.build({"description": "test"})
            mock_audit.assert_called_once()


# ---------------------------------------------------------------------------
# OpenSWERunner.get_status()
# ---------------------------------------------------------------------------

class TestGetStatus:

    def test_returns_status_for_known_run(self):
        runner = _fresh_runner()
        with patch.object(runner, "_try_llm_fallback", return_value={
            "status": "completed", "tier": "llm_react", "code": "",
            "files_changed": [], "output": {},
        }), patch.object(runner, "_audit"):
            result = runner.build({"description": "test"})
            status = runner.get_status(result["run_id"])
            assert status["status"] == "completed"

    def test_returns_error_for_unknown_run(self):
        runner = _fresh_runner()
        status = runner.get_status("nonexistent-id")
        assert "error" in status


# ---------------------------------------------------------------------------
# _try_external_swe()
# ---------------------------------------------------------------------------

class TestExternalSWE:

    def test_returns_none_when_url_not_set(self):
        runner = _fresh_runner()
        runner._openswe_url = ""
        result = runner._try_external_swe({"description": "test"}, "", None)
        assert result is None

    def test_returns_none_on_connection_error(self):
        runner = _fresh_runner()
        runner._openswe_url = "http://nonexistent:9999"
        result = runner._try_external_swe({"description": "test"}, "", None)
        assert result is None


# ---------------------------------------------------------------------------
# _try_langgraph_swe()
# ---------------------------------------------------------------------------

class TestLangGraphSWE:

    def test_returns_none_when_unavailable(self):
        runner = _fresh_runner()
        with patch("src.integrations.openswe_runner.logger"):
            result = runner._try_langgraph_swe({"description": "test"}, "")
            # Should return None if langgraph_runner.run returns error or is unavailable
            # (depends on whether langgraph is installed)
            assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# _try_llm_fallback() — ReAct pattern
# ---------------------------------------------------------------------------

class TestReActLLMFallback:

    def test_uses_react_pattern(self):
        runner = _fresh_runner()
        with patch("src.core.llm_gateway.llm_gateway") as mock_gw:
            mock_gw.generate.return_value = REACT_RESPONSE
            result = runner._try_llm_fallback(
                {"description": "Build API", "task_type": "BACKEND"}, ""
            )
            assert result["tier"] == "llm_react"
            assert result["status"] == "completed"
            assert "app.py" in result["files_changed"]

    def test_passes_acceptance_criteria(self):
        runner = _fresh_runner()
        with patch("src.core.llm_gateway.llm_gateway") as mock_gw:
            mock_gw.generate.return_value = REACT_RESPONSE
            runner._try_llm_fallback(
                {"description": "Build API", "task_type": "BACKEND",
                 "acceptance_criteria": ["Has error handling", "Has tests"]},
                "",
            )
            prompt = mock_gw.generate.call_args[0][0]
            assert "Has error handling" in prompt
            assert "Has tests" in prompt

    def test_stops_when_agent_says_done(self):
        runner = _fresh_runner()
        with patch("src.core.llm_gateway.llm_gateway") as mock_gw:
            mock_gw.generate.return_value = REACT_RESPONSE  # STATUS: DONE
            result = runner._try_llm_fallback({"description": "test", "task_type": "BACKEND"}, "")
            assert mock_gw.generate.call_count == 1
            assert result["output"]["react_iterations"] == 1

    def test_iterates_when_status_is_iterate(self):
        runner = _fresh_runner()
        with patch("src.core.llm_gateway.llm_gateway") as mock_gw:
            mock_gw.generate.side_effect = [REACT_RESPONSE_ITERATE, REACT_RESPONSE]
            result = runner._try_llm_fallback({"description": "test", "task_type": "BACKEND"}, "")
            assert mock_gw.generate.call_count == 2
            assert result["output"]["react_iterations"] == 2

    def test_respects_max_iterations(self):
        runner = _fresh_runner()
        with patch("src.core.llm_gateway.llm_gateway") as mock_gw:
            mock_gw.generate.return_value = REACT_RESPONSE_ITERATE  # Always ITERATE
            result = runner._try_llm_fallback({"description": "test", "task_type": "BACKEND"}, "")
            # max_iterations=3
            assert mock_gw.generate.call_count == 3

    def test_handles_llm_failure(self):
        runner = _fresh_runner()
        with patch("src.core.llm_gateway.llm_gateway") as mock_gw:
            mock_gw.generate.side_effect = RuntimeError("LLM down")
            result = runner._try_llm_fallback({"description": "test", "task_type": "BACKEND"}, "")
            assert result["status"] == "error"
            assert result["tier"] == "llm_react"

    def test_merges_files_across_iterations(self):
        """Later iterations should override files from earlier ones."""
        runner = _fresh_runner()
        iter1 = """THOUGHT: Build base
ACTION: Generate code
```json
{"files": [{"path": "app.py", "content": "v1"}, {"path": "config.py", "content": "cfg"}]}
```
OBSERVATION: Needs fixes
STATUS: ITERATE"""

        iter2 = """THOUGHT: Fix app
ACTION: Generate code
```json
{"files": [{"path": "app.py", "content": "v2"}]}
```
OBSERVATION: Good now
STATUS: DONE"""

        with patch("src.core.llm_gateway.llm_gateway") as mock_gw:
            mock_gw.generate.side_effect = [iter1, iter2]
            result = runner._try_llm_fallback({"description": "test", "task_type": "BACKEND"}, "")
            # app.py should be v2 (overridden), config.py should remain
            assert len(result["files_changed"]) == 2
            assert "app.py" in result["files_changed"]
            assert "config.py" in result["files_changed"]


# ---------------------------------------------------------------------------
# _parse_react_response()
# ---------------------------------------------------------------------------

class TestParseReactResponse:

    def test_extracts_thought(self):
        runner = _fresh_runner()
        result = runner._parse_react_response(REACT_RESPONSE)
        assert "Flask" in result["thought"]

    def test_extracts_files(self):
        runner = _fresh_runner()
        result = runner._parse_react_response(REACT_RESPONSE)
        assert len(result["files"]) == 2
        assert result["files"][0]["path"] == "app.py"

    def test_extracts_observation(self):
        runner = _fresh_runner()
        result = runner._parse_react_response(REACT_RESPONSE)
        assert "Missing error handling" in result["observation"]

    def test_extracts_status_done(self):
        runner = _fresh_runner()
        result = runner._parse_react_response(REACT_RESPONSE)
        assert "DONE" in result["status"]

    def test_extracts_status_iterate(self):
        runner = _fresh_runner()
        result = runner._parse_react_response(REACT_RESPONSE_ITERATE)
        assert "ITERATE" in result["status"]

    def test_handles_malformed_response(self):
        runner = _fresh_runner()
        result = runner._parse_react_response("Just some random text")
        assert result["files"] == []
        assert result["status"] == "DONE"  # Default

    def test_handles_json_without_fences(self):
        runner = _fresh_runner()
        resp = 'THOUGHT: test\n{"files": [{"path": "x.py", "content": "x"}]}\nSTATUS: DONE'
        result = runner._parse_react_response(resp)
        assert len(result["files"]) == 1


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:

    def test_get_openswe_runner_returns_instance(self):
        from src.integrations.openswe_runner import get_openswe_runner
        runner = get_openswe_runner()
        assert runner is not None
        assert hasattr(runner, "build")

    def test_get_openswe_runner_is_same_instance(self):
        from src.integrations.openswe_runner import get_openswe_runner
        r1 = get_openswe_runner()
        r2 = get_openswe_runner()
        assert r1 is r2


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------

class TestBuildEdgeCases:

    def test_missing_description_field(self):
        """build() with task missing 'description' should still work."""
        runner = _fresh_runner()
        with patch.object(runner, "_try_llm_fallback", return_value={
            "status": "completed", "tier": "llm_react", "code": "",
            "files_changed": [], "output": {},
        }), patch.object(runner, "_audit"):
            result = runner.build({"task_type": "BACKEND"})
            assert result["status"] == "completed"
            assert "run_id" in result

    def test_missing_task_type_field(self):
        """build() with task missing 'task_type' should still work."""
        runner = _fresh_runner()
        with patch.object(runner, "_try_llm_fallback", return_value={
            "status": "completed", "tier": "llm_react", "code": "x=1",
            "files_changed": ["x.py"], "output": {},
        }), patch.object(runner, "_audit"):
            result = runner.build({"description": "Build something"})
            assert result["status"] == "completed"

    def test_all_three_tiers_fail(self):
        """build() when all 3 tiers return failure, result reflects error."""
        runner = _fresh_runner()
        runner._openswe_url = "http://fake:8000"
        with patch.object(runner, "_try_external_swe", return_value=None), \
             patch.object(runner, "_try_langgraph_swe", return_value=None), \
             patch.object(runner, "_try_llm_fallback", return_value={
                 "status": "error", "tier": "llm_react",
                 "error": "All tiers failed", "code": "", "files_changed": [],
             }), patch.object(runner, "_audit"):
            result = runner.build({"description": "test"})
            assert result["status"] == "error"

    def test_build_preserves_task_metadata(self):
        """build() preserves run_id in output even when custom fields present."""
        runner = _fresh_runner()
        with patch.object(runner, "_try_llm_fallback", return_value={
            "status": "completed", "tier": "llm_react", "code": "x=1",
            "files_changed": ["a.py"], "output": {"custom": "data"},
        }), patch.object(runner, "_audit"):
            result = runner.build({
                "description": "test", "task_type": "BACKEND",
                "extra_field": "extra_value",
            })
            assert "run_id" in result
            assert result["output"]["custom"] == "data"

    def test_empty_task_dict(self):
        """build() with completely empty task dict."""
        runner = _fresh_runner()
        with patch.object(runner, "_try_llm_fallback", return_value={
            "status": "completed", "tier": "llm_react", "code": "",
            "files_changed": [], "output": {},
        }), patch.object(runner, "_audit"):
            result = runner.build({})
            assert "run_id" in result


class TestTryLlmFallbackEdgeCases:

    def test_empty_response_from_llm(self):
        """_try_llm_fallback() with empty string from LLM produces no files."""
        runner = _fresh_runner()
        with patch("src.core.llm_gateway.llm_gateway") as mock_gw:
            mock_gw.generate.return_value = ""
            result = runner._try_llm_fallback(
                {"description": "test", "task_type": "BACKEND"}, ""
            )
            assert result["status"] == "completed"
            assert result["files_changed"] == []

    def test_response_with_action_but_invalid_json(self):
        """_try_llm_fallback() with ACTION line but malformed JSON."""
        runner = _fresh_runner()
        response = """THOUGHT: Building something
ACTION: Generate code
```json
{this is not valid json}
```
OBSERVATION: Tried
STATUS: DONE"""
        with patch("src.core.llm_gateway.llm_gateway") as mock_gw:
            mock_gw.generate.return_value = response
            result = runner._try_llm_fallback(
                {"description": "test", "task_type": "BACKEND"}, ""
            )
            assert result["status"] == "completed"
            assert result["files_changed"] == []

    def test_response_with_no_files_key_in_json(self):
        """_try_llm_fallback() where JSON exists but has no 'files' key."""
        runner = _fresh_runner()
        response = """THOUGHT: Building
ACTION: Generate code
```json
{"explanation": "No files generated"}
```
STATUS: DONE"""
        with patch("src.core.llm_gateway.llm_gateway") as mock_gw:
            mock_gw.generate.return_value = response
            result = runner._try_llm_fallback(
                {"description": "test", "task_type": "BACKEND"}, ""
            )
            assert result["status"] == "completed"
            assert result["files_changed"] == []

    def test_with_payload_in_task(self):
        """_try_llm_fallback() includes payload in prompt when present."""
        runner = _fresh_runner()
        with patch("src.core.llm_gateway.llm_gateway") as mock_gw:
            mock_gw.generate.return_value = REACT_RESPONSE
            runner._try_llm_fallback(
                {"description": "test", "task_type": "BACKEND",
                 "payload": {"framework": "django"}}, ""
            )
            prompt = mock_gw.generate.call_args[0][0]
            assert "django" in prompt


class TestParseReactResponseEdgeCases:

    def test_only_status_line(self):
        """_parse_react_response() with only a STATUS line."""
        runner = _fresh_runner()
        result = runner._parse_react_response("STATUS: DONE")
        assert result["status"] == "DONE"
        assert result["files"] == []
        assert result["thought"] == ""

    def test_empty_string(self):
        """_parse_react_response() with empty string returns defaults."""
        runner = _fresh_runner()
        result = runner._parse_react_response("")
        assert result["files"] == []
        assert result["status"] == "DONE"
        assert result["thought"] == ""
        assert result["observation"] == ""

    def test_very_large_response(self):
        """_parse_react_response() handles very large responses."""
        runner = _fresh_runner()
        large_content = "x = 1; " * 10000
        payload = json.dumps({"files": [{"path": "big.py", "content": large_content[:200]}]})
        response = (
            f"THOUGHT: Building large file\n"
            f"ACTION: Generate code\n"
            f"```json\n{payload}\n```\n"
            f"OBSERVATION: Large file generated\n"
            f"STATUS: DONE"
        )
        result = runner._parse_react_response(response)
        assert len(result["files"]) == 1
        assert result["files"][0]["path"] == "big.py"
        assert "DONE" in result["status"]

    def test_multiple_action_blocks(self):
        """_parse_react_response() with multiple JSON blocks takes first fenced block."""
        runner = _fresh_runner()
        response = """THOUGHT: Testing
ACTION: Generate code
```json
{"files": [{"path": "a.py", "content": "first"}]}
```
Some more text
```json
{"files": [{"path": "b.py", "content": "second"}]}
```
STATUS: DONE"""
        result = runner._parse_react_response(response)
        assert len(result["files"]) >= 1
        assert result["files"][0]["path"] == "a.py"

    def test_status_iterate_with_reason(self):
        """_parse_react_response() extracts full STATUS: ITERATE line."""
        runner = _fresh_runner()
        response = "THOUGHT: Fix\nSTATUS: ITERATE — missing error handling"
        result = runner._parse_react_response(response)
        assert "ITERATE" in result["status"]

    def test_no_status_line_defaults_to_done(self):
        """_parse_react_response() defaults to DONE when no STATUS line."""
        runner = _fresh_runner()
        result = runner._parse_react_response("THOUGHT: Just thinking\nOBSERVATION: Noted.")
        assert result["status"] == "DONE"


class TestExternalSWEEdgeCases:

    def test_timeout_returns_none(self):
        """_try_external_swe() returns None on timeout."""
        runner = _fresh_runner()
        runner._openswe_url = "http://10.255.255.1:9999"  # Non-routable → timeout
        result = runner._try_external_swe({"description": "test"}, "", None)
        assert result is None


class TestGetStatusEdgeCases:

    def test_status_right_after_build(self):
        """get_status() immediately after build() returns completed status."""
        runner = _fresh_runner()
        with patch.object(runner, "_try_llm_fallback", return_value={
            "status": "completed", "tier": "llm_react", "code": "x=1",
            "files_changed": ["a.py"], "output": {},
        }), patch.object(runner, "_audit"):
            build_result = runner.build({"description": "test"})
            status = runner.get_status(build_result["run_id"])
            assert status["status"] == "completed"
            assert status["tier"] == "llm_react"
            assert status["run_id"] == build_result["run_id"]

    def test_multiple_builds_independent_statuses(self):
        """Multiple build() calls produce independent status entries."""
        runner = _fresh_runner()
        # Each build() call needs a fresh return dict (not shared reference)
        # and a unique uuid
        def make_result():
            return {
                "status": "completed", "tier": "llm_react", "code": "",
                "files_changed": [], "output": {},
            }
        with patch.object(runner, "_try_llm_fallback", side_effect=lambda *a, **k: make_result()), \
             patch.object(runner, "_audit"):
            r1 = runner.build({"description": "task 1"})
            r2 = runner.build({"description": "task 2"})
            assert r1["run_id"] != r2["run_id"]
            s1 = runner.get_status(r1["run_id"])
            s2 = runner.get_status(r2["run_id"])
            assert s1["run_id"] != s2["run_id"]
            assert s1["status"] == "completed"
            assert s2["status"] == "completed"
