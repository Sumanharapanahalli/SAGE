#!/usr/bin/env python3
"""
SAGE Self-Audit — feature-by-feature Evaluator-Optimizer pass.

Gemini 3.5 Flash = EVALUATOR (critic, finds shortcomings, holds the bar)
Claude Code (Sonnet) = OPTIMIZER (proposes concrete improvements)

Each SAGE feature gets its own loop:
  1. Claude reads the source code and produces a full audit proposal
  2. Gemini scores the proposal: did it catch all real issues? are fixes concrete?
  3. Claude revises based on Gemini's feedback
  4. Repeat until Gemini passes (score >= threshold) or max_iterations hit
  5. Proposal saved to docs/proposals/SAGE-audit-YYYYMMDD/<feature-id>.md

Usage:
    python scripts/sage_audit.py                             # all 28 features
    python scripts/sage_audit.py --feature llm_gateway       # single feature
    python scripts/sage_audit.py --categories core,agents    # category filter
    python scripts/sage_audit.py --resume                    # skip done features
    python scripts/sage_audit.py --dry-run                   # catalog only, no LLM
    python scripts/sage_audit.py --max-iterations 4
    python scripts/sage_audit.py --threshold 8.5
    python scripts/sage_audit.py --gemini-model gemini-2.5-flash
"""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s  %(message)s",
)
logger = logging.getLogger("sage_audit")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Feature catalog — 28 features across 9 categories
# ---------------------------------------------------------------------------

FEATURES = [
    # ── core/src ─────────────────────────────────────────────────────────────
    {
        "id": "llm_gateway",
        "name": "LLM Gateway",
        "category": "core",
        "description": (
            "Multi-provider LLM singleton with thread lock. "
            "Supports Gemini CLI, Claude Code CLI, Claude API, Ollama. "
            "All agents call generate() through this module."
        ),
        "source_files": ["src/core/llm_gateway.py"],
        "criteria": (
            "Provider switching correctness, thread-lock coverage, "
            "timeout handling per provider, token count accuracy, "
            "error propagation (no silent swallows), provider fallback chain, "
            "model name validation vs KNOWN_MODELS, logging completeness, testability"
        ),
    },
    {
        "id": "project_loader",
        "name": "Project Loader",
        "category": "core",
        "description": (
            "Loads solution YAML triad (project.yaml, prompts.yaml, tasks.yaml). "
            "Singleton. Hot-reloads on solution switch. Injects skill_content. "
            "Exposes get_prompts(), get_tasks(), get_project()."
        ),
        "source_files": ["src/core/project_loader.py"],
        "criteria": (
            "YAML validation strictness, hot-reload atomicity (no partial load), "
            "skill injection correctness, missing-field error messages, "
            "singleton thread safety, solution isolation (no cross-solution bleed), "
            "SAGE_SOLUTIONS_DIR mount correctness"
        ),
    },
    {
        "id": "queue_manager",
        "name": "Queue Manager",
        "category": "core",
        "description": (
            "SQLite-backed persistent task queue. "
            "Task creation, status transitions, priority ordering, "
            "dead-letter handling, recovery after restart."
        ),
        "source_files": ["src/core/queue_manager.py"],
        "criteria": (
            "Persistence correctness across restarts, concurrency safety (WAL mode), "
            "priority ordering, dead-letter queue, schema migration, "
            "task expiry/TTL, valid status transitions (pending->running->done|failed), "
            "queue capacity limit handling"
        ),
    },
    {
        "id": "evaluator_optimizer",
        "name": "Evaluator-Optimizer Loop",
        "category": "core",
        "description": (
            "Agentic self-improvement loop: Claude optimizes, Gemini evaluates. "
            "Rubric sharpening, sandbox mode (no file writes), HITL output. "
            "Used for agent design and self-improvement."
        ),
        "source_files": ["src/core/evaluator_optimizer.py"],
        "criteria": (
            "Sandbox completeness (disallowed tools enforced), "
            "rubric sharpening value, JSON parse robustness (malformed evaluator output), "
            "convergence: score threshold vs pass flag priority, "
            "retry-once on empty optimizer response, history completeness, "
            "provider build failure graceful handling"
        ),
    },
    {
        "id": "collective_memory",
        "name": "Collective Memory",
        "category": "core",
        "description": (
            "Git-backed cross-solution knowledge sharing. "
            "Learnings, help requests, semantic search across all solutions on a host. "
            "Operator actions bypass HITL; agent publishes go through proposals."
        ),
        "source_files": ["src/core/collective_memory.py"],
        "criteria": (
            "Git persistence correctness (commit on write), "
            "semantic search relevance, cross-solution isolation, "
            "help request lifecycle (claim/respond/close), "
            "stale learning eviction, concurrent write safety, "
            "graceful degradation when git is unavailable"
        ),
    },
    {
        "id": "constitution",
        "name": "Constitution",
        "category": "core",
        "description": (
            "Per-solution blue book: principles, constraints, voice, decision rules. "
            "Injected into all agent prompts via UniversalAgent. "
            "Versioned. Agent-proposed changes go through yaml_edit HITL gate."
        ),
        "source_files": ["src/core/constitution.py"],
        "criteria": (
            "Injection completeness (every agent call gets constitution), "
            "version history correctness, constraint enforcement at injection time, "
            "conflict detection with prompts.yaml system prompts, "
            "HITL gate for agent-proposed constitution changes, "
            "empty/missing constitution graceful handling (non-blocking)"
        ),
    },
    {
        "id": "build_orchestrator",
        "name": "Build Orchestrator",
        "category": "core",
        "description": (
            "Orchestrates multi-agent build pipelines. "
            "Decomposes build goals into parallel/sequential waves. "
            "Dispatches to UniversalAgent roles. Used by startup solution."
        ),
        "source_files": ["src/core/build_orchestrator.py"],
        "criteria": (
            "Wave parallelism correctness (independent tasks run concurrently), "
            "dependency resolution, failure handling (wave abort vs continue), "
            "HITL preservation (proposals not auto-applied), "
            "agent dispatch accuracy, output aggregation, "
            "timeout management per wave, audit trail completeness"
        ),
    },
    # ── agents ────────────────────────────────────────────────────────────────
    {
        "id": "analyst_agent",
        "name": "Analyst Agent",
        "category": "agents",
        "description": (
            "Triages log entries, errors, and events. "
            "Returns structured JSON with severity, root cause hypothesis, "
            "and recommended action. Memory-retrieval augmented."
        ),
        "source_files": ["src/agents/analyst.py"],
        "criteria": (
            "Prompt quality (specific enough to be useful), "
            "severity classification accuracy (RED/AMBER/GREEN/UNKNOWN), "
            "fallback for LLM failure (not a bare except), "
            "memory retrieval integration, structured output conformance, "
            "domain-blind design (no hardcoded solution logic), "
            "audit logging for every analysis event"
        ),
    },
    {
        "id": "developer_agent",
        "name": "Developer Agent (ReAct)",
        "category": "agents",
        "description": (
            "Code review, MR creation, autonomous implementation via ReAct loop. "
            "The ONLY agent with direct tool access (bash/file via Claude Code CLI). "
            "Uses _react_loop() for multi-step reasoning."
        ),
        "source_files": ["src/agents/developer.py"],
        "criteria": (
            "ReAct loop termination conditions (no infinite loop), "
            "tool call safety (no destructive ops without confirmation), "
            "code review prompt completeness (security, perf, style), "
            "MR format compliance (title length, required sections), "
            "HITL preservation (output is proposal, never auto-applied), "
            "error handling for failed tool calls mid-loop"
        ),
    },
    {
        "id": "monitor_agent",
        "name": "Monitor Agent",
        "category": "agents",
        "description": (
            "Classifies events from CI/CD, crash reporters, webhooks. "
            "Returns severity, requires_action bool, suggested_task_type. "
            "High-throughput: may process many events per minute."
        ),
        "source_files": ["src/agents/monitor.py"],
        "criteria": (
            "Classification accuracy across event types, "
            "event schema flexibility (no hardcoded field names), "
            "false positive rate (not every event is CRITICAL), "
            "suggested_task_type constrained to valid task types, "
            "domain-blind design, debounce/rate limiting for noisy event streams, "
            "audit logging without overwhelming the log"
        ),
    },
    {
        "id": "planner_agent",
        "name": "Planner Agent",
        "category": "agents",
        "description": (
            "Decomposes natural language requests into atomic, executable task sequences. "
            "Task types dynamically loaded from solutions/*/tasks.yaml. "
            "Identifies parallel waves (independent tasks run together)."
        ),
        "source_files": ["src/agents/planner.py"],
        "criteria": (
            "Decomposition granularity (tasks are atomic, not too large), "
            "VALID_TASK_TYPES enforcement (no hallucinated task types), "
            "dependency detection correctness, "
            "parallel wave identification (truly independent tasks), "
            "JSON array output conformance, "
            "fallback when task type is unknown, "
            "max task count/depth safety limit"
        ),
    },
    {
        "id": "universal_agent",
        "name": "Universal Agent",
        "category": "agents",
        "description": (
            "Generic YAML-driven role dispatch. "
            "Injects system_prompt + skill.md + constitution + long-term memory "
            "+ collective intelligence at call time. "
            "All startup solution roles run through this."
        ),
        "source_files": ["src/agents/universal.py"],
        "criteria": (
            "Role dispatch correctness (role_id -> role_cfg), "
            "injection order (constitution before memory before task), "
            "missing role error message quality, "
            "output structure enforcement (all 6 JSON fields present), "
            "each memory/constitution injection is non-blocking (try/except), "
            "execute() method parity with run() (same logic, different signature), "
            "audit logging completeness"
        ),
    },
    {
        "id": "product_owner_agent",
        "name": "Product Owner Agent",
        "category": "agents",
        "description": (
            "Converts 'I want a fitness app' into structured product backlogs. "
            "3-phase LLM loop: analyze -> clarify -> create backlog. "
            "Outputs MoSCoW-prioritized user stories with acceptance criteria."
        ),
        "source_files": ["src/agents/product_owner.py"],
        "criteria": (
            "Interview prompt quality (5W1H coverage), "
            "MoSCoW prioritization correctness, "
            "INVEST criteria applied to user stories, "
            "acceptance criteria specificity (Given-When-Then format), "
            "refine_backlog() and prioritize_stories() are stubs (pass) — CRITICAL gap, "
            "integration path with HITL approval gate (where does backlog go?), "
            "audit logging for requirements_gathered event"
        ),
    },
    {
        "id": "critic_agent",
        "name": "Critic Agent",
        "category": "agents",
        "description": (
            "Reviews agent proposals before they enter the HITL approval queue. "
            "Adds an AI pre-screening layer between agent output and human decision. "
            "Catches obviously wrong or unsafe proposals early."
        ),
        "source_files": ["src/agents/critic.py"],
        "criteria": (
            "Critique depth vs speed trade-off, "
            "false negative rate (bad proposals that slip through), "
            "false positive rate (good proposals wrongly flagged), "
            "structured critique output format, "
            "domain-agnostic critique (no hardcoded solution assumptions), "
            "integration with approval gate API, "
            "handling proposal types: yaml_edit vs code_diff vs implementation_plan"
        ),
    },
    {
        "id": "coder_agent",
        "name": "Coder Agent",
        "category": "agents",
        "description": (
            "Autonomous code generation. "
            "Produces unified diffs or complete file implementations. "
            "Distinct from DeveloperAgent (which does review + ReAct)."
        ),
        "source_files": ["src/agents/coder.py"],
        "criteria": (
            "Code quality (idiomatic, typed, no bare excepts), "
            "test generation alongside implementation, "
            "unified diff format correctness, "
            "context window management for large files, "
            "HITL preservation (all output is proposals, never auto-applied), "
            "clear responsibility boundary vs DeveloperAgent, "
            "language/framework awareness from project.yaml"
        ),
    },
    # ── api ───────────────────────────────────────────────────────────────────
    {
        "id": "api_endpoints",
        "name": "FastAPI Endpoints",
        "category": "api",
        "description": (
            "All HTTP endpoints: config, llm, agent, approvals, onboarding, "
            "health, yaml, collective, agents, improvements. "
            "Single FastAPI app on port 8000. CORS enabled for localhost:5173."
        ),
        "source_files": ["src/interface/api.py"],
        "criteria": (
            "Endpoint completeness (all documented routes implemented), "
            "Pydantic response models (typed, not dict), "
            "input validation (no raw user strings to shell/SQL), "
            "error response consistency ({error, detail, trace_id}), "
            "request-ID propagation through to audit log, "
            "rate limiting on agent-run endpoints, "
            "health endpoint richness (LLM status, queue depth, version), "
            "OpenAPI docs accurate and complete"
        ),
    },
    # ── memory ────────────────────────────────────────────────────────────────
    {
        "id": "audit_logger",
        "name": "Audit Logger",
        "category": "memory",
        "description": (
            "Append-only SQLite event log. "
            "Records every agent action, approval, rejection with actor, "
            "trace_id, input, output, and timestamp. "
            "Compliance record AND training signal for self-improvement."
        ),
        "source_files": ["src/memory/audit_logger.py"],
        "criteria": (
            "Append-only enforcement (no UPDATE/DELETE on event rows), "
            "schema completeness (all required fields present), "
            "query performance on large logs (indexes on trace_id, actor, timestamp), "
            "trace_id linkage across multi-step flows, "
            "retention policy (no unbounded growth), "
            "concurrent write safety (WAL or single writer), "
            "export/query API, PII field handling"
        ),
    },
    {
        "id": "vector_store",
        "name": "Vector Store",
        "category": "memory",
        "description": (
            "ChromaDB semantic search over past analyses, human corrections, "
            "domain decisions. Queried by every agent call for relevant context. "
            "Minimal-mode fallback (no ChromaDB) for low-RAM machines."
        ),
        "source_files": ["src/memory/vector_store.py"],
        "criteria": (
            "Embedding quality (right model, right chunk size), "
            "retrieval relevance (top-k tuning), "
            "collection isolation per solution (no cross-contamination), "
            "minimal-mode fallback correctness, "
            "staleness handling (old corrections from deprecated solutions), "
            "concurrent access safety, "
            "storage size cap and pruning strategy"
        ),
    },
    # ── modules ───────────────────────────────────────────────────────────────
    {
        "id": "nano_modules",
        "name": "Nano-Modules",
        "category": "modules",
        "description": (
            "Five zero-dependency utilities injected across the framework: "
            "severity classifier, JSON extractor, trace ID generator, "
            "payload validator, event bus."
        ),
        "source_files": [
            "src/modules/severity.py",
            "src/modules/json_extractor.py",
            "src/modules/trace_id.py",
            "src/modules/payload_validator.py",
            "src/modules/event_bus.py",
        ],
        "criteria": (
            "Truly zero external dependencies (importable standalone), "
            "severity: all label variants handled (case-insensitive), "
            "json_extractor: nested objects, truncated JSON, multi-fence, "
            "trace_id: cryptographically random, sortable, URL-safe, "
            "payload_validator: schema inference completeness, "
            "event_bus: thread safety, backpressure, subscriber error isolation"
        ),
    },
    # ── ui ────────────────────────────────────────────────────────────────────
    {
        "id": "ui_agents_page",
        "name": "UI — Agents Page",
        "category": "ui",
        "description": (
            "Runs any UniversalAgent role from the web UI. "
            "Role picker dropdown, task text input, structured result display "
            "(summary, analysis, recommendations, next_steps, severity badge)."
        ),
        "source_files": ["web/src/pages/Agents.tsx"],
        "criteria": (
            "Role loading (handles 0 roles empty state), "
            "loading skeleton during LLM call, "
            "all 6 result fields displayed (including severity + confidence), "
            "severity color coding (RED=red, AMBER=yellow, GREEN=green), "
            "copy-to-clipboard for recommendations, "
            "aria-labels for screen readers, "
            "error state on API failure"
        ),
    },
    {
        "id": "ui_llm_settings",
        "name": "UI — LLM Settings",
        "category": "ui",
        "description": (
            "4-provider switcher with current provider status, model display, "
            "session token usage statistics. Switch persists across page reloads."
        ),
        "source_files": ["web/src/pages/LLMSettings.tsx"],
        "criteria": (
            "Switch feedback (spinner + success/error toast), "
            "token usage accuracy (matches backend state), "
            "model name display per provider, "
            "loading state during switch (button disabled), "
            "provider health check integration, "
            "usage stats reset on session end"
        ),
    },
    {
        "id": "ui_improvements",
        "name": "UI — Improvements Page",
        "category": "ui",
        "description": (
            "Two-tab backlog: Solution features (scope=solution) and "
            "SAGE framework ideas (scope=sage). "
            "Feature request submission with priority and description."
        ),
        "source_files": ["web/src/pages/Improvements.tsx"],
        "criteria": (
            "Scope tab separation strictly enforced (no mixing), "
            "feature request form: required fields validated, "
            "GitHub issue link shown for sage-scope items, "
            "MoSCoW priority display and filter, "
            "empty state for each tab, "
            "submission confirmation with audit trail"
        ),
    },
    {
        "id": "ui_settings",
        "name": "UI — Settings Page",
        "category": "ui",
        "description": (
            "Branding, typography, layout density, accent color picker, "
            "dark mode toggle. All settings persisted to localStorage. "
            "Live preview as user changes values."
        ),
        "source_files": ["web/src/pages/Settings.tsx"],
        "criteria": (
            "localStorage persistence correctness (survives reload), "
            "real-time preview (CSS variables update immediately), "
            "reset-to-defaults restores all values, "
            "dark mode toggle applies html.dark class immediately, "
            "branding field validation (max length, allowed chars), "
            "export/import settings as JSON"
        ),
    },
    {
        "id": "ui_yaml_editor",
        "name": "UI — YAML Editor",
        "category": "ui",
        "description": (
            "Live edit of solution YAML files (project.yaml, prompts.yaml, tasks.yaml) "
            "with syntax validation before save and hot-reload trigger."
        ),
        "source_files": ["web/src/pages/YAMLEditor.tsx"],
        "criteria": (
            "Syntax validation before every save (invalid YAML blocked), "
            "hot-reload confirmation (agent sees new YAML immediately), "
            "diff preview between saved and in-editor versions, "
            "unsaved-changes warning on navigation away, "
            "error display line number for invalid YAML, "
            "undo/redo history"
        ),
    },
    {
        "id": "ui_layout",
        "name": "UI — Layout (Header + Sidebar)",
        "category": "ui",
        "description": (
            "Header: solution switcher dropdown, Stop SAGE button. "
            "Sidebar: grouped navigation pages with active state and icons. "
            "Module registry for page discovery."
        ),
        "source_files": [
            "web/src/components/layout/Header.tsx",
            "web/src/components/layout/Sidebar.tsx",
        ],
        "criteria": (
            "Solution switch: confirm dialog if unsaved state, "
            "Stop button: confirm before killing backend+frontend, "
            "active nav state: correct on direct URL navigation, "
            "keyboard navigation: Tab + Enter works on sidebar items, "
            "solution name truncation for long names, "
            "mobile responsiveness: sidebar collapses"
        ),
    },
    # ── solutions ─────────────────────────────────────────────────────────────
    {
        "id": "solution_yaml_design",
        "name": "Solution YAML Contract (starter template)",
        "category": "solutions",
        "description": (
            "The three-file solution contract evaluated via the starter template. "
            "project.yaml: domain declaration. "
            "prompts.yaml: agent thinking (analyst, developer, planner, monitor, roles). "
            "tasks.yaml: task type registry."
        ),
        "source_files": ["solutions/starter/prompts.yaml"],
        "criteria": (
            "Role definition completeness (all standard + custom roles present), "
            "system prompt quality (specific, structured JSON output requirement), "
            "task type coverage for common use cases, "
            "JSON output schema conformance (all required keys defined), "
            "extensibility: adding a new role needs only YAML (no Python changes), "
            "in-YAML documentation quality (comments explain each section)"
        ),
    },
    # ── gym ───────────────────────────────────────────────────────────────────
    {
        "id": "agent_gym",
        "name": "AgentGym",
        "category": "gym",
        "description": (
            "Self-play training platform. 661+ seed exercises across 11 domains. "
            "Glicko-2 ratings per agent-skill pair. "
            "3-tier grading: experimental (40%) + LLM critic (30%) + structural (30%). "
            "Spaced repetition for weakness targeting."
        ),
        "source_files": [".claude/docs/features/agent-gym.md"],
        "criteria": (
            "Domain coverage gaps (what's missing from 11 domains), "
            "grading tier balance (40/30/30 justified?), "
            "Glicko-2 implementation correctness (rating deviation decay), "
            "spaced repetition algorithm (weakness targeting logic), "
            "exercise difficulty calibration (novice to expert progression), "
            "LLM critic prompt quality, "
            "tool access requirements per exercise vs what agents actually have"
        ),
    },
    # ── ops ───────────────────────────────────────────────────────────────────
    {
        "id": "makefile_ops",
        "name": "Makefile & Launch Scripts",
        "category": "ops",
        "description": (
            "Makefile with venv-aware targets (uses .venv/Scripts/python). "
            "sage-launcher.vbs: silent launcher (no terminal windows). "
            "sage.bat: calls sage-launcher.vbs. "
            "VS Code extension: iframe to web UI."
        ),
        "source_files": ["Makefile"],
        "criteria": (
            "Target completeness (all documented targets exist), "
            "cross-platform correctness (Windows .venv\\Scripts vs Linux .venv/bin), "
            "missing dependency detection and helpful error messages, "
            "silent launcher reliability (no zombie processes), "
            "port conflict detection before starting servers, "
            "make test-all target correctness"
        ),
    },
]


# ---------------------------------------------------------------------------
# Context loading
# ---------------------------------------------------------------------------

MAX_FILE_CHARS = 10_000  # per file — keeps token count manageable


def load_context(feature: dict) -> str:
    parts = []
    for rel in feature["source_files"]:
        full = ROOT / rel
        if not full.exists():
            parts.append(
                f"### {rel}\n[FILE NOT FOUND — feature may not be implemented yet]\n"
            )
            continue
        text = full.read_text(encoding="utf-8", errors="replace")
        if len(text) > MAX_FILE_CHARS:
            text = (
                text[:MAX_FILE_CHARS]
                + f"\n\n... [truncated — {len(text) - MAX_FILE_CHARS} chars omitted]"
            )
        parts.append(f"### {rel}\n```\n{text}\n```")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

TASK_TEMPLATE = """\
# SAGE Feature Audit: {name}

## What This Feature Does
{description}

## Current Implementation
{context}

---

## Your Task

You are a senior engineer auditing the SAGE framework. Produce a structured proposal \
Markdown document covering ALL shortcomings in the above implementation.

### Section 1 — Findings Table
| # | Shortcoming | Severity | Location | Root Cause |
|---|---|---|---|---|

Severity levels:
- **CRITICAL** — incorrect behaviour, data loss risk, HITL gate bypass, or safety violation
- **IMPORTANT** — degrades reliability, observability, or developer experience significantly
- **MINOR** — style, documentation, or ergonomics issue

### Section 2 — Detailed Fixes
For each CRITICAL or IMPORTANT finding, provide:
- The specific change needed (show actual code/YAML/config, not just a description)
- Why this matters in the context of SAGE's five laws

### Section 3 — Test Plan
Bullet list of what to verify after applying the fixes. \
Include specific pytest test names or UI interaction steps.

### Section 4 — Effort Estimate
Rough effort for each fix: S (< 2h), M (half day), L (1-2 days), XL (> 2 days)

---

## SAGE Laws to Check Against (violations are CRITICAL findings)

1. **Agents propose, humans decide** — HITL approval gate must never be bypassed
2. **Domain-blind src/** — no solution-specific logic anywhere in src/
3. **Audit logging** — every significant agent action must be logged
4. **No bare `except:` clauses** — always catch specific exceptions
5. **No `print()`** — use `self.logger` or `logging.getLogger()`
6. **Type hints** — all public methods must have type annotations
7. **Tests required** — all new behaviour needs a test
"""

CRITERIA_TEMPLATE = """\
{feature_criteria}

---

Scoring deductions (each applies -1 to -3 points):
- Shortcoming described vaguely ("could be improved") instead of specifically (-2)
- Fix described in prose but no code shown for a code-level issue (-2)
- Severity CRITICAL vs IMPORTANT vs MINOR clearly mislabelled (-1 per instance)
- SAGE law violated in the proposed fixes themselves (-3 per violation)
- Significant gap a senior engineer would catch that is missing entirely (-3)

Score >= 8 only when:
- All CRITICAL shortcomings have concrete, copy-pasteable fixes
- Severity triage is accurate and justified
- Every fix respects SAGE's five laws
- Test plan is specific (named tests, not "add more tests")
"""


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def save_proposal(out_dir: Path, feature: dict, result: dict) -> Path:
    slug = feature["id"]
    out_file = out_dir / f"{slug}.md"
    score = result.get("score", 0.0)
    converged = result.get("converged", False)
    iterations = result.get("iterations", 0)

    history_lines = []
    for h in result.get("history", []):
        fb = (h.get("feedback") or "").replace("\n", " ")[:140]
        history_lines.append(
            f"- **Iter {h['iteration']}** score={h['score']} pass={h['passed']}  \n"
            f"  Gemini: _{fb}_"
        )

    content = (
        f"# SAGE Audit Proposal: {feature['name']}\n\n"
        f"**Category:** `{feature['category']}`  \n"
        f"**Score:** {score:.1f}/10  \n"
        f"**Converged:** {'yes' if converged else 'no'} "
        f"({iterations} iteration{'s' if iterations != 1 else ''})  \n"
        f"**Status:** pending_review — submit to `/approvals/submit` after human review\n\n"
        "## Gemini Evaluation History\n\n"
        + ("\n".join(history_lines) or "_(no history)_")
        + "\n\n---\n\n## Claude's Proposal\n\n"
        + (result.get("final") or "_(no output generated)_")
        + "\n"
    )
    out_file.write_text(content, encoding="utf-8")
    return out_file


def save_summary(out_dir: Path, results: list) -> Path:
    out_file = out_dir / "_summary.md"
    by_score = sorted(results, key=lambda r: r["score"])
    total = len(results)
    passed = sum(1 for r in results if r["converged"])
    avg = sum(r["score"] for r in results) / total if total else 0

    lines = [
        "# SAGE Self-Audit Summary",
        f"\n**Date:** {date.today()}  ",
        f"**Features audited:** {total}  ",
        f"**Converged (score >= threshold):** {passed}/{total}  ",
        f"**Average score:** {avg:.1f}/10  ",
        "",
        "## Findings by Score — Lowest First (most improvement needed)",
        "",
        "| Feature | Category | Score | Conv | Iters |",
        "|---|---|---|---|---|",
    ]
    for r in by_score:
        f = r["feature"]
        conv = "yes" if r["converged"] else "no"
        lines.append(
            f"| [{f['name']}]({f['id']}.md) | {f['category']} "
            f"| **{r['score']:.1f}** | {conv} | {r['iterations']} |"
        )

    lines += [
        "",
        "## Priority Queue",
        "",
        "Apply proposals in score order — lowest score = most critical shortcomings found.",
        "Each proposal file has a Section 4 effort estimate.",
        "",
        "Submit approved proposals via:",
        "```bash",
        "# Review proposal, then:",
        "curl -X POST http://localhost:8000/approvals/submit \\",
        '  -H "Content-Type: application/json" \\',
        '  -d \'{"proposal_type": "implementation_plan", "content": "<paste proposal>"}\'',
        "```",
    ]
    out_file.write_text("\n".join(lines), encoding="utf-8")
    return out_file


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="SAGE self-audit: Gemini Flash critiques, Claude proposes fixes"
    )
    ap.add_argument("--feature", help="Run only this feature ID (e.g. llm_gateway)")
    ap.add_argument(
        "--categories", help="Comma-separated categories (e.g. core,agents,ui)"
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="Skip features whose output file already exists",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Print catalog only — no LLM calls"
    )
    ap.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Max loop iterations per feature (default: 3)",
    )
    ap.add_argument(
        "--threshold",
        type=float,
        default=8.0,
        help="Gemini pass score 0-10 (default: 8.0)",
    )
    ap.add_argument(
        "--gemini-model",
        default="gemini-3.5-flash",
        help="Gemini evaluator model (default: gemini-3.5-flash)",
    )
    ap.add_argument(
        "--claude-model",
        default="claude-sonnet-4-6",
        help="Claude optimizer model (default: claude-sonnet-4-6)",
    )
    args = ap.parse_args(argv)

    # Apply filters
    features = list(FEATURES)
    if args.feature:
        features = [f for f in features if f["id"] == args.feature]
        if not features:
            ids = [f["id"] for f in FEATURES]
            logger.error("Unknown feature: %s\nAvailable: %s", args.feature, ids)
            return 1
    if args.categories:
        cats = {c.strip() for c in args.categories.split(",")}
        features = [f for f in features if f["category"] in cats]
        if not features:
            avail = sorted({f["category"] for f in FEATURES})
            logger.error("No features in categories %s. Available: %s", cats, avail)
            return 1

    # Output directory
    out_dir = ROOT / "docs" / "proposals" / f"SAGE-audit-{date.today()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("SAGE Self-Audit")
    logger.info("  Features   : %d", len(features))
    logger.info("  Evaluator  : %s (Gemini critic)", args.gemini_model)
    logger.info("  Optimizer  : claude-code/%s", args.claude_model)
    logger.info(
        "  Iterations : %d max, threshold %.1f", args.max_iterations, args.threshold
    )
    logger.info("  Output     : %s", out_dir)

    # Dry run — just print catalog
    if args.dry_run:
        cats = {}
        for f in features:
            cats.setdefault(f["category"], []).append(f)
        for cat, fs in cats.items():
            print(f"\n[{cat.upper()}]")
            for f in fs:
                files = ", ".join(f["source_files"])
                print(f"  {f['id']:30s}  {f['name']}")
                print(f"  {'':30s}  files: {files}")
        print(f"\nTotal: {len(features)} features across {len(cats)} categories")
        return 0

    from src.core.evaluator_optimizer import EvaluatorOptimizerRunner

    all_results = []

    for i, feature in enumerate(features, 1):
        out_file = out_dir / f"{feature['id']}.md"

        if args.resume and out_file.exists():
            logger.info("[%d/%d] SKIP (resume): %s", i, len(features), feature["id"])
            continue

        logger.info("[%d/%d] Auditing: %s", i, len(features), feature["name"])

        # Build task with source code baked in
        context_text = load_context(feature)
        task = TASK_TEMPLATE.format(
            name=feature["name"],
            description=feature["description"],
            context=context_text,
        )
        criteria = CRITERIA_TEMPLATE.format(feature_criteria=feature["criteria"])

        # Runner: Gemini Flash evaluator + Claude Code optimizer (sandboxed)
        runner = EvaluatorOptimizerRunner(
            {
                "optimizer": {
                    "provider": "claude-code",
                    "model": args.claude_model,
                    "timeout": 600,
                },
                "evaluator": {
                    "provider": "gemini",
                    "model": args.gemini_model,
                    "timeout": 180,
                },
                "criteria": criteria,
                "max_iterations": args.max_iterations,
                "score_threshold": args.threshold,
                "generate_rubric": True,  # Gemini sharpens its own rubric before judging
                "sandbox": True,  # optimizer cannot write files
            }
        )

        result = runner.run(task)  # context already embedded in task string

        entry = {
            "feature": feature,
            "score": result.get("score", 0.0),
            "converged": result.get("converged", False),
            "iterations": result.get("iterations", 0),
        }
        all_results.append(entry)

        saved = save_proposal(out_dir, feature, result)
        logger.info(
            "  score=%.1f  converged=%s  iters=%d  -> %s",
            entry["score"],
            entry["converged"],
            entry["iterations"],
            saved.name,
        )

        if "error" in result:
            logger.warning("  loop error: %s", result["error"])

    # Final summary
    if all_results:
        summary = save_summary(out_dir, all_results)
        avg = sum(r["score"] for r in all_results) / len(all_results)
        worst = min(all_results, key=lambda r: r["score"])
        logger.info("")
        logger.info("Done: %d features audited", len(all_results))
        logger.info("  Average score : %.1f / 10", avg)
        logger.info(
            "  Most critical : %s (%.1f)", worst["feature"]["name"], worst["score"]
        )
        logger.info(
            "  Converged     : %d / %d",
            sum(1 for r in all_results if r["converged"]),
            len(all_results),
        )
        logger.info("  Summary       : %s", summary)
        logger.info("")
        logger.info("Review proposals in: %s", out_dir)
        logger.info("Apply approved proposals via POST /approvals/submit")

    return 0


if __name__ == "__main__":
    sys.exit(main())
