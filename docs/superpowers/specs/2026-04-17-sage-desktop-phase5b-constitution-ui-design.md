# Phase 5b — Constitution UI Design

**Date:** 2026-04-17
**Branch:** feature/sage-desktop-phase5b (off main)
**Status:** approved

## 1. Goal

Expose the per-solution **Constitution** (`src/core/constitution.py`) in
sage-desktop so regulated-industry operators can author principles,
constraints, voice, and decision rules without leaving the app — and
without FastAPI. The Constitution is what every agent's system prompt
is *prepended* with, so it is the single highest-leverage
solution-level configuration in SAGE.

Phase 5b is the desktop counterpart to `web/src/pages/Constitution.tsx`
(if it exists) — but the sidecar already has everything needed, so
adding the UI is a straightforward NDJSON exposure.

## 2. Non-goals

- No approval-queue integration. Operator edits to the constitution
  are the operator's own action, same rationale as YAML authoring
  (Phase 3b). If an *agent* proposes a constitution change, that
  still lives in the proposal queue as a `yaml_edit` against
  `constitution.yaml` — unchanged.
- No migration tooling. If a constitution is malformed on disk, the
  UI surfaces the validation errors; we do not attempt auto-repair.
- No diff/merge UI over `_history`. Version history is shown as a
  read-only timeline (version, timestamp, changed_by).

## 3. RPC surface

Four new methods:

| Method | Params | Result |
|---|---|---|
| `constitution.get` | `{}` | `{ data, stats, preamble, history, errors }` |
| `constitution.update` | `{ data, changed_by? }` | `{ stats, preamble, version, path }` |
| `constitution.preamble` | `{}` | `{ preamble }` |
| `constitution.check_action` | `{ action_description }` | `{ allowed, violations }` |

**`constitution.get`** — reads disk-backed state. Returns:
- `data` — full dict (meta, principles, constraints, voice, decisions, knowledge, _history)
- `stats` — the `get_stats()` dict (counts)
- `preamble` — current `build_prompt_preamble()` output
- `history` — `get_version_history()` list
- `errors` — `validate()` output; `[]` = valid

**`constitution.update`** — replaces the full `data`. Validation runs
before write; on failure returns `InvalidParams` with the error list.
On success auto-increments version, appends to `_history`, and writes
to disk via `Constitution._data = data; save(changed_by)`.

**`constitution.preamble`** — cheap getter for the preamble-preview
pane; redundant with `get().preamble` but lets the UI refresh without
re-reading disk.

**`constitution.check_action`** — dry-run the constraint checker
against a free-text action description. Used by the UI to let
operators verify that a constraint catches the cases they care about
before saving.

Error mapping:
- Validation failures → `InvalidParams` (-32602)
- I/O failures → `SidecarError` (-32000)
- Import failure (Constitution module unavailable) → `SidecarError`
  with `message: "constitution handlers are not wired"`

## 4. Page layout — `/constitution`

```
┌───────────────────────────────────────────────────────────────┐
│ Constitution                                                  │
│ <solution-name>  v{version}  last updated {when} by {who}     │
│ ┌─────────────────────────────────┬─────────────────────────┐ │
│ │  Editor                         │  Preview / Validator    │ │
│ │ ┌─────────────────────────────┐ │ ┌─────────────────────┐ │ │
│ │ │ Principles (weighted)        │ │ │ Preamble (injected) │ │ │
│ │ │  id / text / weight / remove │ │ │   live preview      │ │ │
│ │ │  [ + add principle ]         │ │ └─────────────────────┘ │ │
│ │ └─────────────────────────────┘ │ ┌─────────────────────┐ │ │
│ │ ┌─────────────────────────────┐ │ │ Action checker      │ │ │
│ │ │ Constraints                 │ │ │   textarea + button │ │ │
│ │ │  text / remove              │ │ │   → allowed / viols │ │ │
│ │ │  [ + add constraint ]       │ │ └─────────────────────┘ │ │
│ │ └─────────────────────────────┘ │ ┌─────────────────────┐ │ │
│ │ ┌─────────────────────────────┐ │ │ Version history     │ │ │
│ │ │ Voice: tone + avoid[]       │ │ │   v / when / who    │ │ │
│ │ └─────────────────────────────┘ │ └─────────────────────┘ │ │
│ │ ┌─────────────────────────────┐ │                         │ │
│ │ │ Decisions:                  │ │                         │ │
│ │ │   auto_approve_categories[] │ │                         │ │
│ │ │   escalation_keywords[]     │ │                         │ │
│ │ └─────────────────────────────┘ │                         │ │
│ │                                 │                         │ │
│ │ [ Save ]  [ Revert ]            │                         │ │
│ └─────────────────────────────────┴─────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

Save is disabled until the draft diverges from loaded state or
validation fails.

## 5. File structure

```
sage-desktop/
├─ sidecar/
│  ├─ handlers/
│  │  └─ constitution.py          (new — 4 methods + _require_ctx wiring)
│  └─ tests/
│     └─ test_constitution.py     (new — 10-12 unit tests with fake/real)
├─ src-tauri/
│  └─ src/commands/
│     └─ constitution.rs          (new — 4 proxy commands)
└─ src/
   ├─ api/
   │  ├─ types.ts                 (+ ConstitutionData, ConstitutionStats, ConstitutionState, CheckActionResult)
   │  └─ client.ts                (+ 4 client functions)
   ├─ hooks/
   │  └─ useConstitution.ts       (useConstitution, useUpdateConstitution, useCheckAction)
   ├─ components/domain/
   │  ├─ PrinciplesEditor.tsx     (list + add + remove + weight slider)
   │  ├─ ConstraintsEditor.tsx    (list + add + remove)
   │  ├─ VoiceEditor.tsx          (tone + avoid)
   │  ├─ DecisionsEditor.tsx      (auto_approve_categories + escalation_keywords)
   │  ├─ PreamblePreview.tsx      (displays preamble text)
   │  ├─ ActionChecker.tsx        (textarea + check button + result)
   │  └─ VersionHistoryList.tsx   (timeline)
   ├─ pages/
   │  └─ Constitution.tsx         (composes above)
   └─ __tests__/
      ├─ hooks/useConstitution.test.ts
      ├─ components/PrinciplesEditor.test.tsx
      ├─ components/ConstraintsEditor.test.tsx
      ├─ components/ActionChecker.test.tsx
      └─ pages/Constitution.test.tsx
```

## 6. Wire contract (TypeScript)

```typescript
export interface ConstitutionPrinciple {
  id: string;
  text: string;
  weight: number; // 0.0–1.0, 1.0 = non-negotiable
}

export interface ConstitutionMeta {
  name: string;
  version: number;
  last_updated: string;
  updated_by: string;
}

export interface ConstitutionVoice {
  tone?: string;
  avoid?: string[];
}

export interface ConstitutionDecisions {
  auto_approve_categories?: string[];
  escalation_keywords?: string[];
}

export interface ConstitutionData {
  meta?: ConstitutionMeta;
  principles?: ConstitutionPrinciple[];
  constraints?: string[];
  voice?: ConstitutionVoice;
  decisions?: ConstitutionDecisions;
  knowledge?: Record<string, unknown>;
  _history?: Array<{ version: number; changed_by: string; timestamp: string }>;
}

export interface ConstitutionStats {
  is_empty: boolean;
  name: string;
  version: number;
  principle_count: number;
  constraint_count: number;
  non_negotiable_count: number;
  has_voice: boolean;
  has_decisions: boolean;
  has_knowledge: boolean;
  history_entries: number;
}

export interface ConstitutionState {
  data: ConstitutionData;
  stats: ConstitutionStats;
  preamble: string;
  history: Array<{ version: number; changed_by: string; timestamp: string }>;
  errors: string[];
}

export interface CheckActionResult {
  allowed: boolean;
  violations: string[];
}
```

## 7. Testing targets

- Sidecar: +10 unit tests (`handlers/constitution`) → 167 total
- Rust: no new tests (proxy-only)
- React: +5 hook tests, +3 principles-editor, +3 constraints-editor,
  +2 action-checker, +1 page-smoke, +1 sidebar entry → 148 total

## 8. Law 1 note

Operator-authored constitutions bypass the proposal queue — this is
consistent with Phase 3b YAML authoring. When an *agent* proposes a
constitution change, it still flows through the existing `yaml_edit`
proposal kind so the audit trail remains uniform.

## 9. Acceptance criteria

- `/constitution` page loads current constitution, or shows an empty
  editor if `is_empty`.
- Adding a principle, saving, and reloading preserves the addition
  and bumps `version`.
- Action checker accurately reports constraint matches (mirrors
  `Constitution.check_action` output).
- Validation errors surface inline and block save.
- Preamble preview updates live as the editor is modified.
- All new tests green; no regressions in 133-test suite.
