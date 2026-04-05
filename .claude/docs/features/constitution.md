# Solution Constitution

Per-solution "blue book" defining immutable principles, hard constraints, agent voice, and decision rules. The constitution shapes every agent's behavior by injecting a preamble into all system prompts.

## Overview

Every solution can optionally include a `constitution.yaml` that defines how agents should behave in that domain. This is the soul of the solution — it ensures agents maintain consistent principles regardless of task type.

## File Location

```
solutions/<name>/constitution.yaml
```

## YAML Schema

```yaml
meta:
  name: "MedTech Agent Constitution"
  version: 1
  last_updated: "2026-04-05"
  updated_by: "founder"

# Core principles — injected into every agent prompt, sorted by weight
principles:
  - id: safety-first
    text: "Patient safety overrides all other priorities."
    weight: 1.0    # 1.0 = non-negotiable, shown as [NON-NEGOTIABLE] in prompts
  - id: lean-iteration
    text: "Prefer smallest working increment over comprehensive plans."
    weight: 0.8

# Hard constraints — violations trigger automatic rejection
constraints:
  - "Never modify files in /critical/ without explicit human approval"
  - "All API changes must be backward compatible"

# Agent communication style
voice:
  tone: "precise, clinical, evidence-based"
  avoid: ["marketing speak", "vague estimates", "unsubstantiated claims"]

# Decision-making rules
decisions:
  default_approval_tier: "human"       # "human" or "auto"
  auto_approve_categories: ["docs", "tests", "formatting"]
  escalation_keywords: ["safety", "regulatory", "patient", "recall"]

# Domain knowledge priorities
knowledge:
  primary_sources: ["IEC 62304", "FDA 21 CFR Part 11"]
  trusted_repos: []
```

## How It Works

1. **Loading** — Constitution is loaded from the active solution's directory at startup
2. **Prompt Injection** — `build_prompt_preamble()` generates a structured text block injected into every agent's system prompt via `inject_into_prompt()`
3. **Constraint Checking** — `check_action()` validates proposed actions against hard constraints
4. **Escalation Detection** — `check_escalation()` flags text containing escalation keywords for human review
5. **Auto-Approve** — `can_auto_approve()` checks if a category (docs, tests) can bypass HITL
6. **Version History** — Every save auto-increments version and records who changed what

## Integration

Constitution is injected in `src/agents/universal.py` after SKILL.md injection:

```python
from src.core.constitution import get_constitution
constitution = get_constitution()
system_prompt = constitution.inject_into_prompt(system_prompt)
```

This is non-blocking — if no constitution exists, the original prompt passes through unchanged.

## API Endpoints

All under `/constitution` prefix:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/constitution` | Full constitution data |
| GET | `/constitution/stats` | Counts and status |
| GET | `/constitution/validate` | Validation errors |
| GET | `/constitution/preamble` | Generated prompt preamble |
| GET | `/constitution/history` | Version history |
| GET | `/constitution/principles` | All principles |
| POST | `/constitution/principles` | Add principle |
| PUT | `/constitution/principles/{id}` | Update principle |
| DELETE | `/constitution/principles/{id}` | Remove principle |
| GET | `/constitution/constraints` | All constraints |
| POST | `/constitution/constraints` | Add constraint |
| PUT | `/constitution/voice` | Update voice settings |
| PUT | `/constitution/decisions` | Update decision rules |
| POST | `/constitution/check-action` | Check action against constraints |
| POST | `/constitution/check-escalation` | Check for escalation keywords |
| POST | `/constitution/save` | Save to disk (auto-increments version) |
| POST | `/constitution/reload` | Reload from disk |

## Web UI

6-tab dashboard at `/constitution`:

1. **Overview** — Stats cards (principles, constraints, version, voice/decisions status)
2. **Principles** — Add/edit/remove with weight sliders, non-negotiable indicators
3. **Constraints** — Manage hard rules with add/remove
4. **Voice & Decisions** — Configure tone, auto-approve categories, escalation keywords
5. **Preview** — Live preview of the preamble injected into agent prompts
6. **History** — Version history with timestamps and author attribution

## Tests

47 tests in `tests/test_constitution.py` covering: loading, CRUD, validation, prompt injection, constraint checking, escalation, thread safety, persistence, and version history.
