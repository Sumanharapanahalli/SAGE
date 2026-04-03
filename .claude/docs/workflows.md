# SAGE Framework Workflows

## The SAGE Lean Loop

Every task processed by SAGE follows this five-phase cycle:

```
1. SURFACE     → Agent detects or receives signal (log, webhook, trigger)
2. CONTEXTUALIZE → Vector memory searched; prior decisions retrieved
3. PROPOSE     → LLM generates action proposal with trace_id
4. DECIDE      → Human reviews and approves or rejects with feedback
5. COMPOUND    → Feedback ingested into vector store; audit log updated
```

Phase 5 feeds back into Phase 2 for the next task. This is compounding intelligence — the system gets measurably better with every human interaction.

## Approval Gate — Two Tiers

**Not all actions go through the approval queue. Framework control ops execute immediately. Only solution-level agent proposals require human sign-off.**

| Tier | Operations | Behaviour |
|---|---|---|
| **Framework control** | `POST /config/switch`, `POST /llm/switch`, `POST /config/modules` | **Executes immediately.** No proposal created. Returns `{"status": "switched"}`. |
| **Solution agent proposals** | `yaml_edit`, `implementation_plan`, `code_diff`, `knowledge_*`, `agent_hire` | **Requires HITL approval.** Creates a `Proposal` in the store. Human reviews at `/approvals`. Nothing executes until approved. |

## LangGraph Workflow Pattern

Create `solutions/<name>/workflows/my_workflow.py`:

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class State(TypedDict, total=False):
    task: str
    result: str
    approved: bool

def analyze(state): ...   # your agent logic
def finalize(state): ...  # runs after approval

graph = StateGraph(State)
graph.add_node("analyze", analyze)
graph.add_node("finalize", finalize)
graph.set_entry_point("analyze")
graph.add_edge("analyze", "finalize")
graph.add_edge("finalize", END)
workflow = graph.compile(interrupt_before=["finalize"])  # pause for approval
```

Then call:
```
POST /workflow/run   {"workflow_name": "my_workflow", "state": {"task": "..."}}
# Returns {"status": "awaiting_approval", "run_id": "..."}
POST /workflow/resume {"run_id": "...", "feedback": {"approved": true}}
```

## Build Orchestrator Workflows

### 0→1 Greenfield Build

Full pipeline: `POST /build/start` with a product description.

```
Description → Domain Detection (13 domains via DOMAIN_RULES)
  → Workforce Assembly (19 agents, 5 teams from WORKFORCE_REGISTRY)
  → Hierarchical Decomposition (LLM → task graph)
  → Critic reviews plan (score 0-100)
  → HITL approval gate
  → Wave execution (parallel independent tasks)
  → Critic reviews code per task
  → Integration merge
  → Critic reviews integration
  → HITL final approval
  → Completed
```

### 1→N Refinement

Same orchestrator, scoped to changes. Triggered by feature requests, bug fixes, or improvement proposals.

Key 1→N differences:
- Domain already known — skips detection
- Workforce is stable — router has learned agent strengths
- Decomposition scoped to the change, not the whole product
- Critic calibration is higher (knows existing quality baseline)
- AdaptiveRouter scores are warm — compounds from prior builds
- Anti-drift checkpoints compare against established baseline

## Agent Gym Training Workflow

### MuZero-Inspired Training Loop

```
1. PLAY      → Agent attempts an exercise from its runner's skill set
2. EXECUTE   → Real code execution: compile, test, simulate (experimental verification)
3. GRADE     → 3-tier grading: experimental 40% + LLM critic 30% + structural 30%
4. CRITIQUE  → N critics (Gemini, Claude, Ollama, Human Expert, ...) review EXPERIMENTAL RESULTS
5. REFLECT   → Agent reviews its output vs critic feedback, generates improvement plan
6. REFINE    → Critics evolve acceptance criteria based on experimental evidence
7. COMPOUND  → Learnings stored in vector memory for next attempt
```

### Exercise Selection Algorithm

1. **Spaced repetition** — failed exercises due for retry (highest priority)
2. **Optimal zone** — exercises where agent success rate is 40-70% (best learning zone)
3. **Unseen** — exercises not yet attempted (exploration)

## Regulatory Compliance Workflows

### Change Control Process

```
1. INITIATE → Submit change request with justification
2. ASSESS   → Analyze impact on requirements, testing, docs
3. REVIEW   → Human approval based on risk assessment
4. EXECUTE  → Apply changes with full audit trail
5. VERIFY   → Confirm changes meet acceptance criteria
```

### Electronic Signature Workflow

```
1. CREATE   → Set up signature workflow with required signers
2. NOTIFY   → Alert signers of pending signature request
3. SIGN     → Apply 21 CFR Part 11 compliant signatures
4. VERIFY   → Validate signature integrity and compliance
5. ARCHIVE  → Store with complete audit trail
```

## Research and Optimization Workflows

### AutoResearch Engine (Karpathy-style)

```
1. PROPOSE  → LLM generates hypothesis + code change (search/replace)
2. APPLY    → Changes written to workspace, committed to git
3. EXECUTE  → Experiment runs with wall-clock timeout (default 300s)
4. MEASURE  → Metric extracted from stdout (regex, last occurrence)
5. DECIDE   → If improved: keep (commit stays). If not: discard (git reset)
6. LOOP     → Repeat with updated baseline and history context
```

### Meta-Optimization Loop

```
1. COLLECT  → Gather execution traces from Agent Gym sessions
2. PROPOSE  → LLM reads traces + prior candidates → proposes harness changes
3. EVALUATE → Run proposal against exercise set, measure vs baseline
4. PERSIST  → Save iteration (accepted/rejected) in SQLite
5. CONVERGE → Detect when optimization has plateaued
```

## Error Recovery and Resilience

### Anti-Drift Checkpoints

- `_checkpoint()` after each state change
- `_restore_runs()` on startup
- Drift detection via `BUILD_DRIFT_WARNING` audit events
- Automatic rollback on critical failures

### Graceful Degradation

All integrations designed for graceful degradation:
- OpenShell unavailable → SandboxRunner → Direct execution
- Vector store down → In-memory fallback
- LLM provider failed → Switch to backup provider
- MCP server offline → Disable dependent tools