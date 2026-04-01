"""
SAGE Framework — 3-Tier Execution Cascade Tests
==================================================
Tests for the OpenShell → SandboxRunner → OpenSWE isolation cascade
in the build orchestrator.

Groups:
  1. Individual tier verification (8 tests)
  2. Cascade fallback logic (6 tests)
  3. Tier 1 (OpenShell) internals (5 tests)
  4. Tier 2 (SandboxRunner) internals (6 tests)
  5. Task enrichment (5 tests)
  6. Security policy generation (6 tests)
  7. Security / injection testing (6 tests)
  8. Wave executor integration (7 tests)
  9. Edge cases (6 tests)
 10. Integration with real temp dirs (4 tests)
"""

import os
import shutil
import tempfile
import threading
from contextlib import contextmanager
from unittest.mock import MagicMock, patch, call

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers & constants
# ---------------------------------------------------------------------------

def _fresh_orchestrator():
    from src.integrations.build_orchestrator import BuildOrchestrator
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return BuildOrchestrator(checkpoint_db=tmp.name)


MOCK_BUILD_RESULT = {
    "status": "completed", "tier": "llm_react", "code": "x=1",
    "files_changed": ["app.py"], "output": {},
}

MOCK_TASK = {
    "step": 1, "task_type": "backend_api", "description": "Build REST API",
    "payload": {}, "depends_on": [], "agent_role": "developer",
}

MOCK_RUN = {
    "workspace_dir": "/tmp/sage-test-workspace",
    "plan": [MOCK_TASK],
    "agent_results": [],
    "_prior_wave_context": "",
    "detected_domains": [],
}


def _mock_openshell(available=True, sandbox_yields=True, raises=False):
    """Create a mock OpenShellRunner."""
    mock = MagicMock()
    mock.is_available.return_value = available

    @contextmanager
    def _sb(name, policy=None):
        if raises:
            raise RuntimeError("OpenShell sandbox creation failed")
        if sandbox_yields:
            handle = MagicMock()
            handle.name = name
            yield handle
        else:
            yield None

    mock.sandbox = MagicMock(side_effect=_sb)
    return mock


def _mock_openswe(result=None, raises=False):
    """Create a mock OpenSWERunner."""
    mock = MagicMock()
    if raises:
        mock.build.side_effect = RuntimeError("OpenSWE build failed")
    else:
        mock.build.return_value = dict(result or MOCK_BUILD_RESULT)
    return mock


def _mock_local_sandbox(clone_ok=True, diff_output=""):
    """Create a mock SandboxRunner."""
    mock = MagicMock()
    mock.clone_repo.return_value = {"success": clone_ok, "error": None if clone_ok else "clone failed"}
    mock.execute.return_value = {"success": True, "stdout": "", "stderr": "", "returncode": 0}
    mock.get_diff.return_value = {"success": bool(diff_output), "stdout": diff_output}
    return mock


# ---------------------------------------------------------------------------
# Group 1: Individual Tier Verification
# ---------------------------------------------------------------------------

class TestRouteToAgentCascade:

    def test_tier1_openshell_used_when_available(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        openshell = _mock_openshell(available=True, sandbox_yields=True)

        with patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.return_value = "developer"
            result = orch._route_to_agent(
                MOCK_TASK, "developer", openswe, MOCK_RUN,
                openshell=openshell, local_sandbox=None,
            )

        assert result["execution_tier"] == "openshell"
        # OpenSWE was called with a sandbox_handle
        openswe.build.assert_called_once()
        _, kwargs = openswe.build.call_args
        assert kwargs.get("sandbox_handle") is not None

    def test_tier1_yields_none_falls_to_tier2(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        openshell = _mock_openshell(available=True, sandbox_yields=False)
        local_sandbox = _mock_local_sandbox()
        run = {**MOCK_RUN, "workspace_dir": tempfile.mkdtemp()}

        try:
            with patch("src.integrations.build_orchestrator.adaptive_router") as ar:
                ar.route.return_value = "developer"
                result = orch._route_to_agent(
                    MOCK_TASK, "developer", openswe, run,
                    openshell=openshell, local_sandbox=local_sandbox,
                )
            assert result["execution_tier"] == "sandbox_runner"
        finally:
            shutil.rmtree(run["workspace_dir"], ignore_errors=True)

    def test_tier2_sandbox_runner_used_when_workspace_exists(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        local_sandbox = _mock_local_sandbox()
        run = {**MOCK_RUN, "workspace_dir": tempfile.mkdtemp()}

        try:
            with patch("src.integrations.build_orchestrator.adaptive_router") as ar:
                ar.route.return_value = "developer"
                result = orch._route_to_agent(
                    MOCK_TASK, "developer", openswe, run,
                    openshell=None, local_sandbox=local_sandbox,
                )
            assert result["execution_tier"] == "sandbox_runner"
        finally:
            shutil.rmtree(run["workspace_dir"], ignore_errors=True)

    def test_tier2_skipped_when_no_workspace(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        local_sandbox = _mock_local_sandbox()

        with patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.return_value = "developer"
            result = orch._route_to_agent(
                MOCK_TASK, "developer", openswe, {**MOCK_RUN, "workspace_dir": ""},
                openshell=None, local_sandbox=local_sandbox,
            )
        # Falls to Tier 3 — no execution_tier tag from direct openswe call
        assert result["status"] == "completed"
        openswe.build.assert_called_once()

    def test_tier2_skipped_when_no_local_sandbox(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()

        with patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.return_value = "developer"
            result = orch._route_to_agent(
                MOCK_TASK, "developer", openswe, MOCK_RUN,
                openshell=None, local_sandbox=None,
            )
        assert result["status"] == "completed"
        openswe.build.assert_called_once()

    def test_tier3_openswe_always_used_as_fallback(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()

        with patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.return_value = "developer"
            result = orch._route_to_agent(
                MOCK_TASK, "developer", openswe, MOCK_RUN,
                openshell=None, local_sandbox=None,
            )
        openswe.build.assert_called_once()
        assert result["status"] == "completed"

    def test_adaptive_router_override_applied(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()

        with patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.return_value = "analyst"  # Override from developer → analyst
            result = orch._route_to_agent(
                MOCK_TASK, "developer", openswe, MOCK_RUN,
                openshell=None, local_sandbox=None,
            )
        ar.route.assert_called_once_with("backend_api")
        assert result["status"] == "completed"

    def test_task_enrichment_passed_to_all_tiers(self):
        orch = _fresh_orchestrator()
        task = {**MOCK_TASK, "acceptance_criteria": ["Must return JSON", "Must validate"]}
        openswe = _mock_openswe()

        with patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.return_value = "developer"
            orch._route_to_agent(
                task, "developer", openswe, MOCK_RUN,
                openshell=None, local_sandbox=None,
            )
        called_task = openswe.build.call_args[1]["task"]
        assert "Must return JSON" in called_task["description"]
        assert "Must validate" in called_task["description"]


# ---------------------------------------------------------------------------
# Group 2: Cascade Fallback Logic
# ---------------------------------------------------------------------------

class TestCascadeFallback:

    def test_tier1_exception_falls_to_tier2(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        openshell = _mock_openshell(available=True, raises=True)
        local_sandbox = _mock_local_sandbox()
        run = {**MOCK_RUN, "workspace_dir": tempfile.mkdtemp()}

        try:
            with patch("src.integrations.build_orchestrator.adaptive_router") as ar:
                ar.route.return_value = "developer"
                result = orch._route_to_agent(
                    MOCK_TASK, "developer", openswe, run,
                    openshell=openshell, local_sandbox=local_sandbox,
                )
            assert result["execution_tier"] == "sandbox_runner"
        finally:
            shutil.rmtree(run["workspace_dir"], ignore_errors=True)

    def test_tier1_fails_tier2_fails_falls_to_tier3(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        openshell = _mock_openshell(available=True, raises=True)

        with patch("src.integrations.build_orchestrator.adaptive_router") as ar, \
             patch.object(orch, "_try_sandbox_runner", return_value=None):
            ar.route.return_value = "developer"
            result = orch._route_to_agent(
                MOCK_TASK, "developer", openswe, MOCK_RUN,
                openshell=openshell, local_sandbox=_mock_local_sandbox(),
            )
        # Falls to Tier 3
        assert result["status"] == "completed"

    def test_tier2_clone_failure_falls_to_tier3(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        local_sandbox = _mock_local_sandbox(clone_ok=False)
        # Workspace is a URL, not a directory → triggers clone path
        run = {**MOCK_RUN, "workspace_dir": "https://github.com/fake/repo.git"}

        with patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.return_value = "developer"
            result = orch._route_to_agent(
                MOCK_TASK, "developer", openswe, run,
                openshell=None, local_sandbox=local_sandbox,
            )
        # Tier 2 clone failed → Tier 3
        assert result["status"] == "completed"

    def test_tier2_openswe_exception_falls_to_tier3(self):
        orch = _fresh_orchestrator()
        # First call (inside _try_sandbox_runner) raises, second (Tier 3) succeeds
        openswe = MagicMock()
        openswe.build.side_effect = [
            RuntimeError("sandbox openswe failed"),
            dict(MOCK_BUILD_RESULT),
        ]
        local_sandbox = _mock_local_sandbox()
        run = {**MOCK_RUN, "workspace_dir": tempfile.mkdtemp()}

        try:
            with patch("src.integrations.build_orchestrator.adaptive_router") as ar:
                ar.route.return_value = "developer"
                result = orch._route_to_agent(
                    MOCK_TASK, "developer", openswe, run,
                    openshell=None, local_sandbox=local_sandbox,
                )
            # Tier 2 failed (openswe raised), fell to Tier 3
            assert result["status"] == "completed"
            assert openswe.build.call_count == 2
        finally:
            shutil.rmtree(run["workspace_dir"], ignore_errors=True)

    def test_all_tiers_fail_returns_error(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe(result={"status": "error", "output": "LLM failed"})
        openshell = _mock_openshell(available=True, raises=True)

        with patch("src.integrations.build_orchestrator.adaptive_router") as ar, \
             patch.object(orch, "_try_sandbox_runner", return_value=None):
            ar.route.return_value = "developer"
            result = orch._route_to_agent(
                MOCK_TASK, "developer", openswe, MOCK_RUN,
                openshell=openshell, local_sandbox=_mock_local_sandbox(),
            )
        assert result["status"] == "error"

    def test_cascade_order_is_1_2_3(self):
        orch = _fresh_orchestrator()
        call_order = []

        orig_try_openshell = orch._try_openshell
        orig_try_sandbox = orch._try_sandbox_runner

        def track_openshell(*args, **kwargs):
            call_order.append("tier1")
            return None  # Force fallthrough

        def track_sandbox(*args, **kwargs):
            call_order.append("tier2")
            return None  # Force fallthrough

        openswe = _mock_openswe()

        with patch.object(orch, "_try_openshell", side_effect=track_openshell), \
             patch.object(orch, "_try_sandbox_runner", side_effect=track_sandbox), \
             patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.return_value = "developer"
            result = orch._route_to_agent(
                MOCK_TASK, "developer", openswe, MOCK_RUN,
                openshell=_mock_openshell(), local_sandbox=_mock_local_sandbox(),
            )

        assert call_order == ["tier1", "tier2"]
        openswe.build.assert_called_once()  # Tier 3


# ---------------------------------------------------------------------------
# Group 3: Tier 1 (OpenShell) Internals
# ---------------------------------------------------------------------------

class TestTryOpenshell:

    def test_sandbox_name_contains_task_type(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        openshell = _mock_openshell()

        orch._try_openshell(MOCK_TASK, "/tmp/workspace", openshell, openswe)

        sandbox_call = openshell.sandbox.call_args
        name = sandbox_call[0][0]  # First positional arg
        assert "backend_api" in name

    def test_policy_passed_to_sandbox(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        openshell = _mock_openshell()

        orch._try_openshell(MOCK_TASK, "/tmp/workspace", openshell, openswe)

        sandbox_call = openshell.sandbox.call_args
        policy = sandbox_call[0][1]  # Second positional arg
        assert "filesystem_policy" in policy
        assert "network_policies" in policy

    def test_openswe_receives_sandbox_handle(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        openshell = _mock_openshell()

        orch._try_openshell(MOCK_TASK, "/tmp/workspace", openshell, openswe)

        _, kwargs = openswe.build.call_args
        assert kwargs["sandbox_handle"] is not None

    def test_execution_tier_tagged_openshell(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        openshell = _mock_openshell()

        result = orch._try_openshell(MOCK_TASK, "/tmp/workspace", openshell, openswe)
        assert result["execution_tier"] == "openshell"

    def test_exception_returns_none(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        openshell = _mock_openshell(available=True, raises=True)

        result = orch._try_openshell(MOCK_TASK, "/tmp/workspace", openshell, openswe)
        assert result is None


# ---------------------------------------------------------------------------
# Group 4: Tier 2 (SandboxRunner) Internals
# ---------------------------------------------------------------------------

class TestTrySandboxRunner:

    def test_copies_workspace_directory(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        local_sandbox = _mock_local_sandbox()
        workspace = tempfile.mkdtemp()
        # Create a file so copytree has something
        with open(os.path.join(workspace, "test.py"), "w") as f:
            f.write("print('hello')")

        try:
            result = orch._try_sandbox_runner(MOCK_TASK, workspace, local_sandbox, openswe)
            assert result is not None
            assert result["execution_tier"] == "sandbox_runner"
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def test_creates_isolated_branch(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        local_sandbox = _mock_local_sandbox()
        workspace = tempfile.mkdtemp()

        try:
            orch._try_sandbox_runner(MOCK_TASK, workspace, local_sandbox, openswe)
            # Check that git checkout -b sage-build/... was called
            execute_calls = local_sandbox.execute.call_args_list
            branch_calls = [c for c in execute_calls
                            if "git checkout -b sage-build/" in str(c)]
            assert len(branch_calls) == 1
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def test_collects_diff_from_sandbox(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        local_sandbox = _mock_local_sandbox(diff_output="diff --git a/app.py")
        workspace = tempfile.mkdtemp()

        try:
            result = orch._try_sandbox_runner(MOCK_TASK, workspace, local_sandbox, openswe)
            assert "sandbox_diff" in result
            assert "diff --git" in result["sandbox_diff"]
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def test_cleanup_runs_on_exception(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe(raises=True)
        local_sandbox = _mock_local_sandbox()
        workspace = tempfile.mkdtemp()

        try:
            result = orch._try_sandbox_runner(MOCK_TASK, workspace, local_sandbox, openswe)
            # Should return None on exception (caught internally)
            assert result is None
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def test_non_directory_workspace_triggers_clone(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        local_sandbox = _mock_local_sandbox(clone_ok=False)

        result = orch._try_sandbox_runner(
            MOCK_TASK, "https://github.com/fake/repo.git", local_sandbox, openswe,
        )
        local_sandbox.clone_repo.assert_called_once()
        # Clone failed → returns None
        assert result is None

    def test_execution_tier_tagged_sandbox(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        local_sandbox = _mock_local_sandbox()
        workspace = tempfile.mkdtemp()

        try:
            result = orch._try_sandbox_runner(MOCK_TASK, workspace, local_sandbox, openswe)
            assert result["execution_tier"] == "sandbox_runner"
        finally:
            shutil.rmtree(workspace, ignore_errors=True)


# ---------------------------------------------------------------------------
# Group 5: Task Enrichment
# ---------------------------------------------------------------------------

class TestEnrichTask:

    def test_injects_prior_wave_context(self):
        orch = _fresh_orchestrator()
        run = {**MOCK_RUN, "_prior_wave_context": "Step 1 created DB schema with 3 tables"}
        result = orch._enrich_task(MOCK_TASK, run)
        assert "[Prior wave context]" in result["description"]
        assert "3 tables" in result["description"]

    def test_injects_acceptance_criteria(self):
        orch = _fresh_orchestrator()
        task = {**MOCK_TASK, "acceptance_criteria": ["Must return JSON", "Must validate input"]}
        result = orch._enrich_task(task, MOCK_RUN)
        assert "Must return JSON" in result["description"]
        assert "Must validate input" in result["description"]
        assert "Acceptance Criteria" in result["description"]

    def test_injects_artifact_type_info(self):
        orch = _fresh_orchestrator()
        from src.integrations.build_orchestrator import ARTIFACT_TYPES
        # Use a task type that has artifact info
        known_types = list(ARTIFACT_TYPES.keys())
        if known_types:
            task = {**MOCK_TASK, "task_type": known_types[0]}
            result = orch._enrich_task(task, MOCK_RUN)
            assert "Expected output:" in result["description"]

    def test_sets_payload_artifact_metadata(self):
        orch = _fresh_orchestrator()
        from src.integrations.build_orchestrator import ARTIFACT_TYPES
        known_types = list(ARTIFACT_TYPES.keys())
        if known_types:
            task = {**MOCK_TASK, "task_type": known_types[0]}
            result = orch._enrich_task(task, MOCK_RUN)
            assert "artifact_category" in result.get("payload", {})
            assert "expected_extensions" in result.get("payload", {})

    def test_prior_context_truncated_at_2000(self):
        orch = _fresh_orchestrator()
        long_context = "A" * 5000
        run = {**MOCK_RUN, "_prior_wave_context": long_context}
        result = orch._enrich_task(MOCK_TASK, run)
        # The injected context should be truncated
        context_portion = result["description"].split("[Prior wave context]\n")[1]
        assert len(context_portion) <= 2000


# ---------------------------------------------------------------------------
# Group 6: Security Policy Generation
# ---------------------------------------------------------------------------

class TestBuildSandboxPolicy:

    def test_base_policy_restricts_network(self):
        orch = _fresh_orchestrator()
        policy = orch._build_sandbox_policy({"task_type": "backend_api"})
        assert policy["network_policies"]["allow_outbound"] is False

    def test_base_policy_writable_paths(self):
        orch = _fresh_orchestrator()
        policy = orch._build_sandbox_policy({"task_type": "backend_api"})
        assert "/workspace" in policy["filesystem_policy"]["writable_paths"]
        assert "/tmp" in policy["filesystem_policy"]["writable_paths"]

    def test_base_policy_hidden_paths(self):
        orch = _fresh_orchestrator()
        policy = orch._build_sandbox_policy({"task_type": "backend_api"})
        assert "/root" in policy["filesystem_policy"]["hidden_paths"]
        assert "/home" in policy["filesystem_policy"]["hidden_paths"]

    def test_network_task_enables_outbound(self):
        orch = _fresh_orchestrator()
        for task_type in ["api_integration", "deployment", "ci_cd_pipeline"]:
            policy = orch._build_sandbox_policy({"task_type": task_type})
            assert policy["network_policies"]["allow_outbound"] is True, \
                f"{task_type} should allow outbound"

    def test_infra_task_adds_var_writable(self):
        orch = _fresh_orchestrator()
        for task_type in ["infrastructure", "database_setup", "monitoring_setup"]:
            policy = orch._build_sandbox_policy({"task_type": task_type})
            assert "/var" in policy["filesystem_policy"]["writable_paths"], \
                f"{task_type} should have /var writable"

    def test_deployment_gets_both_network_and_var(self):
        orch = _fresh_orchestrator()
        policy = orch._build_sandbox_policy({"task_type": "deployment"})
        assert policy["network_policies"]["allow_outbound"] is True
        assert "/var" in policy["filesystem_policy"]["writable_paths"]

    def test_firmware_task_gets_docker_image(self):
        orch = _fresh_orchestrator()
        policy = orch._build_sandbox_policy({
            "task_type": "FIRMWARE", "agent_role": "firmware_engineer",
        })
        assert "docker_image" in policy
        assert "firmware" in policy["docker_image"]
        assert "docker_packages" in policy
        assert "gcc-arm-none-eabi" in policy["docker_packages"]

    def test_pcb_task_gets_kicad_docker(self):
        orch = _fresh_orchestrator()
        policy = orch._build_sandbox_policy({
            "task_type": "PCB_DESIGN", "agent_role": "pcb_designer",
        })
        assert "docker_image" in policy
        assert "pcb" in policy["docker_image"]
        assert "kicad" in policy["docker_packages"]

    def test_software_task_has_no_docker_image(self):
        orch = _fresh_orchestrator()
        policy = orch._build_sandbox_policy({
            "task_type": "backend_api", "agent_role": "developer",
        })
        assert "docker_image" not in policy

    def test_resolve_docker_image_from_agent_role(self):
        orch = _fresh_orchestrator()
        img = orch._resolve_docker_image({"task_type": "FIRMWARE", "agent_role": "firmware_engineer"})
        assert img == "sage/firmware-toolchain:latest"

    def test_resolve_docker_image_from_task_type_fallback(self):
        orch = _fresh_orchestrator()
        # No agent_role set — falls back to TASK_TYPE_TO_AGENT mapping
        img = orch._resolve_docker_image({"task_type": "PCB_DESIGN"})
        assert img is not None
        assert "pcb" in img

    def test_resolve_docker_image_returns_none_for_software(self):
        orch = _fresh_orchestrator()
        img = orch._resolve_docker_image({"task_type": "BACKEND", "agent_role": "developer"})
        assert img is None


# ---------------------------------------------------------------------------
# Group 7: Security / Injection Testing
# ---------------------------------------------------------------------------

class TestSecurityInjection:

    def test_path_traversal_in_description_contained_by_policy(self):
        """Task description with path traversal — policy still restricts to /workspace."""
        orch = _fresh_orchestrator()
        malicious_task = {
            **MOCK_TASK,
            "description": "Build API at ../../../../etc/passwd; cat /etc/shadow",
        }
        policy = orch._build_sandbox_policy(malicious_task)
        # Policy is based on task_type, not description — still locked down
        assert policy["filesystem_policy"]["writable_paths"] == ["/workspace", "/tmp"]
        assert "/etc" not in policy["filesystem_policy"]["writable_paths"]

    def test_sandbox_name_sanitized_for_shell_injection(self):
        """Task type with shell metacharacters should be sanitized in sandbox name."""
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        openshell = _mock_openshell()

        malicious_task = {
            **MOCK_TASK,
            "task_type": "BACKEND;rm -rf /;echo pwned",
        }
        orch._try_openshell(malicious_task, "/tmp/workspace", openshell, openswe)

        sandbox_call = openshell.sandbox.call_args
        name = sandbox_call[0][0]
        # No semicolons, spaces, or shell metacharacters in name
        assert ";" not in name
        assert " " not in name
        assert "rm" not in name.split("-")  # rm might appear as substring of "framework" etc

    def test_policy_not_overridable_by_task_payload(self):
        """Malicious payload attempting to override policy should be ignored."""
        orch = _fresh_orchestrator()
        malicious_task = {
            **MOCK_TASK,
            "payload": {
                "filesystem_policy": {"writable_paths": ["/"]},
                "network_policies": {"allow_outbound": True},
            },
        }
        policy = orch._build_sandbox_policy(malicious_task)
        # Policy comes from _build_sandbox_policy, not from task payload
        assert policy["filesystem_policy"]["writable_paths"] == ["/workspace", "/tmp"]
        assert policy["network_policies"]["allow_outbound"] is False

    def test_oversized_description_does_not_crash(self):
        """Extremely large task description should not cause OOM or crash."""
        orch = _fresh_orchestrator()
        huge_task = {
            **MOCK_TASK,
            "description": "A" * 100_000,
            "acceptance_criteria": ["check"] * 1000,
        }
        # Should not raise
        enriched = orch._enrich_task(huge_task, MOCK_RUN)
        assert len(enriched["description"]) > 0

    def test_workspace_outside_tmp_handled_safely(self):
        """Workspace pointing to sensitive dir — Tier 2 still copies, doesn't modify original."""
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        local_sandbox = _mock_local_sandbox()
        # Use a real temp dir as "sensitive" workspace
        workspace = tempfile.mkdtemp()
        sentinel = os.path.join(workspace, "original.txt")
        with open(sentinel, "w") as f:
            f.write("DO NOT MODIFY")

        try:
            orch._try_sandbox_runner(MOCK_TASK, workspace, local_sandbox, openswe)
            # Original file untouched
            with open(sentinel) as f:
                assert f.read() == "DO NOT MODIFY"
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def test_null_bytes_in_task_type_handled(self):
        """Null bytes in task_type should not crash policy generation."""
        orch = _fresh_orchestrator()
        null_task = {**MOCK_TASK, "task_type": "backend\x00api"}
        # Should not raise
        policy = orch._build_sandbox_policy(null_task)
        assert "filesystem_policy" in policy


# ---------------------------------------------------------------------------
# Group 8: Wave Executor Integration
# ---------------------------------------------------------------------------

class TestExecuteAgentsWaves:

    def _setup_orch_for_execute(self, plan, openswe_result=None):
        """Set up orchestrator with a run ready for _execute_agents."""
        orch = _fresh_orchestrator()
        run_id = "test-run-001"
        run = {
            "run_id": run_id,
            "workspace_dir": tempfile.mkdtemp(),
            "plan": plan,
            "agent_results": [],
            "state": "building",
            "detected_domains": [],
            "_prior_wave_context": "",
            "hitl_level": "minimal",
        }
        orch._runs[run_id] = run
        return orch, run

    def _mock_route(self, orch, result=None, fail=False):
        """Patch _route_to_agent to return mock results without lazy imports."""
        if fail:
            r = {"status": "error", "code": "", "files_changed": [], "output": "failed"}
        else:
            r = result or dict(MOCK_BUILD_RESULT)
        return patch.object(orch, "_route_to_agent", return_value=r)

    def test_single_wave_all_independent(self):
        plan = [
            {"step": 1, "task_type": "BACKEND", "description": "API", "depends_on": [], "agent_role": "developer"},
            {"step": 2, "task_type": "FRONTEND", "description": "UI", "depends_on": [], "agent_role": "developer"},
            {"step": 3, "task_type": "TESTS", "description": "Tests", "depends_on": [], "agent_role": "developer"},
        ]
        orch, run = self._setup_orch_for_execute(plan)

        with self._mock_route(orch), \
             patch.object(orch, "_checkpoint"), \
             patch.object(orch, "_audit"), \
             patch.object(orch, "_summarize_context", return_value=""), \
             patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.side_effect = lambda tt: "developer"
            ar.record = MagicMock()
            orch._execute_agents(run)

        results = run["agent_results"]
        assert len(results) == 3
        waves = {r["wave"] for r in results}
        assert waves == {0}

        shutil.rmtree(run["workspace_dir"], ignore_errors=True)

    def test_dependency_failure_propagation(self):
        plan = [
            {"step": 1, "task_type": "BACKEND", "description": "API", "depends_on": [], "agent_role": "developer"},
            {"step": 2, "task_type": "FRONTEND", "description": "UI", "depends_on": [1], "agent_role": "developer"},
        ]
        orch, run = self._setup_orch_for_execute(plan)

        with self._mock_route(orch, fail=True), \
             patch.object(orch, "_checkpoint"), \
             patch.object(orch, "_audit"), \
             patch.object(orch, "_summarize_context", return_value=""), \
             patch.object(orch, "_check_drift", return_value=False), \
             patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.side_effect = lambda tt: "developer"
            ar.record = MagicMock()
            orch._execute_agents(run)

        results = run["agent_results"]
        blocked = [r for r in results if r.get("result", {}).get("status") == "blocked"]
        assert len(blocked) >= 1
        assert blocked[0]["result"]["reason"] == "dependency_failed"

        shutil.rmtree(run["workspace_dir"], ignore_errors=True)

    def test_empty_plan_returns_no_results(self):
        orch, run = self._setup_orch_for_execute([])

        with self._mock_route(orch), \
             patch.object(orch, "_checkpoint"), \
             patch.object(orch, "_audit"):
            orch._execute_agents(run)

        assert run["agent_results"] == []
        shutil.rmtree(run["workspace_dir"], ignore_errors=True)

    def test_multi_wave_sequential_execution(self):
        plan = [
            {"step": 1, "task_type": "DATABASE", "description": "Schema", "depends_on": [], "agent_role": "developer"},
            {"step": 2, "task_type": "BACKEND", "description": "API", "depends_on": [1], "agent_role": "developer"},
            {"step": 3, "task_type": "FRONTEND", "description": "UI", "depends_on": [2], "agent_role": "developer"},
        ]
        orch, run = self._setup_orch_for_execute(plan)

        with self._mock_route(orch), \
             patch.object(orch, "_checkpoint"), \
             patch.object(orch, "_audit"), \
             patch.object(orch, "_summarize_context", return_value=""), \
             patch.object(orch, "_check_drift", return_value=True), \
             patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.side_effect = lambda tt: "developer"
            ar.record = MagicMock()
            orch._execute_agents(run)

        results = run["agent_results"]
        waves = [r["wave"] for r in results]
        assert sorted(set(waves)) == [0, 1, 2]

        shutil.rmtree(run["workspace_dir"], ignore_errors=True)

    def test_openshell_tier_used_via_route(self):
        """Verify _route_to_agent is called with openshell/sandbox params from _execute_agents."""
        plan = [
            {"step": 1, "task_type": "BACKEND", "description": "API", "depends_on": [], "agent_role": "developer"},
        ]
        orch, run = self._setup_orch_for_execute(plan)
        route_calls = []

        def capture_route(*args, **kwargs):
            route_calls.append(kwargs)
            return dict(MOCK_BUILD_RESULT)

        with patch.object(orch, "_route_to_agent", side_effect=capture_route), \
             patch.object(orch, "_checkpoint"), \
             patch.object(orch, "_audit"), \
             patch.object(orch, "_summarize_context", return_value=""), \
             patch.object(orch, "_check_drift", return_value=True), \
             patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.side_effect = lambda tt: "developer"
            ar.record = MagicMock()
            orch._execute_agents(run)

        assert len(route_calls) == 1
        # _execute_agents should pass openshell and local_sandbox kwargs
        assert "openshell" in route_calls[0]
        assert "local_sandbox" in route_calls[0]

        shutil.rmtree(run["workspace_dir"], ignore_errors=True)

    def test_checkpoint_called_per_wave(self):
        plan = [
            {"step": 1, "task_type": "BACKEND", "description": "API", "depends_on": [], "agent_role": "developer"},
            {"step": 2, "task_type": "FRONTEND", "description": "UI", "depends_on": [1], "agent_role": "developer"},
        ]
        orch, run = self._setup_orch_for_execute(plan)

        with self._mock_route(orch), \
             patch.object(orch, "_checkpoint") as mock_cp, \
             patch.object(orch, "_audit"), \
             patch.object(orch, "_summarize_context", return_value=""), \
             patch.object(orch, "_check_drift", return_value=True), \
             patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.side_effect = lambda tt: "developer"
            ar.record = MagicMock()
            orch._execute_agents(run)

        assert mock_cp.call_count >= 2

        shutil.rmtree(run["workspace_dir"], ignore_errors=True)

    def test_all_tasks_blocked_wave_skipped(self):
        """All tasks in wave 2 depend on a failed wave 1 task."""
        plan = [
            {"step": 1, "task_type": "BACKEND", "description": "API", "depends_on": [], "agent_role": "developer"},
            {"step": 2, "task_type": "TESTS", "description": "Tests", "depends_on": [1], "agent_role": "developer"},
            {"step": 3, "task_type": "DEPLOY", "description": "Deploy", "depends_on": [1], "agent_role": "developer"},
        ]
        orch, run = self._setup_orch_for_execute(plan)

        with self._mock_route(orch, fail=True), \
             patch.object(orch, "_checkpoint"), \
             patch.object(orch, "_audit"), \
             patch.object(orch, "_summarize_context", return_value=""), \
             patch.object(orch, "_check_drift", return_value=False), \
             patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.side_effect = lambda tt: "developer"
            ar.record = MagicMock()
            orch._execute_agents(run)

        blocked = [r for r in run["agent_results"]
                   if r.get("result", {}).get("status") == "blocked"]
        assert len(blocked) >= 2

        shutil.rmtree(run["workspace_dir"], ignore_errors=True)


# ---------------------------------------------------------------------------
# Group 9: Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_route_with_no_openshell_no_sandbox(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()

        with patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.return_value = "developer"
            result = orch._route_to_agent(
                MOCK_TASK, "developer", openswe, MOCK_RUN,
                openshell=None, local_sandbox=None,
            )
        assert result["status"] == "completed"

    def test_enrich_task_no_acceptance_criteria(self):
        orch = _fresh_orchestrator()
        task = {**MOCK_TASK}
        task.pop("acceptance_criteria", None)
        result = orch._enrich_task(task, MOCK_RUN)
        assert "description" in result
        assert "Build REST API" in result["description"]

    def test_enrich_task_unknown_task_type(self):
        orch = _fresh_orchestrator()
        task = {**MOCK_TASK, "task_type": "COMPLETELY_UNKNOWN_TYPE_XYZ"}
        result = orch._enrich_task(task, MOCK_RUN)
        # Should not crash, description should still be present
        assert "Build REST API" in result["description"]

    def test_policy_unknown_task_type(self):
        orch = _fresh_orchestrator()
        policy = orch._build_sandbox_policy({"task_type": "UNKNOWN_TYPE"})
        # Base restrictive policy
        assert policy["network_policies"]["allow_outbound"] is False
        assert "/workspace" in policy["filesystem_policy"]["writable_paths"]

    def test_openshell_not_available_skips_cleanly(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        openshell = _mock_openshell(available=False)

        with patch("src.integrations.build_orchestrator.adaptive_router") as ar:
            ar.route.return_value = "developer"
            result = orch._route_to_agent(
                MOCK_TASK, "developer", openswe, MOCK_RUN,
                openshell=openshell, local_sandbox=None,
            )
        # Skips tier 1, falls to tier 3
        assert result["status"] == "completed"
        # sandbox() should never be called
        openshell.sandbox.assert_not_called()

    def test_concurrent_route_to_agent_calls(self):
        """Thread-safety: multiple simultaneous _route_to_agent calls."""
        orch = _fresh_orchestrator()
        results = []
        errors = []

        def run_route(idx):
            try:
                openswe = _mock_openswe()
                with patch("src.integrations.build_orchestrator.adaptive_router") as ar:
                    ar.route.return_value = "developer"
                    r = orch._route_to_agent(
                        {**MOCK_TASK, "step": idx}, "developer", openswe, MOCK_RUN,
                        openshell=None, local_sandbox=None,
                    )
                    results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run_route, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(results) == 5
        assert all(r["status"] == "completed" for r in results)


# ---------------------------------------------------------------------------
# Group 10: Integration with Real Temp Dirs
# ---------------------------------------------------------------------------

class TestIntegrationTempDirs:

    def test_sandbox_runner_copies_real_workspace(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        local_sandbox = _mock_local_sandbox()

        workspace = tempfile.mkdtemp()
        os.makedirs(os.path.join(workspace, "src"), exist_ok=True)
        with open(os.path.join(workspace, "src", "main.py"), "w") as f:
            f.write("print('hello world')")

        try:
            result = orch._try_sandbox_runner(MOCK_TASK, workspace, local_sandbox, openswe)
            assert result is not None
            assert result["execution_tier"] == "sandbox_runner"
            # Original workspace untouched
            assert os.path.exists(os.path.join(workspace, "src", "main.py"))
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def test_sandbox_runner_cleanup_on_exception(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe(raises=True)
        local_sandbox = _mock_local_sandbox()

        workspace = tempfile.mkdtemp()
        with open(os.path.join(workspace, "test.py"), "w") as f:
            f.write("x = 1")

        try:
            result = orch._try_sandbox_runner(MOCK_TASK, workspace, local_sandbox, openswe)
            assert result is None  # Exception caught
            # Workspace still exists
            assert os.path.exists(workspace)
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def test_sandbox_runner_with_empty_workspace(self):
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        local_sandbox = _mock_local_sandbox()

        workspace = tempfile.mkdtemp()
        try:
            result = orch._try_sandbox_runner(MOCK_TASK, workspace, local_sandbox, openswe)
            assert result is not None
            assert result["execution_tier"] == "sandbox_runner"
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def test_full_cascade_through_tier2_with_real_fs(self):
        """Full cascade: OpenShell unavailable → SandboxRunner with real FS → success."""
        orch = _fresh_orchestrator()
        openswe = _mock_openswe()
        openshell = _mock_openshell(available=False)
        local_sandbox = _mock_local_sandbox()

        workspace = tempfile.mkdtemp()
        with open(os.path.join(workspace, "app.py"), "w") as f:
            f.write("from flask import Flask")

        try:
            with patch("src.integrations.build_orchestrator.adaptive_router") as ar:
                ar.route.return_value = "developer"
                result = orch._route_to_agent(
                    MOCK_TASK, "developer", openswe, {**MOCK_RUN, "workspace_dir": workspace},
                    openshell=openshell, local_sandbox=local_sandbox,
                )
            assert result["execution_tier"] == "sandbox_runner"
            assert result["status"] == "completed"
            # Original file untouched
            with open(os.path.join(workspace, "app.py")) as f:
                assert "Flask" in f.read()
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
