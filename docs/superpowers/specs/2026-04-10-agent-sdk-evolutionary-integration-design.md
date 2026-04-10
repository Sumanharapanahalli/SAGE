# Agent SDK + Evolutionary Layer + Regulatory Primitives — Design Spec

**Date:** 2026-04-10
**Status:** Draft (pending user review)
**Scope:** SAGE Framework enhancement — integrate Claude Agent SDK, add AlphaEvolve-style evolutionary layer, and fold in medical device CDS regulatory primitives

---

## 1. Overview

This spec defines an enhancement to the SAGE Framework that:

1. **Augments existing agents** with the Claude Agent SDK (`claude-agent-sdk`) — giving SAGE agents real file editing, code search, web search, subagent parallelism, and session continuity when Claude Code is the active LLM provider.
2. **Adds an evolutionary layer** inspired by DeepMind's AlphaEvolve (arXiv 2506.13131) — enabling automatic improvement of prompts, code, and build plans via mutation → evaluation → selection loops.
3. **Folds in regulatory primitives** for medical device Clinical Decision Support (CDS) compliance — intended purpose specification, FDA 4-part transparency, automation bias controls, and gold-standard clinical evaluation.

All three capabilities are **opt-in per solution** and preserve SAGE's domain-blind framework core, multi-provider LLM flexibility, HITL gates, and compliance invariants.

---

## 2. Goals & Non-Goals

### Goals

- Leverage Agent SDK's built-in tool execution (Read/Edit/Write/Bash/Glob/Grep/WebSearch) when Claude Code is active, while preserving current ReAct fallback for other providers.
- Enable AlphaEvolve-style evolutionary improvement of prompts, code, and build plans with HITL boundaries at start (goal alignment) and end (result approval).
- Reduce HITL friction: replace per-tool-call gates with two meaningful gates (goal + result) while preserving Law 1.
- Add first-class regulatory primitives to support medical device CDS solutions without coupling framework core to any domain.
- Maintain all existing SAGE invariants: compliance audit trail, compounding intelligence, domain isolation, graceful degradation.

### Non-Goals

- **No replacement of the LLM gateway.** The gateway remains primary; the SDK is an accelerator when Claude Code is active.
- **No breaking changes** to existing agent APIs or solution YAML configs (new fields are additive).
- **No forced adoption.** Solutions that don't set `agent_sdk.enabled: true` work exactly as they do today.
- **No API key requirement.** The SDK uses Claude Code CLI authentication — no separate `ANTHROPIC_API_KEY`.
- **No bypass of Law 1.** Goal and result gates preserve human decision authority; destructive ops still hard-block.

---

## 3. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        SAGE Framework                           │
│                                                                  │
│   ┌──────────────┐     ┌─────────────────┐    ┌──────────────┐  │
│   │ SAGE Agents  │────▶│ AgentSDKRunner  │───▶│ Claude Agent │  │
│   │ (Universal,  │     │   (bridge)      │    │     SDK      │  │
│   │  Coder,      │     └────────┬────────┘    └──────┬───────┘  │
│   │  Analyst…)   │              │                    │          │
│   └──────┬───────┘              │ fallback           │ hooks    │
│          │                      ▼                    ▼          │
│          │              ┌──────────────┐    ┌──────────────┐    │
│          └─────────────▶│ LLM Gateway  │    │  SDK Hooks   │    │
│                         │ (existing)   │    │ (compliance) │    │
│                         └──────────────┘    └──────┬───────┘    │
│                                                    │            │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │         Compliance Infrastructure (existing)            │  │
│   │  Proposal Store │ Audit Logger │ Cost Tracker │ Vector  │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │            Evolutionary Layer (new)                     │  │
│   │   EvolutionOrchestrator → ProgramDatabase               │  │
│   │   PromptEvolver │ CodeEvolver │ BuildEvolver            │  │
│   │   Ensemble of Evaluators (incl. GoldStandardEvaluator)  │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │         Regulatory Primitives (new, opt-in)             │  │
│   │   IntendedPurpose │ FDAClassifier │ Transparency        │  │
│   │   AutomationBiasControls │ GoldStandardEvaluator        │  │
│   └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Component Design

### 4.1 AgentSDKRunner (`src/core/agent_sdk_runner.py`)

Bridge layer between SAGE agents and the Claude Agent SDK. All SAGE agents route their LLM calls through this runner.

**Core interface:**

```python
class AgentSDKRunner:
    def is_sdk_available(self) -> bool:
        """True when claude_agent_sdk is installed AND active provider is claude-code."""

    async def run(self, role_id: str, task: str, context: dict) -> dict:
        """Execute a SAGE agent role. Uses SDK if available, else falls back to gateway."""

    async def run_with_evolution(
        self,
        role_id: str,
        task: str,
        evolver_type: Literal["prompt", "code", "build"],
        config: EvolutionConfig,
    ) -> dict:
        """Evolutionary execution via the EvolutionOrchestrator."""
```

**Role translation:** SAGE role definitions from `prompts.yaml` are mapped to SDK `AgentDefinition` objects. Task types drive `allowed_tools` selection.

**Task type → SDK tool mapping:**

| SAGE Task Type | SDK Tools |
|---|---|
| `analysis`, `review` | `Read`, `Grep`, `Glob` |
| `code_review`, `implementation` | `Read`, `Edit`, `Write`, `Grep`, `Glob` |
| `code_generation`, `testing` | `Read`, `Edit`, `Write`, `Bash`, `Grep`, `Glob` |
| `research`, `investigation` | `Read`, `Grep`, `Glob`, `WebSearch`, `WebFetch` |
| `planning`, `decomposition` | `Read`, `Grep`, `Glob`, `Agent` |

**Graceful degradation:** When `is_sdk_available()` returns `False`, `run()` delegates to the existing `llm_gateway.generate()` ReAct path — zero behavior change for non-Claude-Code providers.

### 4.2 SDK Hooks (`src/core/sdk_hooks.py`)

Translates SAGE compliance infrastructure into Agent SDK hook callbacks.

**Hook assignments:**

```
PreToolUse:
  - budget_check_hook       → cost_tracker (DENIES on budget exceeded)
  - pii_filter_hook         → scrub sensitive data
  - data_residency_hook     → region enforcement
  - destructive_op_hook     → HARD BLOCK rm -rf, DROP TABLE, force-push

PostToolUse:
  - audit_logger_hook       → compliance_audit_log write
  - cost_record_hook        → track actual spend
  - change_tracker_hook     → accumulate file changes for Gate 2

SubagentStop:
  - evolution_scorer_hook   → score subagent output, feed ProgramDatabase
  - audit_subagent_hook     → log with parent trace_id correlation

Stop:
  - result_approval_hook    → trigger Gate 2 (result approval)
```

**Observational vs blocking:** Per revised HITL model (§5), most hooks are observational. Only budget, PII, data residency, and destructive ops block mid-execution.

### 4.3 Evolutionary Layer (`src/core/evolution/`)

AlphaEvolve-inspired evolutionary improvement. Three evolvers share a common `ProgramDatabase` and `EvolutionOrchestrator`.

**Files:**

- `orchestrator.py` — `EvolutionOrchestrator` — main evolutionary loop
- `program_db.py` — `ProgramDatabase` — SQLite-backed candidate store
- `candidate.py` — `Candidate` dataclass
- `prompt_evolver.py` — `PromptEvolver`
- `code_evolver.py` — `CodeEvolver`
- `build_evolver.py` — `BuildEvolver`
- `evaluators.py` — Ensemble of evaluators (including `GoldStandardEvaluator`)

**Candidate schema:**

```python
@dataclass
class Candidate:
    id: str
    content: str          # prompt text, code, or build plan JSON
    candidate_type: Literal["prompt", "code", "build_plan"]
    fitness: float        # 0.0–1.0 normalized
    parent_ids: list[str] # lineage
    generation: int
    metadata: dict        # per-evaluator scores, mutation description
    created_at: datetime
```

**ProgramDatabase:**

- SQLite at `solutions/<name>/.sage/evolution.db` (per-solution isolation)
- Tournament selection for parent sampling (bias to high fitness, preserve diversity)
- Pruning: keep top-N + diversity sample
- Lineage tracking for full audit trail

**Dual-model strategy (AlphaEvolve pattern):**

- **Breadth population:** Haiku subagents — fast, cheap, many mutations per generation
- **Depth refinement:** Opus subagents — applied to top-k candidates for focused improvement

**Evaluator weights:**

| Evolver | Evaluators | Weight |
|---|---|---|
| PromptEvolver | Agent success rate (audit log) | 0.4 |
| | Critic quality score | 0.3 |
| | Task completion rate | 0.2 |
| | Token efficiency | 0.1 |
| CodeEvolver | Test pass rate | 0.4 |
| | Critic code quality | 0.3 |
| | Spec correctness | 0.2 |
| | Complexity metric | 0.1 |
| BuildEvolver | Integration test pass rate | 0.3 |
| | Critic architecture score | 0.3 |
| | Cohesion metrics | 0.2 |
| | Build time/resources | 0.2 |

**GoldStandardEvaluator (regulatory primitive):** Compares candidate output against curated benchmark dataset (e.g., physician panel consensus for medtech solutions). Produces auditable clinical evaluation evidence suitable for FDA/notified-body submission.

### 4.4 Regulatory Primitives (`src/core/regulatory/`)

Opt-in compliance extensions for medical device CDS and similar regulated domains.

**Files:**

- `intended_purpose.py` — Schema + validator
- `fda_classifier.py` — Automated FDA CDS classifier (4-criterion test)
- `transparency_report.py` — Structured explainability schema
- `automation_bias.py` — Time-criticality controls

**4.4.1 Intended Purpose Schema**

Added to `solutions/<name>/project.yaml`:

```yaml
intended_purpose:
  function: "Triage support for emergency department prioritization"
  performance_claims:
    sensitivity: 0.92
    specificity: 0.88
    confidence_interval: "95%"
  target_population:
    age_range: [18, 85]
    exclusions: ["pregnancy", "pediatric"]
  boundary_conditions:
    - "Not for life-threatening time-critical decisions"
    - "Requires physician verification"
  user_group: "Board-certified ED physicians"
  fda_classification: "Non-Device CDS"
  mdr_class: "Class I"
  predicate_device: null
```

Validator runs at solution load time. Blocks task execution outside declared `boundary_conditions`.

**4.4.2 FDA 4-Part Transparency**

Every agent proposal must include a `transparency_report`:

```json
{
  "transparency_report": {
    "inputs_used": ["vital_signs.json", "lab_results_2024.csv"],
    "sources_cited": ["NICE Guideline CG87", "UpToDate 2024"],
    "logic_chain": ["step 1", "step 2", "conclusion"],
    "confidence": "HIGH",
    "user_verifiable": true,
    "automation_bias_warning": "Time-critical: verify before acting"
  }
}
```

Enforced via `transparency_validator_hook` on `PostToolUse`. Missing/incomplete reports cause rejection.

**4.4.3 FDA CDS Classifier**

New agent role `RegulatoryClassifierAgent` runs on solution setup and `intended_purpose` changes. Applies the 4-criterion test:

1. Not analyzing medical images/physiological signals
2. Displays medical information only
3. Provides recommendations/options, not specific diagnoses
4. Users can independently verify (considering automation bias)

Outputs a classification result + reasoning. Ambiguous cases create a Gate 1 (Goal Alignment) proposal.

**4.4.4 Automation Bias Controls**

Task-level `time_criticality` flag in `tasks.yaml`:

```yaml
task_types:
  sepsis_alert:
    time_criticality: "high"  # low | medium | high
    automation_bias_controls:
      require_physician_acknowledgment: true
      force_reasoning_display: true
      delay_ms: 3000
```

Enforced via `automation_bias_hook` on `PreToolUse` for the recommendation tool.

---

## 5. HITL Model — Two Gates

The per-tool-call HITL model is replaced with two meaningful gates.

### Gate 1: Goal Alignment (before execution)

Agent runs in planning-only mode (read-only tools) to produce a proposal:

```python
{
  "role": "security_analyst",
  "task": "Review auth module for vulnerabilities",
  "intended_approach": "Static analysis via Grep + manual review",
  "files_to_modify": ["src/auth/jwt.py"],
  "tools_requested": ["Read", "Grep", "Glob", "Edit"],
  "estimated_cost": 0.42,
  "estimated_duration_sec": 180,
  "risk_level": "LOW"
}
```

Proposal stored in existing `proposal_store`. Human approves the direction. Optional steering via `decision.feedback`.

### Autonomous Execution

Between gates, the SDK runs with `permission_mode="acceptEdits"`. Hooks observe (audit, cost tracking) but do not block **except** for:

- Budget exceeded (hard stop)
- PII leakage (hard stop)
- Data residency violation (hard stop)
- Destructive operations (hard stop)

### Gate 2: Result Approval (after execution)

`change_tracker_hook` accumulates every file change throughout execution. `Stop` hook fires `result_approval_hook`:

```python
{
  "files_created": [...],
  "files_modified": [...],
  "diffs": "unified diff format",
  "commands_run": [...],
  "test_results": {...},
  "actual_cost": 0.38,
  "duration_sec": 156
}
```

Human approves the outcome. **Rollback mechanism:** SDK file checkpointing is used to create a snapshot before execution. Rejection triggers full rollback.

**Limitation:** `Bash` commands with external side effects (API calls, emails sent) cannot be rolled back. The `destructive_op_hook` blocks the worst cases proactively.

### Preserved Invariants Under Revised Model

- ✅ Law 1: HITL preserved at meaningful boundaries
- ✅ Audit trail: every tool call still logged
- ✅ Compounding intelligence: rejections at either gate feed vector memory
- ✅ Budget enforcement: hard limits throughout execution
- ✅ Destructive op protection: absolute safety maintained

---

## 6. Integration Points

### Minimal changes to existing files

| File | Change |
|---|---|
| `src/core/llm_gateway.py` | Add `sdk_available` property. No behavior change. |
| `src/agents/universal.py` | Route through `AgentSDKRunner.run()`. Falls back to current path. |
| `src/agents/coder.py` | Same routing change. |
| `src/agents/analyst.py` | Same routing change. |
| `src/interface/api.py` | Add evolution + regulatory endpoints with lazy imports. |
| `solutions/starter/project.yaml` | Add `intended_purpose` template (commented, opt-in). |
| `solutions/starter/tasks.yaml` | Add `time_criticality` field template. |
| `requirements.txt` | Add `claude-agent-sdk` as optional dep (try/except import). |

### New files

```
src/core/agent_sdk_runner.py
src/core/sdk_hooks.py
src/core/evolution/__init__.py
src/core/evolution/orchestrator.py
src/core/evolution/program_db.py
src/core/evolution/candidate.py
src/core/evolution/prompt_evolver.py
src/core/evolution/code_evolver.py
src/core/evolution/build_evolver.py
src/core/evolution/evaluators.py
src/core/regulatory/__init__.py
src/core/regulatory/intended_purpose.py
src/core/regulatory/fda_classifier.py
src/core/regulatory/transparency_report.py
src/core/regulatory/automation_bias.py

tests/test_agent_sdk_runner.py
tests/test_sdk_hooks.py
tests/test_evolution_orchestrator.py
tests/test_program_db.py
tests/test_prompt_evolver.py
tests/test_code_evolver.py
tests/test_build_evolver.py
tests/test_evaluators.py
tests/test_intended_purpose.py
tests/test_fda_classifier.py
tests/test_transparency_report.py
tests/test_automation_bias.py

web/src/pages/Evolution.tsx
web/src/pages/Regulatory.tsx
web/src/api/client.ts                  (extended)

.claude/docs/features/evolution.md
.claude/docs/features/cds-compliance.md
```

### New API endpoints

```
POST /evolution/start                 — Start evolutionary run (creates Gate 1 proposal)
GET  /evolution/{id}                  — Status, generation, top candidates, fitness trend
POST /evolution/{id}/stop             — Early termination
GET  /evolution/history               — Past runs + lineage browser

POST /regulatory/classify             — Run FDA classifier on intended_purpose
GET  /regulatory/classification       — Current classification for active solution
GET  /regulatory/transparency/{trace_id}  — Fetch transparency report for a proposal
POST /regulatory/gold-standard/upload — Upload benchmark dataset
POST /regulatory/gold-standard/evaluate   — Run gold standard evaluation
```

---

## 7. Graceful Degradation Contract

Every new component must work with `claude_agent_sdk` NOT installed.

```python
try:
    from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition, HookMatcher
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
```

**When `SDK_AVAILABLE` is False:**
- `AgentSDKRunner.is_sdk_available()` returns `False`
- Evolution endpoints return `503 Service Unavailable` with clear error
- Regulatory primitives still work (they don't depend on SDK)
- Existing agents unchanged

**SDK features activate only when:**
1. `claude_agent_sdk` package installed, AND
2. `llm_gateway.current_provider == "claude-code"`, AND
3. Claude Code CLI is authenticated

All three conditions fail → full fallback to current implementation.

---

## 8. Rollout Phases (TDD)

Each phase: write tests first, implement to green, refactor, commit.

### Phase 1 — Foundation (SDK bridge + hooks)
- `AgentSDKRunner` with detection + graceful fallback
- SDK hook infrastructure wired to proposal store, audit logger, cost tracker
- Two-gate HITL model
- Tests: fallback path, hook firing, HITL gate creation
- **Gate:** All existing tests still pass; new runner works with SDK uninstalled

### Phase 2 — Agent Migration
- Route `UniversalAgent` through `AgentSDKRunner`
- Validate against existing solutions
- Tests: universal agent produces identical outputs via fallback path
- **Gate:** Regression-free migration

### Phase 3 — Program Database + Evaluators
- `Candidate`, `ProgramDatabase`, base `Evaluator` interface
- Ensemble evaluator infrastructure
- Tournament selection
- Tests: SQLite persistence, tournament sampling, lineage tracking

### Phase 4 — PromptEvolver (lowest risk)
- Mutation via SDK subagents
- Evaluation via Critic agent
- End-to-end evolution on a test solution
- Tests: single-generation evolution, HITL gates fire at correct boundaries

### Phase 5 — CodeEvolver + BuildEvolver
- Code mutation with test-based fitness
- Build plan evolution with integration scoring
- Tests: evolved code actually passes test suite

### Phase 6 — Regulatory Primitives
- `IntendedPurpose` schema + validator
- `FDAClassifier` agent role
- `TransparencyReport` schema + validator hook
- `AutomationBiasControls` hook
- `GoldStandardEvaluator` integration
- Tests: classification accuracy, transparency enforcement, time-criticality delays

### Phase 7 — UI + Documentation
- Evolution monitoring page (`web/src/pages/Evolution.tsx`)
- Regulatory dashboard (`web/src/pages/Regulatory.tsx`)
- New docs: `evolution.md`, `cds-compliance.md`
- Updated CLAUDE.md section
- Tests: UI smoke tests, doc link verification

---

## 9. Testing Strategy

**TDD mandatory** for all new code.

- **Unit tests:** Every new class/function in `tests/test_*.py`
- **Integration tests:** End-to-end flows — agent → runner → SDK → hooks → proposal store
- **Fallback tests:** Every component tested with SDK both available and unavailable
- **Evolutionary tests:** Deterministic seeds, mock LLM responses, assert database state transitions
- **Regulatory tests:** Sample intended_purpose configs covering both Non-Device and Device CDS classifications
- **Existing suite:** `make test` must pass throughout

---

## 10. Preserved SAGE Invariants

| Invariant | How Preserved |
|---|---|
| Law 1: HITL on agent proposals | Gate 1 + Gate 2 both required; destructive ops hard-block |
| Law 2: Eliminate waste | Evolutionary layer automates what humans can't scale |
| Law 3: Compounding intelligence | Rejections at both gates feed vector memory |
| Law 4: Vertical slices | Each rollout phase is end-to-end testable |
| Law 5: Atomic verification | Every mutation evaluated before selection |
| Framework vs Solutions | All SDK/evolution/regulatory configs live in YAML; `src/` is domain-blind |
| Provider agnosticism | SDK is accelerator, gateway remains primary |
| Audit trail integrity | Every SDK tool call hits `compliance_audit_log` via `PostToolUse` hook |
| Data isolation | ProgramDatabase at `solutions/<name>/.sage/evolution.db` |
| No `print()` | All new code uses `self.logger` |

---

## 11. Trade-offs & Open Questions

### Trade-offs

- **Less granular HITL control:** Per-tool-call gates are gone. Mitigation: rollback via file checkpointing, hard-blocking of destructive ops and budget overruns.
- **Rollback scope:** Only filesystem. `Bash` commands with external side effects (API calls, emails) are not reversible. Mitigation: `destructive_op_hook` blocks the worst cases.
- **SDK dependency risk:** `claude_agent_sdk` is a new external dependency. Mitigation: optional import, full fallback path.
- **Evolutionary cost:** Evolution loops can burn tokens. Mitigation: hard budget caps at generation boundaries; Gate 1 requires cost estimate approval.

### Open Questions

1. **Session persistence across processes:** SDK sessions are local to the host. For distributed SAGE deployments, how should sessions be handled? Initial answer: scope sessions to a single SAGE process; distributed use resumes by re-running Gate 1.
2. **Evolution timeout handling:** What happens if an evolution run exceeds expected duration? Initial answer: soft warning at 2x estimate, hard stop at 5x estimate or budget cap.
3. **Gold standard dataset format:** What schema for clinical benchmark datasets? Defer to Phase 6 design review with domain experts.
4. **Multi-tenant evolution isolation:** Should evolution budgets be per-tenant in addition to per-agent? Initial answer: yes, extend existing cost tracker with `evolution_run_id` scope.

---

## 12. Success Criteria

- All existing SAGE tests pass after each phase
- New tests achieve > 85% line coverage on new components
- A PromptEvolver run on the `starter` solution improves a seed prompt's Critic score by ≥ 10% over 3 generations (validates evolutionary effectiveness)
- FDA classifier correctly classifies at least 10 hand-labeled test cases (validates regulatory primitive accuracy)
- SDK features activate cleanly when Claude Code is provider; fall back cleanly when it's not
- Two-gate HITL model validated: agent cannot reach result approval without goal approval
- Documentation updated (CLAUDE.md, feature docs, API reference)

---

## 13. References

- **Claude Agent SDK:** https://code.claude.com/docs/en/agent-sdk/overview
- **AlphaEvolve:** arXiv:2506.13131 (DeepMind, 2025) — https://arxiv.org/abs/2506.13131
- **FDA CDS Guidance:** https://blog.johner-institute.com/regulatory-affairs/decision-support-systems-medical-device/
- **SAGE SOUL:** `.claude/SOUL.md`
- **SAGE CLAUDE.md:** `CLAUDE.md`
- **Existing regulatory docs:** `.claude/docs/features/regulatory-compliance.md`
