# Issue: Human-in-the-Loop Design Pattern — Formal Definition and Full Audit

**Labels:** `architecture`, `design-pattern`, `framework-core`, `compliance`
**Milestone:** Intelligence Layer v1
**Scope:** `sage` (framework-wide)
**Priority:** HIGH — this is the founding principle of SAGE; gaps here undermine the whole value proposition

---

## Problem

SAGE's founding thesis is: **AI proposes. Humans decide. Always.**

This is documented in SOUL.md, ARCHITECTURE.md, and every piece of marketing material. But as
the framework grew from Phase 0 through Phase 11, new endpoints and integrations were added
without consistently applying the pattern. Several agent actions now write to the system, modify
state, or trigger external effects **without an approval gate**.

This is not a minor inconsistency — it is a compliance failure for regulated users and an
architectural failure for everyone else. If any endpoint can act without human confirmation,
users cannot trust the HITL guarantee.

### Scope of the problem

A full audit of `src/interface/api.py` found **18 write/execute endpoints** that currently
act without going through the proposal → approve → act cycle:

| Endpoint | Action | Risk |
|----------|--------|------|
| `PUT /config/yaml/{file}` | Rewrites solution YAML live | Silently changes all agent behaviour |
| `POST /config/switch` | Switches active solution | Changes all agent behaviour |
| `POST /llm/switch` | Switches LLM provider/model | Changes inference quality globally |
| `POST /onboarding/generate` | Writes solution YAML files to disk | No review before files are created |
| `POST /knowledge/add` | Adds document to vector store | Unreviewed content shapes future RAG context |
| `DELETE /knowledge/entry/{id}` | Removes a knowledge entry | Irreversible deletion of institutional memory |
| `POST /knowledge/import` | Bulk imports to vector store | No review before large context change |
| `POST /code/execute` | Executes AutoGen-generated code | Code runs in Docker sandbox without final human sign-off |
| `POST /code/plan` | Generates + queues code plan | Plan queued without review |
| `POST /mcp/invoke` | Calls an MCP tool directly | Direct tool call with no proposal layer |
| `POST /temporal/workflow/start` | Starts a durable workflow | Workflow begins without approval |
| `POST /config/modules` | Modifies active modules | Changes which UI pages are visible |

The other write endpoints (`/mr/create`, `/mr/review`, `/analyze`, `/agent/run`, etc.) already
return proposals but their **downstream execution** path is not always gated.

---

## The HITL Contract (Formal Definition)

Every AI-initiated action in SAGE must follow this five-step contract. No exceptions.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    THE SAGE HITL CONTRACT                           │
│                                                                     │
│  1. PROPOSE    Agent generates an action proposal                   │
│                { trace_id, action_type, payload, confidence,        │
│                  risk_level, reversibility }                        │
│                                                                     │
│  2. SURFACE    Proposal is made visible to a human                  │
│                Via: Web UI / Slack Block Kit / Teams card / API     │
│                                                                     │
│  3. DECIDE     Human explicitly approves or rejects                 │
│                POST /approve/{trace_id}  or                         │
│                POST /reject/{trace_id} + feedback                   │
│                                                                     │
│  4. ACT        Action executes ONLY after approval                  │
│                Approval is recorded before execution begins         │
│                                                                     │
│  5. AUDIT      Full event chain logged immutably                    │
│                proposal → decision → execution → outcome            │
└─────────────────────────────────────────────────────────────────────┘
```

### Action Classification

Not all actions carry the same risk. The approval mechanism scales with reversibility and blast radius:

| Class | Risk | Reversibility | Approval required | Example |
|-------|------|--------------|-------------------|---------|
| `INFORMATIONAL` | None | n/a | No approval needed | Reading data, health checks |
| `EPHEMERAL` | Low | Instant rollback | Soft confirmation (undo available) | LLM provider switch |
| `STATEFUL` | Medium | Manual rollback | Explicit approve/reject + audit log | Adding knowledge entries, YAML edits |
| `EXTERNAL` | High | Hard to reverse | Explicit approve/reject + audit log | MR create, Slack message sent |
| `DESTRUCTIVE` | Critical | Irreversible | Explicit approve/reject + human note | Delete knowledge, drop DB |

### What counts as "Human Approval"

Valid approval surfaces (all call `POST /approve/{trace_id}`):
- Web UI Approve button
- Slack Block Kit Approve button → `/webhook/slack`
- Teams adaptive card Approve → `/webhook/teams`
- Direct REST call: `POST /approve/{trace_id}`
- n8n callback after human action in external tool

**Not valid:**
- Auto-approval after a timeout
- Agent self-approving its own proposal
- Code that calls approve internally
- Skipping the proposal step and acting directly

---

## Required Changes

### 1. `ProposalStore` — centralised pending action registry

A new `src/core/proposal_store.py` that all endpoints use before acting:

```python
class Proposal(BaseModel):
    trace_id: str                    # UUID
    created_at: datetime
    action_type: str                 # "yaml_edit" | "knowledge_add" | "llm_switch" | ...
    risk_class: RiskClass            # INFORMATIONAL | EPHEMERAL | STATEFUL | EXTERNAL | DESTRUCTIVE
    reversible: bool
    proposed_by: str                 # "AnalystAgent" | "user:admin" | "OnboardingWizard"
    description: str                 # Human-readable: "Switch LLM provider from gemini to ollama"
    payload: dict                    # The actual action data
    status: Literal["pending", "approved", "rejected", "expired"]
    decided_by: Optional[str]        # Who approved/rejected
    decided_at: Optional[datetime]
    feedback: Optional[str]          # Rejection reason

class ProposalStore:
    def create(self, action_type, risk_class, payload, description, ...) -> Proposal: ...
    def approve(self, trace_id, decided_by) -> Proposal: ...
    def reject(self, trace_id, decided_by, feedback) -> Proposal: ...
    def get_pending(self) -> list[Proposal]: ...
    def get(self, trace_id) -> Proposal: ...
```

All proposals are stored in `data/audit_log.db` (`proposals` table). The existing `approve/{trace_id}` and `reject/{trace_id}` endpoints delegate to `ProposalStore`.

### 2. Endpoint changes — the 12 ungated endpoints

Each ungated write endpoint must be converted from **act immediately** to **propose → await approval → act**.

**Pattern before (wrong):**
```python
@app.put("/config/yaml/{file_name}")
async def update_yaml(file_name: str, body: YamlUpdateRequest):
    # validates and writes immediately
    write_yaml(file_name, body.content)
    project_config.reload(project_name)
    return {"saved": True}
```

**Pattern after (correct):**
```python
@app.put("/config/yaml/{file_name}")
async def update_yaml(file_name: str, body: YamlUpdateRequest):
    diff = compute_diff(current_yaml, body.content)
    proposal = proposal_store.create(
        action_type="yaml_edit",
        risk_class=RiskClass.STATEFUL,
        payload={"file": file_name, "content": body.content, "diff": diff},
        description=f"Edit {file_name}.yaml — {len(diff.splitlines())} lines changed",
        reversible=True,
    )
    return {"status": "pending_approval", "trace_id": proposal.trace_id,
            "description": proposal.description, "diff": diff}

# Execution only happens in the approve handler:
@app.post("/approve/{trace_id}")
async def approve_proposal(trace_id: str, body: ApproveRequest):
    proposal = proposal_store.approve(trace_id, decided_by=body.approved_by)
    await _execute_approved_proposal(proposal)   # dispatches to action executor
    audit_logger.log_event(...)
    return {"approved": True, "trace_id": trace_id}
```

**Endpoint-by-endpoint changes:**

| Endpoint | Current behaviour | New behaviour |
|----------|------------------|---------------|
| `PUT /config/yaml/{file}` | Writes immediately | Returns proposal with diff; executes on approve |
| `POST /config/switch` | Switches immediately | Returns proposal; executes on approve; prior solution kept as rollback |
| `POST /llm/switch` | Switches immediately | Returns EPHEMERAL proposal; UI shows "undo" for 60s |
| `POST /onboarding/generate` | Writes files immediately | Returns draft YAML for review; writes only on explicit confirm |
| `POST /knowledge/add` | Adds immediately | Returns proposal with content preview; adds on approve |
| `DELETE /knowledge/entry/{id}` | Deletes immediately (irreversible) | Returns DESTRUCTIVE proposal; requires explicit human note to approve |
| `POST /knowledge/import` | Bulk imports immediately | Returns proposal with count + sample; imports on approve |
| `POST /code/plan` | Queues plan immediately | Returns plan for review; queues on approve |
| `POST /code/execute` | Executes immediately in Docker | Returns execution plan; runs on approve; output shown before marking complete |
| `POST /mcp/invoke` | Calls tool immediately | Returns tool call proposal; invokes on approve |
| `POST /temporal/workflow/start` | Starts workflow immediately | Returns workflow proposal; starts on approve |
| `POST /config/modules` | Updates immediately | Returns proposal; applies on approve |

### 3. HITL-aware Onboarding

The conversational onboarding wizard (see Issue #4) must embed HITL at every consequential step:

```
Step 7: SAGE has drafted your YAML files.

  Here's what I'm about to create:
  solutions/myapp/project.yaml    — 42 lines
  solutions/myapp/prompts.yaml    — 118 lines
  solutions/myapp/tasks.yaml      — 67 lines

  Changes I'll make to your .env:
  + GITHUB_TOKEN=<the token you provided>

  [ Review each file ] [ Approve and create ] [ Go back and edit ]
```

No files are written until the user explicitly clicks "Approve and create". This generates a
`STATEFUL` proposal internally, which the confirm button approves.

### 4. HITL-aware Teacher-Student (Issue #2)

Model promotion (student → student_only for a task type) is an `EXTERNAL` class action and must go through approval:

```
SAGE: The student model has won 94% of comparisons for ANALYZE_CRASH over the
      last 7 days (312 comparisons). Ready to promote it to student_only for
      this task type?

      Estimated impact: ~2.1s faster per analysis, ~$0 cloud cost for this task.
      Risk: if a novel crash type appears, the student may perform worse.

      [ Approve promotion ] [ Keep in parallel_compare ] [ Reject ]
```

### 5. Proposal Dashboard (Web UI)

The existing Audit Log page is a record of past events. A new **Pending Approvals** section on the Dashboard surfaces all proposals currently awaiting human decision:

```
Pending Approvals (3)

┌─────────────────────────────────────────────────────────────────────┐
│ [STATEFUL]  Edit prompts.yaml — analyst system prompt changed       │
│ Proposed by: OnboardingWizard  •  2 minutes ago                     │
│ 14 lines changed — see diff                          [Approve] [Reject] │
├─────────────────────────────────────────────────────────────────────┤
│ [DESTRUCTIVE]  Delete knowledge entry #47                           │
│ "NullPointerException in CheckoutService" — added 3 days ago        │
│ Irreversible                              [Approve + note] [Reject] │
├─────────────────────────────────────────────────────────────────────┤
│ [EPHEMERAL]  Switch LLM provider: gemini → ollama                   │
│ Proposed by: user  •  just now                                      │
│ Undo available for 60 seconds             [Approve] [Undo in 0:45]  │
└─────────────────────────────────────────────────────────────────────┘
```

### 6. Expiry and timeout policy

Proposals do not auto-approve. They expire:

| Risk class | Expiry | On expiry |
|-----------|--------|-----------|
| `EPHEMERAL` | 5 minutes | Silently discarded, no action taken |
| `STATEFUL` | 24 hours | Marked `expired`, user notified |
| `EXTERNAL` | 72 hours | Marked `expired`, user notified |
| `DESTRUCTIVE` | No expiry | Must be explicitly approved or rejected |

Expiry is enforced by a background job that runs every 60 seconds.

---

## What Does NOT Need HITL

To prevent the framework becoming unusable, these actions are explicitly exempt:

| Action | Why exempt |
|--------|-----------|
| `GET` requests (all) | Read-only, no state change |
| `POST /analyze` | Returns a proposal — the proposal itself IS the HITL gate |
| `POST /approve/{trace_id}` | This IS the approval action |
| `POST /reject/{trace_id}` | This IS the rejection action |
| `POST /eval/run` | Running evals is observation, not action |
| `POST /onboarding/session/{id}/reply` | Conversational turn, no state written |
| `POST /knowledge/search` | Read-only |
| `POST /slack/send-proposal` | Sending a notification, not acting |
| `POST /shutdown` | Initiated by human explicitly |
| Health checks, status endpoints | Operational, no agent action |

---

## Files Added / Modified

| File | Change |
|------|--------|
| `src/core/proposal_store.py` | New — `Proposal` model, `ProposalStore`, `RiskClass` enum |
| `src/core/proposal_executor.py` | New — `execute_approved_proposal()` dispatch map |
| `src/interface/api.py` | Convert 12 endpoints to proposal pattern; update approve/reject to call executor |
| `data/audit_log.db` | New `proposals` table |
| `web/src/pages/Dashboard.tsx` | Add "Pending Approvals" panel |
| `web/src/components/proposals/ProposalCard.tsx` | New — renders a proposal with approve/reject |
| `web/src/components/proposals/DiffView.tsx` | New — shows YAML/text diffs for review |
| `tests/test_proposal_store.py` | New — unit tests |
| `tests/test_hitl_contract.py` | New — integration tests: every write endpoint must return a trace_id |

---

## Implementation Plan

### Step 1 — ProposalStore + executor skeleton
- `src/core/proposal_store.py` with SQLite backing
- `src/core/proposal_executor.py` with empty dispatch map
- `POST /approve/{trace_id}` and `POST /reject/{trace_id}` delegated to ProposalStore
- Unit tests

### Step 2 — Convert STATEFUL endpoints (lowest risk changes first)
- `PUT /config/yaml/{file}` → proposal with diff
- `POST /knowledge/add` and `POST /knowledge/import` → proposal with preview
- `DELETE /knowledge/entry/{id}` → DESTRUCTIVE proposal requiring note
- Integration tests: confirm these endpoints no longer act immediately

### Step 3 — Convert EPHEMERAL endpoints
- `POST /llm/switch` → EPHEMERAL proposal with 60s undo
- `POST /config/switch` → proposal with rollback
- `POST /config/modules` → proposal

### Step 4 — Convert EXTERNAL/HEAVY endpoints
- `POST /code/plan` and `POST /code/execute` → proposals
- `POST /mcp/invoke` → proposal
- `POST /temporal/workflow/start` → proposal

### Step 5 — Pending Approvals UI
- Dashboard panel showing all pending proposals
- ProposalCard component with diff view
- Approve/reject from within the card

### Step 6 — Contract test suite
- `tests/test_hitl_contract.py`: automated test that calls every non-GET endpoint and asserts it either (a) returns a `trace_id` pending proposal, or (b) is in the explicit exempt list
- This test will fail immediately if a future PR adds an ungated write endpoint

---

## Acceptance Criteria

- [ ] All 12 currently ungated write endpoints return a proposal instead of acting immediately
- [ ] `POST /approve/{trace_id}` executes the action for all proposal types
- [ ] `DELETE /knowledge/entry/{id}` requires an explicit human note in the approve body
- [ ] DESTRUCTIVE proposals never expire
- [ ] `tests/test_hitl_contract.py` passes and will catch any future ungated endpoint
- [ ] Pending Approvals panel visible on Dashboard
- [ ] All existing tests pass (`make test`)
- [ ] The onboarding wizard (Issue #4) uses the proposal pattern for YAML file creation

---

## Relationship to Other Issues

| Issue | Relationship |
|-------|-------------|
| SAGE Framework SLM (Issue #1) | SLM routing decisions are INFORMATIONAL — no HITL needed |
| Teacher-Student LLM (Issue #2) | Model promotion is STATEFUL — goes through approval |
| Conversational Onboarding (Issue #4) | YAML file creation must be STATEFUL proposal, not immediate write |

This issue must be implemented **before** Issue #1, #2, and #4 ship — those features will add
more agent-initiated actions and must be built on top of the ProposalStore from the start.
