# Issue: Teacher-Student LLM Architecture for Solution Domains

**Labels:** `enhancement`, `intelligence`, `solutions`, `ml`
**Milestone:** Intelligence Layer v1
**Scope:** `solution` (configurable per solution, zero framework changes required)

---

## Summary

Add a configurable teacher-student LLM architecture to SAGE solutions. A local small model
(student) and a cloud model (teacher) both operate on solution domain tasks. A lightweight
router decides which model to use — or runs both in parallel and compares results. Over time,
disagreements become the training signal for continuously improving the local student model.

This is entirely opt-in and configured in `project.yaml`. Solutions that do not configure it
continue to use the existing single `LLMGateway` provider unchanged.

---

## Problem

Today SAGE solutions use one LLM for all tasks — typically a cloud model. This creates three
problems:

**Cost:** Every routine task (severity classification, short summaries, field extraction)
costs a full cloud API call. For a team running 50 analyses per day, this adds up.

**Latency:** Cloud round-trips add 2–5 seconds even for trivial classifications that a
local 1B model could answer in 200ms.

**No improvement loop:** The solution's LLM quality is fixed by the model provider. Human
rejections go into the vector store (RAG), but the model itself never gets better at the
domain. There is no mechanism to distil domain expertise into a local model over time.

---

## Proposed Solution

Add a `DualLLMRunner` to `src/integrations/dual_llm_runner.py` that manages the
teacher-student relationship per solution. It is invoked transparently by `LLMGateway`
when the active solution has `llm_strategy: dual` configured.

```
Agent calls LLMGateway.generate(prompt, system_prompt, task_tier)
     │
     ▼
DualLLMRunner (if configured for this solution)
     │
     ├── Strategy: "student_first"
     │     Student generates → confidence scored → if below threshold, escalate to teacher
     │
     ├── Strategy: "parallel_compare"
     │     Student + Teacher generate simultaneously → judge picks better result
     │     Disagreement logged as training candidate
     │
     ├── Strategy: "teacher_only"
     │     Teacher generates → student observes (shadow mode — no user impact)
     │     All outputs logged as distillation candidates
     │
     └── Strategy: "student_only"
           Student generates → no teacher call (fully offline, post-training)
```

---

## The Three Phases of a Solution's LLM Maturity

```
Phase A — Bootstrapping (new solution, no trained student)
  Strategy: teacher_only
  Teacher handles all requests. Student observes every teacher response.
  Distillation candidates accumulate in data/distillation/<solution_name>/

Phase B — Parallel evaluation (enough data to test the student)
  Strategy: parallel_compare
  Both models generate. Judge (lightweight scorer) picks the better result.
  Win/loss rates tracked. If student wins >80% on a task type → promote to student_first.

Phase C — Student-led (student is good enough for routine tasks)
  Strategy: student_first (per task type, configurable granularity)
  Student handles ANALYZE_CRASH, CLASSIFY_SEVERITY, etc.
  Teacher only called when student confidence is below threshold or task_tier == "heavy".
  Cost and latency drop significantly.
```

---

## Configuration in `project.yaml`

```yaml
# solutions/meditation_app/project.yaml

llm_strategy:
  mode: "dual"                        # single | dual — default is single (existing behaviour)

  student:
    provider: "ollama"
    model: "gemma3:1b"                # any locally available model
    confidence_threshold: 0.82        # below this → escalate to teacher
    handles_task_tiers: ["light"]     # light | standard | heavy

  teacher:
    provider: "gemini"                # uses the existing LLMGateway provider config
    model: "gemini-2.5-flash"

  strategy: "student_first"          # student_first | parallel_compare | teacher_only | student_only

  # Per-task-type overrides (optional — fine-grained control)
  task_overrides:
    ANALYZE_CRASH:     "parallel_compare"   # always compare — high stakes
    CLASSIFY_SEVERITY: "student_first"      # student is reliable here
    CREATE_MR:         "teacher_only"       # teacher always for MR creation

  distillation:
    enabled: true
    output_dir: "data/distillation/meditation_app/"
    min_samples_before_training: 200        # collect this many before suggesting fine-tune
    format: "alpaca"                        # alpaca | sharegpt | chatml
```

---

## How Parallel Comparison Works

```
Task arrives (e.g. ANALYZE_CRASH)
     │
     ├──────────────────────────────┐
     ▼                              ▼
Student.generate(prompt)     Teacher.generate(prompt)
     │  (async, ~200ms)            │  (async, ~2500ms)
     └──────────────┬──────────────┘
                    ▼
            Judge.compare(student_output, teacher_output)
                    │
                    ▼
    Score each output on:
      - JSON validity (required fields present?)
      - Severity accuracy (is it consistent with known patterns?)
      - Root cause specificity (generic vs. precise hypothesis)
      - Recommended action actionability
                    │
            ┌───────┴────────┐
            │                │
      [Student wins]   [Teacher wins]
            │                │
      Student result    Teacher result
      returned           returned
      Teacher result     Student result
      logged as          logged as
      "agreement"        "distillation candidate"
```

All comparisons are written to `data/distillation/<solution>/comparisons.jsonl`:
```json
{"task_type": "ANALYZE_CRASH", "input": "...", "student": {...}, "teacher": {...},
 "winner": "teacher", "scores": {"student": 0.71, "teacher": 0.94}, "timestamp": "..."}
```

---

## Confidence Scoring (Student-First Mode)

When `strategy: student_first`, the student's output is scored before being returned.
Confidence scoring is itself lightweight — run by the SAGE Framework SLM (see Issue #1)
or by a simple rule-based scorer:

```python
def score_confidence(output: dict, task_type: str, schema: dict) -> float:
    score = 1.0
    # Required fields present?
    for field in schema.get("required_fields", []):
        if field not in output:
            score -= 0.3
    # Severity is a known value?
    if "severity" in output and output["severity"] not in {"RED","AMBER","GREEN","UNKNOWN"}:
        score -= 0.4
    # Root cause is not generic filler?
    generic_phrases = ["unknown error", "something went wrong", "error occurred"]
    if any(p in output.get("root_cause_hypothesis","").lower() for p in generic_phrases):
        score -= 0.25
    return max(0.0, score)
```

If `score < confidence_threshold`, the request is escalated to the teacher transparently.
The student's attempt is still logged as a distillation candidate with the teacher's answer
as the gold label.

---

## Distillation Data Collection

Every time the teacher produces a response (in any mode), it is saved as a potential
training example:

```
data/distillation/
└── meditation_app/
    ├── comparisons.jsonl       ← parallel_compare results
    ├── escalations.jsonl       ← student_first escalations (teacher gold labels)
    ├── shadow_observations.jsonl ← teacher_only mode observations
    └── training_ready/
        ├── alpaca_format.json  ← export when min_samples reached
        └── metadata.json       ← sample counts, task type breakdown, date range
```

When `min_samples_before_training` is reached, SAGE raises a notification in the web UI:

> "Distillation dataset for meditation_app is ready: 247 samples across 6 task types.
> Export for fine-tuning: GET /distillation/meditation_app/export?format=alpaca"

The user can then fine-tune the student model using standard tools (Unsloth, LLaMA-Factory,
Hugging Face TRL) and point the `student.model` config at the fine-tuned version.

---

## New API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/distillation/{solution}/stats` | Sample counts, win rates, task type breakdown |
| `GET` | `/distillation/{solution}/export` | Export training dataset (`?format=alpaca\|sharegpt`) |
| `GET` | `/distillation/{solution}/comparisons` | Browse individual comparisons |
| `POST` | `/distillation/{solution}/promote` | Promote student to `student_only` for a task type |
| `GET` | `/llm/dual-status` | Current win rates, escalation rates, cost savings estimate |

---

## Implementation Plan

### Step 1 — DualLLMRunner skeleton
- `src/integrations/dual_llm_runner.py`
- `teacher_only` and `student_only` strategies (no comparison logic yet)
- `project.yaml` `llm_strategy:` parsing in `ProjectConfig`
- Unit tests: mock both providers

### Step 2 — student_first with confidence scoring
- Rule-based confidence scorer (no additional model required)
- Escalation logging to `data/distillation/`
- Integration tests: confirm teacher is called when student confidence is low

### Step 3 — parallel_compare
- Async concurrent generation (both providers called simultaneously)
- Judge scorer
- Comparison logging
- `/distillation/{solution}/stats` and `/distillation/{solution}/comparisons` endpoints

### Step 4 — Distillation export
- `/distillation/{solution}/export` with Alpaca and ShareGPT formats
- Web UI notification when `min_samples_before_training` reached
- `data/distillation/` included in `.gitignore` (may contain proprietary training data)

### Step 5 — Per-task-type promotion
- `task_overrides` in `project.yaml`
- `/distillation/{solution}/promote` endpoint
- Web UI: per-task-type win rate chart on LLM Settings page

---

## Files Added / Modified

| File | Change |
|------|--------|
| `src/integrations/dual_llm_runner.py` | New — DualLLMRunner class |
| `src/core/llm_gateway.py` | Check for `dual` strategy; delegate to DualLLMRunner |
| `src/core/project_loader.py` | Parse `llm_strategy:` from `project.yaml` |
| `src/interface/api.py` | Add `/distillation/` and `/llm/dual-status` endpoints |
| `tests/test_dual_llm_runner.py` | New — unit + integration tests |
| `solutions/starter/project.yaml` | Add commented-out `llm_strategy:` template |
| `.gitignore` | Add `data/distillation/` |
| `web/src/pages/LLMSettings.tsx` | Add win rate chart and promotion controls |

---

## Acceptance Criteria

- [ ] `mode: single` (default) produces zero behaviour change — all existing tests pass
- [ ] `teacher_only` logs every teacher response to `data/distillation/`
- [ ] `student_first`: student handles LIGHT tasks when confidence >= threshold; teacher called when below
- [ ] `parallel_compare`: both providers called concurrently; winner returned; loser logged
- [ ] `/distillation/{solution}/export` produces valid Alpaca-format JSONL
- [ ] Web UI shows dual-LLM status (win rates, escalation rate, estimated cost saving) on LLM Settings page
- [ ] All existing framework tests still pass (`make test`)
- [ ] `data/distillation/` is in `.gitignore`

---

## Relationship to Issue #1 (SAGE Framework SLM)

These are independent but complementary:

| | SAGE Framework SLM (Issue #1) | Teacher-Student (this issue) |
|---|---|---|
| **What it handles** | Framework tasks (setup, routing, YAML lint) | Solution domain tasks (analysis, review, planning) |
| **Model type** | Fixed 380M–1B, SAGE-aware | Configurable per solution |
| **Improvement loop** | SAGE doc fine-tuning (future) | Continuous distillation from teacher |
| **Who configures it** | Framework maintainers | Solution owners in `project.yaml` |
| **Required** | Optional (degrades gracefully) | Optional (single-LLM default unchanged) |

The SAGE Framework SLM (Issue #1) could serve as the **judge** in `parallel_compare` mode
once it is available — a natural integration point between the two features.

---

## Open Questions

1. **Fine-tuning toolchain**: Should SAGE ship a `make distill PROJECT=meditation_app` target
   that runs Unsloth locally, or just export the data and leave the fine-tuning to the user?
   Recommendation: export-only for now; fine-tuning is a separate concern.

2. **Privacy**: Distillation data may contain production logs. Should there be a
   `redact_pii: true` option in the distillation config that runs a lightweight PII scrubber
   before saving? Recommendation: yes, add as a future step.

3. **Multi-student**: Could a solution configure multiple student models and route by task type?
   e.g., Phi-3.5 for code review, Gemma for log analysis. Recommendation: supported via
   `task_overrides` pointing to different `student_model` keys — defer to Step 5.
