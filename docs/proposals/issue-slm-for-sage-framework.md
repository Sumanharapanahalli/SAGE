# Issue: SAGE Framework SLM — Embedded Small Language Model for Framework Intelligence

**Labels:** `enhancement`, `intelligence`, `framework-core`
**Milestone:** Intelligence Layer v1
**Scope:** `sage` (framework improvement, not solution-specific)

---

## Summary

Embed a small language model (Gemma 3 380M or equivalent) directly into SAGE as the always-on
framework intelligence layer. This model handles everything that is about SAGE itself — not about
any solution domain. It runs locally, starts with the framework, and requires no API key or
network connection.

---

## Problem

Today, every user interaction with SAGE — even trivial ones like "what command do I need?" or
"validate this YAML" — goes to the full cloud LLM (Gemini/Claude). This means:

- New users have no help unless a cloud LLM is already configured
- Setup guidance, YAML lint, and query routing all add unnecessary latency
- Framework-level intelligence is mixed with domain-level intelligence in the same model call

There is a second, deeper problem: the framework has no voice of its own. A user setting up
SAGE for the first time asks "how do I add a Slack integration?" — the answer requires SAGE
knowledge, not domain knowledge. A 380M model that knows SAGE deeply is more useful here
than a 70B model that knows nothing about SAGE specifically.

---

## Proposed Solution

Add a `SAGEIntelligence` class to `src/core/sage_intelligence.py` that wraps a locally running
380M SLM and handles all framework-level tasks. The full LLM gateway is untouched and continues
to handle solution-domain tasks.

```
User Input
     │
     ▼
SAGEIntelligence.classify(input)        ← 380M: is this a framework question or a domain task?
     │                │
     │         [framework question]
     │                ▼
     │         SAGEIntelligence.respond()   ← 380M handles it directly
     │
[domain task]
     ▼
LLMGateway.generate()                   ← full model handles it as today
```

---

## Responsibilities of the SAGE SLM

### 1. Framework Onboarding Assistant

Natural language Q&A about SAGE itself. The 380M model is fine-tuned on or given context from:
- `GETTING_STARTED.md`
- `ARCHITECTURE.md`
- `docs/ADDING_A_PROJECT.md`
- The active solution's `project.yaml`, `prompts.yaml`, `tasks.yaml`

Example exchanges:
```
User:  "how do I switch to Ollama?"
SAGE:  "Edit config/config.yaml: set llm.provider to 'ollama'. Then POST /llm/switch
        {"provider": "ollama", "model": "llama3.2"} or use the LLM Settings page."

User:  "why is my analyst returning non-JSON?"
SAGE:  "Your analyst system_prompt in prompts.yaml likely doesn't end with: 'Do not output
        markdown, prose, or any text outside the JSON object.' Add that line."
```

### 2. Meta-Query Conversion

Converts a user's natural language into a structured SAGE API call. This is the "intent layer"
before the domain layer.

```
User input:  "analyze this crash log from our iOS app"
             │
             ▼
SAGEIntelligence.to_api_call(input, active_solution_context)
             │
             ▼
{
  "endpoint": "POST /analyze",
  "body": {"input": "<log text>"},
  "agent_role": "analyst",
  "suggested_task_type": "ANALYZE_CRASH"   ← from active solution's tasks.yaml
}
```

This means the user can describe their intent in plain language and SAGE routes it correctly
without the full LLM being invoked first.

### 3. YAML Validation and Lint

Before a user saves or hot-reloads a solution YAML file, the SLM checks it:

- Schema validation against the three-file structure
- Consistency check: does the planner prompt list the same task types as `tasks.yaml`?
- Common mistake detection: non-JSON analyst prompt, missing `CREATE_MR`, `collection_name` collision
- Plain English error messages, not raw Python tracebacks

Runs on `PUT /config/yaml/{file}` before the file is written.

### 4. Task Router

Classifies every incoming task and decides:
- Which agent role handles it
- What complexity tier it is (`light` / `standard` / `heavy`)
- Whether it can be parallelised with other pending tasks

```python
class TaskTier(Enum):
    LIGHT    = "light"     # classification, severity triage, short summaries → SLM handles
    STANDARD = "standard"  # analysis, MR review, planning → full LLM
    HEAVY    = "heavy"     # multi-step ReAct, AutoGen code gen → full LLM + tools
```

`LIGHT` tasks are handled entirely by the SLM at near-zero latency. `STANDARD` and `HEAVY`
tasks go to the full LLM gateway as today.

### 5. Prompt Quality Guard

Before any prompt reaches the full LLM, the SLM checks it for:
- Empty or trivially short inputs
- Inputs that look like test strings ("aaa", "test", "asdf")
- Inputs that are clearly the wrong type for the selected task
- Requests to override or bypass SAGE's safety behaviour

This prevents wasted full-LLM calls on bad inputs and gives the user immediate feedback.

---

## Model Choice

| Model | Size | RAM | Function calling | Notes |
|-------|------|-----|-----------------|-------|
| Gemma 3 380M | 380M | ~400 MB | Yes (Google) | Smallest viable; marginal on complex classification |
| Gemma 3 1B | 1B | ~800 MB | Yes (Google) | Recommended — structured output reliability much higher |
| Phi-3.5 Mini 3.8B | 3.8B | ~2.5 GB | Yes (Microsoft) | Best quality in the small range; use if RAM allows |
| SmolLM2 1.7B | 1.7B | ~1.2 GB | Limited | Designed for on-device, good instruction following |

**Recommended starting point:** Gemma 3 1B via Ollama (`ollama pull gemma3:1b`). This reuses
the existing Ollama provider with zero new dependencies. The 380M can be offered as a
`--sage-slm minimal` flag for truly constrained devices.

---

## Configuration

In `config/config.yaml`:

```yaml
sage_intelligence:
  enabled: true
  model: "gemma3:1b"          # any Ollama model
  provider: "ollama"           # ollama | local (GGUF) | none
  light_task_threshold: 0.85   # confidence above this → SLM handles without escalation
  fallback_on_error: true      # if SLM fails, route to full LLM silently
```

If `enabled: false` or the model is unavailable, all tasks fall through to the full LLM
gateway exactly as today. Zero breaking change.

---

## Implementation Plan

### Step 1 — Core class (no routing yet)
- `src/core/sage_intelligence.py`: `SAGEIntelligence` wraps an Ollama call to the SLM
- Load SAGE framework docs as static context on startup
- Expose `classify(input) → TaskTier` and `respond(input) → str`
- Unit tests with mocked Ollama responses

### Step 2 — YAML lint
- Wire into `PUT /config/yaml/{file}` before file write
- Return structured lint errors: `[{field, message, suggestion}]`
- Tests covering all Common Mistakes from `ADDING_A_PROJECT.md`

### Step 3 — Meta-query conversion
- New endpoint: `POST /sage/intent` → `{endpoint, body, suggested_task_type}`
- Web UI: natural language input bar on Dashboard that calls this first

### Step 4 — Task router
- `TaskTier` enum in `src/core/sage_intelligence.py`
- `queue_manager.py` calls `classify()` before dispatching
- Light tasks bypass full LLM; result logged to audit as `actor="SAGEIntelligence"`

### Step 5 — Onboarding assistant
- `GET /sage/ask?q=<question>` endpoint
- Web UI: help panel (?) button on every page that opens an assistant drawer

---

## Files Added / Modified

| File | Change |
|------|--------|
| `src/core/sage_intelligence.py` | New — SAGEIntelligence class |
| `src/interface/api.py` | Add `/sage/intent`, `/sage/ask` endpoints; wire lint into YAML PUT |
| `src/core/queue_manager.py` | Call `sage_intelligence.classify()` before dispatch |
| `config/config.yaml` | Add `sage_intelligence:` section |
| `tests/test_sage_intelligence.py` | New — unit tests |
| `web/src/pages/Dashboard.tsx` | Add natural language input bar |
| `web/src/components/shared/HelpPanel.tsx` | New — assistant drawer |

---

## Acceptance Criteria

- [ ] `SAGEIntelligence` starts and responds when Ollama is available; silently disabled otherwise
- [ ] YAML lint catches all 5 Common Mistakes from `ADDING_A_PROJECT.md` before file write
- [ ] `POST /sage/intent` converts "analyze this log" → correct endpoint + task_type for active solution
- [ ] `LIGHT` tasks (severity classification, short summaries) route to SLM; full LLM not called
- [ ] Help panel answers "how do I switch LLM provider?" correctly from framework docs context
- [ ] All existing tests still pass (`make test`)
- [ ] Memory overhead of SLM at idle: under 1 GB RAM

---

## Out of Scope (separate issue)

- Teacher-student training for solution domain models — see Issue #2
- Fine-tuning the SLM on SAGE-specific data (Phase 2 of this feature)
- Multi-modal inputs
