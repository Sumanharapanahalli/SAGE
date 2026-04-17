# sage-desktop Phase 3c — Onboarding Wizard

**Status:** design
**Branch:** `feature/sage-desktop-phase3c` (off main)
**Goal:** Let the user create a brand-new solution from a natural-language
description, entirely from inside sage-desktop — no FastAPI, no browser.

---

## 1. Why this phase

The user wants to build yoga, dancing, and medical-apps solutions with
sage-desktop *today*. Phase 3a made it possible to switch between
existing solutions; Phase 3c lets the user create new ones. Together,
these two are the critical path from "install sage-desktop" to
"productive first time."

The framework already has `src.core.onboarding.generate_solution(...)` —
it's been driving the HTTP `/onboarding/generate` route for months. We
just wire it into the sidecar and add a React wizard over the top.

---

## 2. Scope

**In scope:**
- `onboarding.generate` RPC in the sidecar (thin wrapper over
  `generate_solution`)
- Tauri `onboarding_generate` command (read-path — long-running LLM call,
  but the sidecar already serializes through its mutex)
- React `OnboardingWizard` page at `/onboarding` with 3 steps:
  1. Describe domain (textarea) + solution name (snake_case input)
  2. Optional: compliance standards, integrations, parent solution
  3. Review & generate → progress → show created files + "Switch to this
     solution" button
- Typed error handling for YAML validation failures and LLM unavailable
- Navigation: "+ New solution" entry in the Sidebar (next to the
  solution picker); wizard closes by navigating to the previous route

**Out of scope:**
- Org.yaml auto-add (no org UI in sage-desktop yet)
- Editing existing solutions (Phase 3b)
- Streaming LLM progress (wizard shows a single spinner; Phase 4)

---

## 3. Architecture

```
React OnboardingWizard
  useOnboardingGenerate()          (useMutation)
      │
      ▼
  invoke("onboarding_generate", {description, solution_name, ...})
      │
      ▼
Rust commands/onboarding.rs
  sidecar.read().await.call("onboarding.generate", params)
      │
      ▼
sidecar/handlers/onboarding.py
  generate_solution(...)           (existing framework code)
      │
      ▼
solutions/<name>/{project,prompts,tasks}.yaml
```

The generated solution lives on disk immediately. If the user clicks
"Switch to it", we reuse the Phase 3a `switchSolution` hook — the
wizard becomes a composition of two existing primitives (list +
switch) plus one new RPC.

### Error surface
The framework raises `ValueError` for YAML-validation failures and
`RuntimeError` for LLM-unavailable. The sidecar handler maps both to
JSON-RPC errors:

| Python exception | Code | DesktopError variant |
|---|---|---|
| `RuntimeError` (LLM unavailable) | `-32000` (`RPC_SIDECAR_ERROR`) | `SidecarDown` |
| `ValueError` (invalid YAML / bad name) | `-32602` (`RPC_INVALID_PARAMS`) | `InvalidParams` |
| `FileExistsError`-like `status: "exists"` | returned as `result` (not error) — UI treats it as a soft-fail | — |

No new error codes.

---

## 4. File structure

### Framework (existing — no changes)
- `src/core/onboarding.py` — already exposes `generate_solution`

### Sidecar
- **New:** `sage-desktop/sidecar/handlers/onboarding.py`
  - `generate(params)` — validates params, calls `generate_solution`,
    returns `{solution_name, path, status, files, suggested_routes}`
- **New:** `sage-desktop/sidecar/tests/test_onboarding.py`
- **Modify:** `sage-desktop/sidecar/app.py`
  - Import and register `onboarding.generate`

### Rust
- **New:** `sage-desktop/src-tauri/src/commands/onboarding.rs`
  - `onboarding_generate` Tauri command
- **Modify:** `sage-desktop/src-tauri/src/commands/mod.rs` (+ `pub mod onboarding;`)
- **Modify:** `sage-desktop/src-tauri/src/lib.rs` (register handler)

### React
- **New:** `sage-desktop/src/api/types.ts` — add `OnboardingParams`,
  `OnboardingResult`
- **Modify:** `sage-desktop/src/api/client.ts` — add `onboardingGenerate`
- **New:** `sage-desktop/src/hooks/useOnboarding.ts` — `useOnboardingGenerate`
- **New:** `sage-desktop/src/components/domain/OnboardingWizard.tsx`
- **New:** `sage-desktop/src/pages/Onboarding.tsx`
- **Modify:** `sage-desktop/src/App.tsx` — add `/onboarding` route
- **Modify:** `sage-desktop/src/components/layout/Sidebar.tsx` —
  "+ New solution" link

### Tests
- `sidecar/tests/test_onboarding.py` (+5–6 unit tests, all with mocked
  `generate_solution`)
- `src-tauri/src/commands/onboarding.rs` (none — proxy-only)
- React: `__tests__/hooks/useOnboarding.test.ts` (+3 tests),
  `__tests__/components/OnboardingWizard.test.tsx` (+5 tests)

### Docs
- `.claude/docs/interfaces/desktop-gui.md` — Phase 3c section
- `CLAUDE.md` — one-line update

---

## 5. UI flow

### Step 1 — Describe
- **Solution name** — snake_case text input, validated client-side
  (`^[a-z][a-z0-9_]*$`), max 40 chars
- **Description** — multi-line textarea, min 30 chars

### Step 2 — Options (all optional)
- **Compliance standards** — chip input (e.g. "ISO 9001", "IEC 62304")
- **Integrations** — chip input (e.g. "gitlab", "slack")
- **Parent solution** — dropdown of existing solutions from
  `useSolutions()` (empty = no parent)

### Step 3 — Review & generate
- Summary of what will be sent
- Primary action: **Generate**
- Disabled while pending; shows spinner with "Asking LLM…" hint
- On success: green panel with generated file names, size breakdown,
  and two buttons: **Switch to it** (calls `useSwitchSolution`) /
  **Stay on current**
- On error: red panel with the typed `DesktopError` + "Try again"

### Navigation
- Sidebar gains a "+ New solution" link above the solution footer.
- Wizard is a full-width page (not modal), so back/forward navigation
  works. Successful create stays on the wizard until the user clicks
  one of the two exit buttons.

---

## 6. Wire contract

### `onboarding.generate` request
```json
{
  "description": "Yoga instructor assistant that plans classes, scales intensity, and tracks student progress.",
  "solution_name": "yoga",
  "compliance_standards": ["ISO 9001"],
  "integrations": ["gitlab"],
  "parent_solution": ""
}
```
All fields other than `description` and `solution_name` are optional.

### `onboarding.generate` success result
```json
{
  "solution_name": "yoga",
  "path": "C:/.../solutions/yoga",
  "status": "created",
  "files": {
    "project.yaml": "…",
    "prompts.yaml": "…",
    "tasks.yaml": "…"
  },
  "suggested_routes": ["studio_ops", "student_tracking"],
  "message": "Solution 'yoga' created."
}
```
When `status == "exists"`, `files` is `{}` and the UI renders the
"already exists" message with no Switch button.

---

## 7. Testing targets

| Layer | New tests | What they cover |
|---|---|---|
| Sidecar pytest | 5–6 | happy path, missing description, bad name, LLM unavailable (RuntimeError), invalid YAML from LLM (ValueError), already-exists soft-fail |
| Rust cargo | 0 | proxy-only command; no logic to test |
| Vitest hook | 3 | mutation success, typed error, param pass-through |
| Vitest component | 5 | step navigation, client-side name validation, submit, success view switch-to-it button, error panel |

Total new: **13–14** on top of Phase 3a's 84 → ~97.

Framework tests unaffected.

---

## 8. Acceptance criteria

- Create a new "yoga" solution through the wizard → `solutions/yoga/`
  contains three valid YAML files and `workflows/`, `mcp_servers/`,
  `evals/` stubs.
- Click "Switch to it" → sidecar respawns and the new solution becomes
  active (verified by the Status page showing `project.name: "yoga"`).
- Try again with the same name → the UI shows the "already exists"
  soft-fail message with no Switch button.
- Attempt to generate without a description → button stays disabled;
  message explains the minimum length.
- With LLM unavailable → UI shows a red panel with `SidecarDown` error.
- All 5 test layers green (framework, sidecar, Rust, vitest, vite
  build).

---

## 9. Risk + mitigations

| Risk | Mitigation |
|---|---|
| Long LLM call blocks the sidecar's single-lane mutex | Accepted — sidecar is one user, one process. Spinner in UI is enough. |
| Generated YAML occasionally invalid | `generate_solution` already validates before writing; handler re-raises as `InvalidParams`. |
| User types a name with spaces / caps | Client-side regex + framework's `_sanitize_name` as a backstop. |
| Disk write fails mid-generation | `generate_solution` raises; UI shows the error. No partial-solution cleanup (accepted — matches HTTP behavior). |

---

## 10. Plan link

`docs/superpowers/plans/2026-04-17-sage-desktop-phase3c.md` — bite-sized
TDD plan follows.
