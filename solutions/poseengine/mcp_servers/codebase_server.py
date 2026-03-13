"""
PoseEngine — Codebase Awareness MCP Server
==========================================
Gives SAGE agents the ability to inspect the PoseEngine solution's own state:
  - What task types are defined
  - What roles exist
  - What's implemented vs pending
  - Test status

This is what enables the tech_lead and ADVISE_BUILD task to be self-aware
rather than relying solely on what's embedded in the system prompt.

Usage via MCP tool call:
    get_solution_state()       → current YAML + implementation summary
    get_task_types()           → all defined task types
    get_roles()                → all universal agent roles
    get_implementation_gaps()  → known gaps from knowledge seed
    run_solution_tests()       → run pytest and return summary
"""

import json
import os
import subprocess
import sys

import yaml

SOLUTION_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAGE_ROOT = os.path.abspath(os.path.join(SOLUTION_DIR, "..", ".."))


def _load_yaml(filename: str) -> dict:
    path = os.path.join(SOLUTION_DIR, filename)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def get_task_types() -> dict:
    """Return all task types defined in tasks.yaml."""
    tasks = _load_yaml("tasks.yaml")
    types = tasks.get("task_types", [])
    descriptions = tasks.get("task_descriptions", {})
    return {
        "task_types": types,
        "count": len(types),
        "descriptions": descriptions,
    }


def get_roles() -> dict:
    """Return all universal agent roles defined in prompts.yaml."""
    prompts = _load_yaml("prompts.yaml")
    roles = prompts.get("roles", {})
    return {
        "roles": [
            {
                "id": role_id,
                "name": cfg.get("name", role_id),
                "description": cfg.get("description", ""),
                "icon": cfg.get("icon", "🤖"),
            }
            for role_id, cfg in roles.items()
        ],
        "count": len(roles),
    }


def get_solution_state() -> dict:
    """Return a summary of current solution configuration and known gaps."""
    project = _load_yaml("project.yaml")
    tasks = _load_yaml("tasks.yaml")
    prompts = _load_yaml("prompts.yaml")

    # Count test files
    tests_dir = os.path.join(SOLUTION_DIR, "tests")
    test_files = [
        f for f in os.listdir(tests_dir)
        if f.startswith("test_") and f.endswith(".py")
    ] if os.path.isdir(tests_dir) else []

    return {
        "solution": project.get("name", "poseengine"),
        "version": project.get("version", "unknown"),
        "domain": project.get("domain", "ml-mobile"),
        "active_modules": project.get("active_modules", []),
        "integrations": project.get("integrations", []),
        "task_type_count": len(tasks.get("task_types", [])),
        "role_count": len(prompts.get("roles", {})),
        "test_files": test_files,
        "test_count": len(test_files),
        "known_gaps": [
            "Queue dispatcher (queue_manager.py) does not handle poseengine task types",
            "ANALYZE_POSE_SEQUENCE not wired to any agent",
            "GENERATE_FEEDBACK not wired to any agent",
            "EVALUATE_MODEL / EXPORT_MODEL / REGISTER_MODEL not wired",
            "WandB poller not implemented in monitor",
            "Model registry API endpoint missing",
            "Zero actual test files in solutions/poseengine/tests/",
            "GitHub support missing from developer.py (GitLab only)",
        ],
    }


def get_implementation_gaps() -> dict:
    """Return structured gap analysis: what's defined vs what's wired."""
    tasks = _load_yaml("tasks.yaml")
    task_types = tasks.get("task_types", [])

    # These are dispatched by queue_manager._dispatch()
    wired_in_queue = {
        "ANALYZE_LOG", "CREATE_MR", "REVIEW_MR",
        "FLASH_FIRMWARE", "MONITOR_CHECK", "PLAN_TASK",
    }

    not_wired = [t for t in task_types if t not in wired_in_queue]

    return {
        "total_task_types": len(task_types),
        "wired_in_queue": list(wired_in_queue & set(task_types)),
        "not_wired_in_queue": not_wired,
        "not_wired_count": len(not_wired),
        "priority_gaps": [
            {
                "gap": "Queue dispatch missing for poseengine task types",
                "impact": "HIGH — all poseengine-specific tasks silently fail",
                "fix": "Add dispatch cases in src/core/queue_manager.py _dispatch()",
            },
            {
                "gap": "No ANALYZE_POSE_SEQUENCE implementation",
                "impact": "HIGH — core platform capability absent",
                "fix": "Add sequence_analyst agent or extend AnalystAgent",
            },
            {
                "gap": "No GENERATE_FEEDBACK implementation",
                "impact": "HIGH — all application domains (yoga/dance/etc) need this",
                "fix": "Add feedback_generator agent using prompts.yaml role",
            },
            {
                "gap": "Zero tests",
                "impact": "MEDIUM — no regression safety net",
                "fix": "Add solutions/poseengine/tests/test_*.py with mocked LLM",
            },
        ],
    }


def run_solution_tests() -> dict:
    """Run poseengine solution tests and return summary."""
    venv_pytest = os.path.join(SAGE_ROOT, ".venv", "bin", "pytest")
    tests_dir = os.path.join(SOLUTION_DIR, "tests")

    cmd = [
        venv_pytest, tests_dir,
        "-v", "--tb=short", "--no-header", "-q",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=SAGE_ROOT,
            env={**os.environ, "SAGE_PROJECT": "poseengine"},
        )
        lines = (result.stdout + result.stderr).strip().split("\n")
        summary_line = next((l for l in reversed(lines) if "passed" in l or "failed" in l or "error" in l), "no tests collected")
        return {
            "returncode": result.returncode,
            "summary": summary_line,
            "passed": result.returncode == 0,
            "output": "\n".join(lines[-20:]),  # last 20 lines
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "summary": "timeout", "passed": False, "output": "Tests timed out after 120s"}
    except Exception as e:
        return {"returncode": -1, "summary": str(e), "passed": False, "output": str(e)}


# ---------------------------------------------------------------------------
# MCP entry point (fastmcp)
# ---------------------------------------------------------------------------
try:
    from fastmcp import FastMCP

    mcp = FastMCP("poseengine-codebase")

    @mcp.tool()
    def solution_state() -> str:
        """Get current PoseEngine solution state: task types, roles, test count, known gaps."""
        return json.dumps(get_solution_state(), indent=2)

    @mcp.tool()
    def task_types() -> str:
        """List all task types defined in poseengine/tasks.yaml."""
        return json.dumps(get_task_types(), indent=2)

    @mcp.tool()
    def agent_roles() -> str:
        """List all universal agent roles defined in poseengine/prompts.yaml."""
        return json.dumps(get_roles(), indent=2)

    @mcp.tool()
    def implementation_gaps() -> str:
        """Return structured gap analysis: which task types are defined but not wired."""
        return json.dumps(get_implementation_gaps(), indent=2)

    @mcp.tool()
    def solution_tests() -> str:
        """Run poseengine test suite and return pass/fail summary."""
        return json.dumps(run_solution_tests(), indent=2)

    if __name__ == "__main__":
        if len(sys.argv) > 1:
            import argparse
            parser = argparse.ArgumentParser(description="PoseEngine codebase awareness tool")
            parser.add_argument("command", choices=["state", "tasks", "roles", "gaps", "tests"])
            args = parser.parse_args()
            dispatch = {
                "state": get_solution_state,
                "tasks": get_task_types,
                "roles": get_roles,
                "gaps": get_implementation_gaps,
                "tests": run_solution_tests,
            }
            print(json.dumps(dispatch[args.command](), indent=2))
        else:
            mcp.run()

except ImportError:
    # fastmcp not installed — functions still usable directly
    if __name__ == "__main__":
        import argparse
        parser = argparse.ArgumentParser(description="PoseEngine codebase awareness tool")
        parser.add_argument("command", choices=["state", "tasks", "roles", "gaps", "tests"])
        args = parser.parse_args()

        dispatch = {
            "state": get_solution_state,
            "tasks": get_task_types,
            "roles": get_roles,
            "gaps": get_implementation_gaps,
            "tests": run_solution_tests,
        }
        print(json.dumps(dispatch[args.command](), indent=2))
