#!/usr/bin/env python3
"""
SAGE Self-Improvement Runner
=============================
Runs the EvaluatorOptimizer loop (Claude as BOTH optimizer and evaluator)
across a catalogue of improvement tasks, producing HITL-gated proposals.

Nothing is applied automatically — every output is a proposal that a human
must review and approve through the SAGE approval gate.

Usage:
    python scripts/self_improve.py                        # all tasks
    python scripts/self_improve.py --batch backend        # one category
    python scripts/self_improve.py --task-ids 1,3,7      # specific tasks
    python scripts/self_improve.py --dry-run              # print plan only
    python scripts/self_improve.py --resume               # skip done tasks

Output:  docs/proposals/<YYYYMMDD>-self-improvement/
         ├── _summary.md        ← ranked table + run stats
         ├── task-01-*.md       ← final proposal (submit to HITL gate)
         └── ...
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Improvement catalogue — add / remove tasks here
# Each entry: (id, category, task_description, context_files, criteria)
# context_files: repo-relative paths (read as context for the optimizer).
# ---------------------------------------------------------------------------
SAGE_ROOT = Path(__file__).parent.parent

TASKS: list[dict] = [

    # ── BACKEND / API ───────────────────────────────────────────────────────

    {
        "id": 1, "category": "backend",
        "title": "Typed FastAPI response models",
        "task": (
            "Add Pydantic response models to every FastAPI endpoint in "
            "src/interface/api.py that currently returns a bare dict. "
            "Define models in a new src/interface/schemas.py. "
            "Return typed responses so OpenAPI docs are accurate and clients "
            "get schema validation. Keep all existing behaviour."
        ),
        "context_files": ["src/interface/api.py"],
        "criteria": (
            "Every endpoint has a response_model; a schemas.py is created with "
            "all model classes; existing tests still pass; no business logic changed."
        ),
    },

    {
        "id": 2, "category": "backend",
        "title": "Structured error events in agents",
        "task": (
            "Replace bare `except Exception as e: logger.error(str(e))` blocks "
            "in src/agents/analyst.py, developer.py, and universal.py with "
            "structured error events: emit a dict with keys "
            "`{event:'agent_error', agent:..., task_id:..., error_type:..., "
            "message:..., trace_id:...}` to the audit_logger on failure. "
            "Keep the same external behaviour."
        ),
        "context_files": [
            "src/agents/analyst.py", "src/agents/developer.py",
            "src/agents/universal.py", "src/memory/audit_logger.py",
        ],
        "criteria": (
            "All bare except blocks are replaced; audit_logger receives structured "
            "dicts on agent failure; no new bare excepts introduced; "
            "existing tests pass."
        ),
    },

    {
        "id": 3, "category": "backend",
        "title": "Request-ID propagation end-to-end",
        "task": (
            "Add a request_id (UUID4) to every incoming FastAPI request via "
            "a middleware that sets a context var. Propagate it through "
            "llm_gateway.generate() as an optional param and log it in "
            "every audit_logger.log() call. Add X-Request-ID to all responses. "
            "No breaking changes to existing endpoints."
        ),
        "context_files": [
            "src/interface/api.py", "src/core/llm_gateway.py",
            "src/memory/audit_logger.py",
        ],
        "criteria": (
            "A middleware adds request_id; it is threaded through LLM calls and "
            "audit log entries; X-Request-ID response header is present; "
            "all existing tests pass."
        ),
    },

    {
        "id": 4, "category": "backend",
        "title": "Circuit breaker for LLM providers",
        "task": (
            "Add a lightweight circuit breaker to src/core/llm_gateway.py: "
            "after 3 consecutive failures on a provider, open the circuit for "
            "60 seconds (return an error immediately, don't call the provider). "
            "Log state transitions (CLOSED->OPEN->HALF_OPEN->CLOSED). "
            "Keep the existing provider interface unchanged."
        ),
        "context_files": ["src/core/llm_gateway.py"],
        "criteria": (
            "A CircuitBreaker class or inline logic opens after 3 failures; "
            "waits 60 s before retrying; logs state transitions; "
            "passes=False returns immediately while open; "
            "no change to LLMGateway public interface."
        ),
    },

    {
        "id": 5, "category": "backend",
        "title": "Structured logging schema",
        "task": (
            "Replace all `logger.info(f'...')` f-string calls in "
            "src/core/llm_gateway.py and src/core/queue_manager.py with "
            "structured `logger.info(msg, extra={...})` calls. "
            "Fields: event, provider, duration_ms, task_id, status. "
            "Add a JSON formatter option in a new src/core/log_config.py "
            "that can be toggled with env var SAGE_JSON_LOGS=1."
        ),
        "context_files": [
            "src/core/llm_gateway.py", "src/core/queue_manager.py",
        ],
        "criteria": (
            "No f-string logs remain in targeted files; "
            "all log calls use extra={} with named fields; "
            "log_config.py exists with JSON formatter; "
            "SAGE_JSON_LOGS=1 activates it; existing tests pass."
        ),
    },

    {
        "id": 6, "category": "backend",
        "title": "Rate limiting on /agent/run",
        "task": (
            "Add per-IP rate limiting to the POST /agent/run endpoint in "
            "src/interface/api.py: max 10 requests per 60 seconds per IP. "
            "Return HTTP 429 with Retry-After header on excess. "
            "Use a simple in-memory token-bucket (no Redis dependency). "
            "Add a config option in config.yaml: api.rate_limit_per_min."
        ),
        "context_files": ["src/interface/api.py", "config/config.yaml"],
        "criteria": (
            "Rate limiter exists; /agent/run returns 429 after 10 req/60s from "
            "same IP; Retry-After header is set; config key documented; "
            "no external dependency added."
        ),
    },

    {
        "id": 7, "category": "backend",
        "title": "YAML schema validation on project load",
        "task": (
            "Add JSON Schema or Pydantic validation to "
            "src/core/project_loader.py so that when a solution's "
            "project.yaml, prompts.yaml, or tasks.yaml is loaded, "
            "required fields are checked and a clear error is raised "
            "(not a KeyError deep in agent code). "
            "Define minimal schemas for the three YAML files."
        ),
        "context_files": ["src/core/project_loader.py"],
        "criteria": (
            "Missing required fields raise a descriptive ValidationError at load "
            "time; the three YAML schemas are defined; "
            "valid existing solution YAMLs still load without error."
        ),
    },

    {
        "id": 8, "category": "backend",
        "title": "Health endpoint enrichment",
        "task": (
            "Extend GET /health in src/interface/api.py to return: "
            "queue_depth (int), llm_provider (str), llm_status ('ok'|'degraded'|'down'), "
            "memory_entries (int from vector store if available), "
            "uptime_seconds (float). "
            "Add the new fields without breaking the existing response shape."
        ),
        "context_files": [
            "src/interface/api.py", "src/core/queue_manager.py",
            "src/core/llm_gateway.py",
        ],
        "criteria": (
            "GET /health returns all 5 new fields; existing 'status' field preserved; "
            "degraded LLM provider does not crash the health check; "
            "test_api.py tests pass."
        ),
    },

    {
        "id": 9, "category": "backend",
        "title": "ProposalRepository extracted from api.py",
        "task": (
            "Extract the SQLite proposal CRUD operations in "
            "src/interface/api.py into a new "
            "src/core/proposal_repository.py with a ProposalRepository class. "
            "Methods: create(), get(), list(), approve(), reject(), batch_approve(). "
            "api.py imports and calls ProposalRepository — no direct DB access in api.py."
        ),
        "context_files": ["src/interface/api.py"],
        "criteria": (
            "ProposalRepository class exists with all 6 methods; "
            "api.py has no direct sqlite3 calls for proposals; "
            "all existing proposal endpoints still work; tests pass."
        ),
    },

    {
        "id": 10, "category": "backend",
        "title": "Input sanitization for task descriptions",
        "task": (
            "Add input sanitization to the POST /agent/run endpoint: "
            "strip null bytes, control characters (\\x00-\\x1f except \\t\\n), "
            "and limit task description to 4000 chars. "
            "Return HTTP 422 with a clear message for invalid input. "
            "Add a pure-function sanitize_task_input() in src/modules/payload_validator.py."
        ),
        "context_files": [
            "src/interface/api.py", "src/modules/payload_validator.py",
        ],
        "criteria": (
            "sanitize_task_input() exists in payload_validator.py; "
            "null bytes and control chars are stripped; "
            "task > 4000 chars returns 422; existing valid requests still work."
        ),
    },

    # ── WEB UI ──────────────────────────────────────────────────────────────

    {
        "id": 11, "category": "ui",
        "title": "StatusDot shared component",
        "task": (
            "Create web/src/components/ui/StatusDot.tsx: a shared component "
            "that renders an online/offline/degraded indicator. "
            "Props: status ('online'|'offline'|'degraded'), label (string), size ('sm'|'md'). "
            "Replace the 3 inline status dot implementations in "
            "Header.tsx, Dashboard.tsx, and LLMSettings.tsx with <StatusDot>. "
            "Use only existing Tailwind classes."
        ),
        "context_files": [
            "web/src/components/layout/Header.tsx",
            "web/src/pages/Dashboard.tsx",
        ],
        "criteria": (
            "StatusDot.tsx exists with correct props; "
            "renders green for online, red for offline, amber for degraded; "
            "imported in Header.tsx and Dashboard.tsx; "
            "no duplicate inline status dot code remains in those files; "
            "TypeScript compiles without errors."
        ),
    },

    {
        "id": 12, "category": "ui",
        "title": "Skeleton loading states",
        "task": (
            "Add skeleton loading states to web/src/pages/Analyst.tsx, "
            "Monitor.tsx, and Improvements.tsx. "
            "When data is fetching, show a pulse-animated grey placeholder "
            "the same shape as the loaded content. "
            "Use a shared web/src/components/ui/Skeleton.tsx component. "
            "No external dependency — pure Tailwind animate-pulse."
        ),
        "context_files": [
            "web/src/pages/Analyst.tsx",
            "web/src/pages/Monitor.tsx",
        ],
        "criteria": (
            "Skeleton.tsx exists with variant='text'|'card'|'row' props; "
            "Analyst.tsx and Monitor.tsx render skeletons while fetching; "
            "no loading spinner removed (both can coexist); "
            "TypeScript compiles."
        ),
    },

    {
        "id": 13, "category": "ui",
        "title": "Error boundaries for page components",
        "task": (
            "Add a React error boundary to web/src/App.tsx that wraps "
            "each route. On render error, show a fallback card with: "
            "the error message, a 'Try again' button (reloads the route), "
            "and a 'Go to Dashboard' link. "
            "Create web/src/components/ui/ErrorBoundary.tsx as a class component. "
            "Do not wrap the Header or Sidebar (only the main content area)."
        ),
        "context_files": ["web/src/App.tsx"],
        "criteria": (
            "ErrorBoundary.tsx is a React class component; "
            "it wraps only the route <Outlet> in App.tsx; "
            "renders fallback card with error message and two actions; "
            "TypeScript compiles; does not break normal rendering."
        ),
    },

    {
        "id": 14, "category": "ui",
        "title": "Aria-labels on icon-only buttons",
        "task": (
            "Add aria-label attributes to every icon-only button (a button "
            "with no visible text, only an SVG icon) in: "
            "web/src/components/layout/Header.tsx, "
            "web/src/components/layout/Sidebar.tsx, "
            "web/src/components/proposals/ProposalCard.tsx. "
            "The aria-label should describe the action, not the icon. "
            "Example: aria-label='Approve proposal' not aria-label='Check mark'."
        ),
        "context_files": [
            "web/src/components/layout/Header.tsx",
            "web/src/components/layout/Sidebar.tsx",
            "web/src/components/proposals/ProposalCard.tsx",
        ],
        "criteria": (
            "Every icon-only button has aria-label; "
            "labels describe the action; "
            "no visible text added to the UI; "
            "TypeScript compiles."
        ),
    },

    {
        "id": 15, "category": "ui",
        "title": "Copy-to-clipboard for diff/code blocks",
        "task": (
            "Add a copy-to-clipboard button to the diff <pre> block in "
            "web/src/components/proposals/ProposalCard.tsx. "
            "The button appears in the top-right corner of the pre block "
            "on hover, shows a clipboard icon, and changes to a check mark "
            "for 2 seconds after copying. "
            "Use the browser Clipboard API (no external dep). "
            "Also apply to any <pre> blocks in the Audit log page."
        ),
        "context_files": [
            "web/src/components/proposals/ProposalCard.tsx",
            "web/src/pages/Audit.tsx",
        ],
        "criteria": (
            "Copy button appears on hover over <pre>; "
            "clipboard API is used; "
            "visual feedback (check icon) shows for 2s after copy; "
            "button is accessible (aria-label='Copy to clipboard'); "
            "TypeScript compiles."
        ),
    },

    # ── TESTING ─────────────────────────────────────────────────────────────

    {
        "id": 16, "category": "testing",
        "title": "YAML config loader property tests",
        "task": (
            "Add property-based tests for src/core/project_loader.py using "
            "pytest + hypothesis. Test: (1) a valid project.yaml always loads "
            "without error; (2) a project.yaml missing any required field raises "
            "a clear error; (3) extra unknown fields are ignored. "
            "Define a hypothesis strategy that generates valid/invalid YAML dicts."
        ),
        "context_files": [
            "src/core/project_loader.py",
            "tests/test_project_loader.py",
        ],
        "criteria": (
            "Hypothesis is used for at least 2 tests; "
            "valid YAML strategy is defined; "
            "invalid YAML strategy tests required fields; "
            "tests run with pytest and pass; "
            "no external deps beyond hypothesis."
        ),
    },

    {
        "id": 17, "category": "testing",
        "title": "End-to-end agent run -> audit log test",
        "task": (
            "Add an integration test in tests/test_integration_agent_audit.py that: "
            "(1) posts a task to /agent/run via TestClient; "
            "(2) polls /agent/status until complete; "
            "(3) checks /audit/log contains an entry for that task_id; "
            "(4) checks the audit entry has the correct agent role and status. "
            "Mock the LLM provider to return a deterministic response."
        ),
        "context_files": [
            "src/interface/api.py", "src/memory/audit_logger.py",
            "tests/test_api.py",
        ],
        "criteria": (
            "test_integration_agent_audit.py exists with at least 2 test cases; "
            "LLM is mocked (no real API calls); "
            "audit log entry is verified by task_id; "
            "tests pass with pytest."
        ),
    },

    {
        "id": 18, "category": "testing",
        "title": "LLM provider fallback test",
        "task": (
            "Add tests in tests/test_llm_gateway.py for provider fallback: "
            "(1) when the primary provider raises an exception, the gateway "
            "falls back to the secondary provider if configured; "
            "(2) when all providers fail, the gateway raises LLMProviderError "
            "with a message listing all failed providers. "
            "Mock all provider generate() calls."
        ),
        "context_files": [
            "src/core/llm_gateway.py", "tests/test_llm_gateway.py",
        ],
        "criteria": (
            "Fallback test uses mocked providers; "
            "all-fail test verifies LLMProviderError with provider list; "
            "no real LLM calls; tests pass with pytest."
        ),
    },

    # ── ARCHITECTURE / QUALITY ───────────────────────────────────────────────

    {
        "id": 19, "category": "architecture",
        "title": "Type hints for llm_gateway public methods",
        "task": (
            "Add complete PEP 484 type hints to all public methods in "
            "src/core/llm_gateway.py: generate(), switch_provider(), "
            "get_status(), get_session_stats(), and all provider classes. "
            "Use `from __future__ import annotations` at the top. "
            "Do not change any logic — annotations only."
        ),
        "context_files": ["src/core/llm_gateway.py"],
        "criteria": (
            "Every public method has return type annotation; "
            "every parameter has a type annotation; "
            "from __future__ import annotations is present; "
            "mypy or pyright raises no errors on the file; "
            "no logic changes."
        ),
    },

    {
        "id": 20, "category": "architecture",
        "title": "Retry policy class",
        "task": (
            "Extract the ad-hoc retry logic scattered across llm_gateway.py "
            "into a src/modules/retry_policy.py module. "
            "Define a RetryPolicy dataclass: max_attempts, base_delay_s, "
            "max_delay_s, jitter (bool). "
            "Add a retry() context manager / decorator that implements "
            "exponential backoff with optional jitter. "
            "Replace all manual retry loops in llm_gateway.py with RetryPolicy."
        ),
        "context_files": ["src/core/llm_gateway.py"],
        "criteria": (
            "retry_policy.py exists with RetryPolicy dataclass and retry mechanism; "
            "exponential backoff formula is correct (base * 2^attempt); "
            "jitter adds 0-25% random variance when enabled; "
            "llm_gateway.py has no manual retry loops; "
            "existing LLM tests pass."
        ),
    },

]

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

# Characters illegal in a Windows filename (and '/' which splits paths on any OS).
_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def slugify(title: str, task_id: int) -> str:
    """Build a filesystem-safe proposal filename stem.

    Titles can contain '/', '>', ':' etc. (e.g. '/agent/run', 'run -> audit'),
    which are illegal in Windows paths and previously crashed the writer.
    """
    base = title.lower().replace(" ", "-")
    base = _INVALID_FILENAME.sub("-", base)       # kill illegal chars
    base = re.sub(r"-{2,}", "-", base).strip("-")  # collapse/trim dashes
    return f"task-{task_id:02d}-{base[:40]}"


# Substrings that indicate a provider *usage/rate limit* or transient overload —
# i.e. "come back later", NOT a config/permission error. Matching these (and
# nothing else) is what makes the wait-and-retry safe: a stale-tool or
# untrusted-workspace failure will NOT match, so we don't sleep forever on it.
_LIMIT_MARKERS = (
    "usage limit", "rate limit", "rate_limit", "429",
    "too many requests", "limit reached", "quota",
    "overloaded", "resets at", "try again later", "please wait",
)


def _result_error_text(result: dict) -> str:
    """Concatenate everything the loop produced so we can scan for limit markers."""
    parts = [str(result.get("final", "")), str(result.get("error", ""))]
    for h in result.get("history", []):
        parts.append(str(h.get("candidate", "")))
        parts.append(str(h.get("feedback", "")))
    return "\n".join(parts).lower()


def hit_usage_limit(result: dict) -> bool:
    """True only when the task failed *and* the failure looks like a usage limit.

    A task that produced any real score (>0) clearly was not limit-blocked, so we
    never re-run a task that already succeeded.
    """
    if result.get("score", 0) > 0:
        return False
    return any(m in _result_error_text(result) for m in _LIMIT_MARKERS)


def proposal_is_done(out_file: Path, threshold: float) -> bool:
    """Whether an existing proposal file counts as 'done' for --resume.

    Existence alone is NOT enough: a broken run leaves score-0 / errored proposals
    on disk (e.g. the stale-MultiEdit failures), and those must be re-run, not
    skipped. A proposal is 'done' only if it actually converged (the evaluator
    passed it) or its recorded score met the threshold.
    """
    try:
        text = out_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if re.search(r"^\*\*Converged:\*\*\s*True", text, re.MULTILINE):
        return True
    m = re.search(r"^\*\*Score:\*\*\s*([0-9.]+)", text, re.MULTILINE)
    if m:
        try:
            return float(m.group(1)) >= threshold
        except ValueError:
            pass
    return False


def read_context(files: list[str]) -> str:
    """Read context files from the repo root, return concatenated content."""
    parts = []
    for rel in files:
        p = SAGE_ROOT / rel
        if p.exists():
            parts.append(f"=== FILE: {rel} ===\n{p.read_text(encoding='utf-8', errors='replace')}")
        else:
            parts.append(f"=== FILE: {rel} === (NOT FOUND — skip if irrelevant)")
    return "\n\n".join(parts)


def run_task(task: dict, out_dir: Path, max_iterations: int, threshold: float) -> dict:
    """Run one evaluator-optimizer loop. Returns result dict."""
    sys.path.insert(0, str(SAGE_ROOT))
    from src.core.evaluator_optimizer import EvaluatorOptimizerRunner

    context = read_context(task.get("context_files", []))

    runner = EvaluatorOptimizerRunner({
        # disallowed_tools is set explicitly (NOT the shared default in
        # evaluator_optimizer.py) because that default still lists "MultiEdit",
        # a tool the current Claude Code CLI no longer knows — which makes the CLI
        # reject the whole call with rc=1 ("deny rule MultiEdit matches no known
        # tool"). Keeping the optimizer write-restricted preserves the HITL
        # guarantee (pure text proposal, never touches the repo).
        "optimizer": {"provider": "claude-code", "model": "claude-opus-4-8", "timeout": 600,
                      "disallowed_tools": "Write Edit NotebookEdit Bash"},
        # Step 0(a): the EVALUATOR must NOT be the same model as the optimizer — a model
        # grading its own output is self-grading and inflates/misjudges scores. A different
        # (still strong) model keeps the judge independent. Opus optimizes; Sonnet evaluates.
        "evaluator": {"provider": "claude-code", "model": "claude-sonnet-4-6", "timeout": 300},
        "criteria": task["criteria"],
        "max_iterations": max_iterations,
        "score_threshold": threshold,
        "generate_rubric": True,
        "sandbox": True,
    })

    start = time.time()
    result = runner.run(task["task"], context)
    elapsed = time.time() - start

    result["task_id"]   = task["id"]
    result["title"]     = task["title"]
    result["category"]  = task["category"]
    result["elapsed_s"] = round(elapsed, 1)

    # Write proposal to disk
    slug = slugify(task["title"], task["id"])
    out_file = out_dir / f"{slug}.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"# Task {task['id']}: {task['title']}\n\n")
        f.write(f"**Category:** {task['category']}  \n")
        f.write(f"**Score:** {result.get('score', 0):.1f}/10  \n")
        f.write(f"**Converged:** {result.get('converged')}  \n")
        f.write(f"**Iterations:** {result.get('iterations')}  \n")
        f.write(f"**Elapsed:** {elapsed:.0f}s  \n\n")
        f.write("---\n\n")
        f.write(f"## Task\n\n{task['task']}\n\n")
        f.write(f"## Criteria\n\n{task['criteria']}\n\n")
        f.write("## Proposal (submit to HITL approval gate)\n\n")
        f.write(result.get("final") or "(no output)")
        f.write("\n\n---\n\n## Iteration History\n\n")
        for h in result.get("history", []):
            f.write(f"**Iter {h['iteration']}** — score {h['score']:.1f} pass={h['passed']}  \n")
            f.write(f"Feedback: {h['feedback'][:200]}  \n\n")

    result["out_file"] = str(out_file)
    return result


def write_summary(results: list[dict], out_dir: Path, args) -> None:
    """Write _summary.md ranked by score."""
    ranked = sorted(results, key=lambda r: r.get("score", 0), reverse=True)
    total_time = sum(r.get("elapsed_s", 0) for r in results)
    converged  = sum(1 for r in results if r.get("converged"))

    lines = [
        "# SAGE Self-Improvement Run — Summary",
        f"\n**Date:** {datetime.date.today()}  ",
        f"**Tasks run:** {len(results)}  ",
        f"**Converged:** {converged}/{len(results)}  ",
        f"**Total time:** {total_time/60:.1f} min  ",
        f"**Model:** Opus 4.8 optimizer / Sonnet 4.6 evaluator (independent judge)  ",
        f"**Max iterations:** {args.max_iterations}  ",
        f"**Threshold:** {args.threshold}  ",
        "\n> Nothing applied — all proposals require HITL approval.\n",
        "\n## Results (ranked by score)\n",
        "| Rank | ID | Category | Title | Score | Conv | Iters | Time |",
        "|------|-----|----------|-------|-------|------|-------|------|",
    ]
    for rank, r in enumerate(ranked, 1):
        conv = "✓" if r.get("converged") else "✗"
        lines.append(
            f"| {rank} | {r['task_id']} | {r['category']} | {r['title'][:40]} | "
            f"{r.get('score',0):.1f} | {conv} | {r.get('iterations')} | {r.get('elapsed_s',0):.0f}s |"
        )

    lines += [
        "\n## Apply Order (highest-scoring, same-category conflicts noted)\n",
    ]
    for r in ranked:
        if r.get("score", 0) >= args.threshold:
            lines.append(f"- **Task {r['task_id']}** ({r['category']}): {r['title']} — score {r.get('score',0):.1f}")

    lines += [
        "\n## Low-scoring / needs re-run\n",
    ]
    for r in ranked:
        if r.get("score", 0) < args.threshold:
            lines.append(f"- Task {r['task_id']}: {r['title']} — score {r.get('score',0):.1f}")

    out_file = out_dir / "_summary.md"
    out_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSummary written -> {out_file}")


def main():
    ap = argparse.ArgumentParser(description="SAGE Self-Improvement Runner")
    ap.add_argument("--batch", help="Run only tasks in this category (backend|ui|testing|architecture)")
    ap.add_argument("--task-ids", help="Comma-separated task IDs to run, e.g. 1,3,7")
    ap.add_argument("--max-iterations", type=int, default=3)
    ap.add_argument("--threshold", type=float, default=8.0)
    ap.add_argument("--dry-run", action="store_true", help="Print plan, don't run")
    ap.add_argument("--resume", action="store_true", help="Skip tasks with existing output files")
    ap.add_argument("--out-dir", default="", help="Override output directory")
    ap.add_argument("--limit-wait-min", type=float, default=30,
                    help="Minutes to wait before retrying a task that hit a usage limit / overload")
    ap.add_argument("--limit-max-retries", type=int, default=12,
                    help="Max wait-and-retry attempts per task on usage-limit errors (0 disables)")
    args = ap.parse_args()

    # Select tasks
    tasks = TASKS
    if args.batch:
        tasks = [t for t in tasks if t["category"] == args.batch]
    if args.task_ids:
        ids = {int(x.strip()) for x in args.task_ids.split(",")}
        tasks = [t for t in tasks if t["id"] in ids]

    if not tasks:
        print("No tasks match the filter. Exiting.")
        sys.exit(1)

    # Output directory
    date_str = datetime.date.today().strftime("%Y%m%d")
    out_dir = Path(args.out_dir) if args.out_dir else \
              SAGE_ROOT / "docs" / "proposals" / f"{date_str}-self-improvement"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nSAGE Self-Improvement Runner")
    print(f"Output -> {out_dir}")
    print(f"Tasks  -> {len(tasks)}  |  max_iterations={args.max_iterations}  |  threshold={args.threshold}")
    print(f"Model  -> Opus 4.8 optimizer / Sonnet 4.6 evaluator (independent judge)\n")

    if args.dry_run:
        print("DRY RUN — tasks that would run:\n")
        for t in tasks:
            print(f"  [{t['id']:02d}] [{t['category']:12s}] {t['title']}")
        return

    results = []
    for i, task in enumerate(tasks, 1):
        slug = slugify(task["title"], task["id"])
        out_file = out_dir / f"{slug}.md"

        if args.resume and proposal_is_done(out_file, args.threshold):
            print(f"[{i}/{len(tasks)}] SKIP (converged): {task['title']}")
            continue

        print(f"\n[{i}/{len(tasks)}] TASK {task['id']:02d}: {task['title']}  [{task['category']}]")
        print(f"  Context files: {', '.join(task.get('context_files', []))}")

        try:
            # Run the task; if it fails specifically because a provider usage
            # limit / overload was hit, wait for the window to free up and retry
            # the same task (instead of recording a useless score-0 proposal).
            attempt = 0
            while True:
                result = run_task(task, out_dir, args.max_iterations, args.threshold)
                if hit_usage_limit(result) and attempt < args.limit_max_retries:
                    attempt += 1
                    resume_at = (datetime.datetime.now()
                                 + datetime.timedelta(minutes=args.limit_wait_min)
                                 ).strftime("%H:%M:%S")
                    print(f"  -> USAGE LIMIT / overload detected. Waiting "
                          f"{args.limit_wait_min:g} min (until ~{resume_at}), then retry "
                          f"{attempt}/{args.limit_max_retries}...")
                    time.sleep(args.limit_wait_min * 60)
                    continue
                break

            results.append(result)
            status = "CONVERGED" if result.get("converged") else "BEST"
            print(f"  -> {status}  score={result.get('score',0):.1f}  "
                  f"iters={result.get('iterations')}  "
                  f"time={result.get('elapsed_s',0):.0f}s"
                  + (f"  (after {attempt} limit-retry)" if attempt else ""))
            print(f"  -> Proposal: {result['out_file']}")
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Writing partial summary...")
            break
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {exc}")
            results.append({
                "task_id": task["id"], "title": task["title"],
                "category": task["category"],
                "score": 0, "converged": False, "iterations": 0,
                "elapsed_s": 0, "error": str(exc),
            })

    if results:
        write_summary(results, out_dir, args)

    print(f"\nDone. Review proposals in:\n  {out_dir}")
    print("Submit each proposal through the SAGE HITL approval gate - nothing was applied.")


if __name__ == "__main__":
    main()
