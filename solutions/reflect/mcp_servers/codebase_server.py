"""
Reflect — Codebase Awareness MCP Server
========================================
Gives SAGE agents the ability to inspect the Reflect platform's own state:
  - What task types are defined
  - What roles exist
  - What's implemented vs pending (from STATE.md)
  - Test counts per component

Usage via MCP tool call:
    get_solution_state()       → current YAML + implementation summary
    get_task_types()           → all defined task types
    get_roles()                → all universal agent roles
    get_implementation_gaps()  → known gaps from STATE.md
    run_solution_tests()       → run pytest and return summary
"""

import json
import os
import subprocess
import sys

import yaml

SOLUTION_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAGE_ROOT = os.path.abspath(os.path.join(SOLUTION_DIR, "..", ".."))
REFLECT_ROOT = "/home/shetty/sandbox/Reflect"


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

    tests_dir = os.path.join(SOLUTION_DIR, "tests")
    test_files = [
        f for f in os.listdir(tests_dir)
        if f.startswith("test_") and f.endswith(".py")
    ] if os.path.isdir(tests_dir) else []

    # Check Reflect repo test counts (approximate)
    reflect_tests = {}
    for component, rel_path in [
        ("extract_engine", "extract_engine/tests"),
        ("pose_engine", "pose_engine/test"),
        ("platform_sdk", "platform_sdk"),
        ("agents", "agents/tests"),
    ]:
        full = os.path.join(REFLECT_ROOT, rel_path)
        if os.path.isdir(full):
            reflect_tests[component] = "present"
        else:
            reflect_tests[component] = "not found"

    return {
        "solution": project.get("name", "reflect"),
        "version": project.get("version", "unknown"),
        "domain": project.get("domain", "movement-analysis"),
        "activity_modules": project.get("activity_modules", []),
        "tenants": project.get("tenants", []),
        "integrations": project.get("integrations", []),
        "task_type_count": len(tasks.get("task_types", [])),
        "role_count": len(prompts.get("roles", {})),
        "sage_test_files": test_files,
        "reflect_components": reflect_tests,
        "reflect_root": REFLECT_ROOT,
        "reflect_exists": os.path.isdir(REFLECT_ROOT),
    }


def get_implementation_gaps() -> dict:
    """Return structured gap analysis from STATE.md."""
    return {
        "phase": "Phase 2 — Quality & Completeness",
        "priority_gaps": [
            {
                "gap": "Voice pack not wired to Flutter app",
                "impact": "HIGH — no TTS feedback in app; core UX feature missing",
                "fix": "Connect voice_packs/ system to Flutter TTS in flutter_app/",
            },
            {
                "gap": "Sequence/flow movement support missing",
                "impact": "HIGH — blocks tai chi, qigong, sun salutation flows",
                "fix": "Extend skill pack schema and C++ engine for sequence detection",
            },
            {
                "gap": "Gym module only 2 movements",
                "impact": "HIGH — ironform_gym tenant cannot use the platform",
                "fix": "Extract 8+ gym movements (squat, deadlift, bench, row, lunge, ...)",
            },
            {
                "gap": "Physical therapy only 2 movements",
                "impact": "HIGH — movewell_clinic blocked; requires clinical review",
                "fix": "Extract 6+ PT movements with clinical sign-off",
            },
            {
                "gap": "Flutter SDK not in CI",
                "impact": "HIGH — 55 Flutter tests skipped; regressions undetected",
                "fix": "Add Flutter SDK to CI environment and enable flutter test suite",
            },
            {
                "gap": "Multi-angle evaluation not implemented",
                "impact": "MEDIUM — skill pack quality unknown from non-frontal camera angles",
                "fix": "Add multi-angle test recordings and evaluation pipeline",
            },
            {
                "gap": "Admin web panel does not exist",
                "impact": "MEDIUM — extract stage requires CLI; blocks non-technical tenants",
                "fix": "Phase 3 deliverable — web UI for extract + skill pack management",
            },
        ],
    }


def run_solution_tests() -> dict:
    """Run reflect solution tests and return summary."""
    venv_pytest = os.path.join(SAGE_ROOT, ".venv", "bin", "pytest")
    tests_dir = os.path.join(SOLUTION_DIR, "tests")

    cmd = [venv_pytest, tests_dir, "-v", "--tb=short", "--no-header", "-q"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=SAGE_ROOT,
            env={**os.environ, "SAGE_PROJECT": "reflect"},
        )
        lines = (result.stdout + result.stderr).strip().split("\n")
        summary_line = next(
            (l for l in reversed(lines) if "passed" in l or "failed" in l or "error" in l),
            "no tests collected",
        )
        return {
            "returncode": result.returncode,
            "summary": summary_line,
            "passed": result.returncode == 0,
            "output": "\n".join(lines[-20:]),
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "summary": "timeout", "passed": False, "output": "Tests timed out"}
    except Exception as e:
        return {"returncode": -1, "summary": str(e), "passed": False, "output": str(e)}


# ---------------------------------------------------------------------------
# MCP entry point (fastmcp)
# ---------------------------------------------------------------------------
try:
    from fastmcp import FastMCP

    mcp = FastMCP("reflect-codebase")

    @mcp.tool()
    def solution_state() -> str:
        """Get current Reflect solution state: modules, tenants, task types, roles."""
        return json.dumps(get_solution_state(), indent=2)

    @mcp.tool()
    def task_types() -> str:
        """List all task types defined in reflect/tasks.yaml."""
        return json.dumps(get_task_types(), indent=2)

    @mcp.tool()
    def agent_roles() -> str:
        """List all agent roles defined in reflect/prompts.yaml."""
        return json.dumps(get_roles(), indent=2)

    @mcp.tool()
    def implementation_gaps() -> str:
        """Return structured gap analysis: current Phase 2 gaps with impact and fix."""
        return json.dumps(get_implementation_gaps(), indent=2)

    @mcp.tool()
    def solution_tests() -> str:
        """Run reflect SAGE solution test suite and return pass/fail summary."""
        return json.dumps(run_solution_tests(), indent=2)

    if __name__ == "__main__":
        if len(sys.argv) > 1:
            # CLI mode when called with a command argument
            import argparse
            parser = argparse.ArgumentParser(description="Reflect codebase awareness tool")
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
    if __name__ == "__main__":
        import argparse
        parser = argparse.ArgumentParser(description="Reflect codebase awareness tool")
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
