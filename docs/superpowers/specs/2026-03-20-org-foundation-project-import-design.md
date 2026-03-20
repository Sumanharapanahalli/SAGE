# Org Foundation + Project Import — Design Spec

**Date:** 2026-03-20
**Status:** Ready for implementation

---

## Goal

Give founders a way to define the company's mission, vision, and core values as the root context for all SAGE solutions. Add a folder-import path to onboarding so existing codebases can be scanned and converted into solutions, guided by an intent hint and an iterative LLM review loop.

---

## User Stories

1. Founder opens SAGE for the first time with no solutions — sees an empty-state card prompting them to define the organization first, then create their first solution.
2. Founder fills in org name, mission, vision, and core values in Settings → Organization. Saves. All future solution generation now receives this context automatically.
3. Founder opens the onboarding wizard, switches to "Import from folder", pastes a folder path and types "Build a QA agent that reviews firmware PRs against IEC 62304". SAGE scans the folder, generates solution YAML shaped by both the org mission and the intent hint.
4. Generated summary is shown in plain English — non-technical founder reads it and types "focus only on the embedded C code, ignore Python tooling" in the refine box. Regenerates. Repeats until satisfied. Clicks "Looks good — continue".
5. Technical co-founder switches to the YAML tab, edits `prompts.yaml` directly, then accepts.
6. LLM is not connected — scan button is disabled with a warning and a link to Settings → LLM.

---

## org.yaml Location

`org.yaml` is stored at `SAGE_SOLUTIONS_DIR/org.yaml` — the root of the solutions directory, one level above individual solutions. This is the existing convention used by `OrgLoader` (`src/core/org_loader.py` line 137). It is a company-wide file shared across all solutions. It is distinct from any per-solution YAML files. If it does not exist, `OrgLoader` gracefully degrades and `GET /org` returns an empty org object.

---

## Architecture

### New pages and components

| File | Purpose |
|---|---|
| `web/src/pages/settings/Organization.tsx` | Organization settings form |
| `web/src/components/dashboard/EmptyState.tsx` | Empty state card for zero-solution state |
| `web/src/components/onboarding/ImportFlow.tsx` | 3-step folder import flow |
| `web/src/components/onboarding/ReviewPanel.tsx` | Summary / YAML tab review component |

### Modified files

| File | Change |
|---|---|
| `web/src/App.tsx` | Add `<Route path="/settings/organization" element={<Organization />} />` |
| `web/src/pages/Onboarding.tsx` | Refactor to full-screen page; add import flow + mission banner + LLM gate |
| `web/src/pages/Dashboard.tsx` | Add empty-state card when no solutions exist |
| `web/src/pages/settings/Settings.tsx` | Add Organization tab/entry |
| `web/src/components/layout/Sidebar.tsx` | Add `/settings/organization` nav entry under Admin area |
| `web/src/components/layout/Header.tsx` | Add `'/settings/organization': 'Admin'` to ROUTE_TO_AREA |
| `web/src/registry/modules.ts` | Add `'organization'` entry with `route: '/settings/organization'` to MODULE_REGISTRY |
| `web/src/api/client.ts` | Add `saveOrg()`, `scanFolder()`, `refineGeneration()` + response types |
| `src/interface/api.py` | Add `PUT /org`, `POST /onboarding/scan-folder`, `POST /onboarding/refine`; modify `POST /onboarding/generate` to inject org context |
| `src/core/folder_scanner.py` | NEW — directory walker + file reader + token budget |

---

## Feature 1: Organization Settings page

**Route:** `/settings/organization`
**Nav:** Settings → Organization (Admin area in sidebar)

All 5 wiring steps required per CLAUDE.md:
1. Page: `web/src/pages/settings/Organization.tsx`
2. Route: `<Route path="/settings/organization" element={<Organization />} />` in `App.tsx`
3. Sidebar: nav entry under Admin area in `Sidebar.tsx`
4. Module registry: key `'organization'`, route `'/settings/organization'` in `modules.ts`
5. Header: `'/settings/organization': 'Admin'` in ROUTE_TO_AREA in `Header.tsx`

### Fields

| Field | Required | Notes |
|---|---|---|
| Organization name | No | Stored as `org.name` |
| Mission | Yes | One paragraph — the root all solutions branch from |
| Vision | No | Where the company is in 10 years |
| Core values | No | Free text, one value per line — split on newline when saving |

### Behaviour

- Page uses CSS vars (`var(--sage-sidebar-bg)` etc.) — inherits the active color scheme from the user menu. No separate appearance controls on this page.
- On save: `PUT /org` writes mission/vision/values into `org.yaml`. Returns updated org data.
- Linked solutions shown at the bottom (read-only list from `GET /org`).
- If `org.yaml` does not exist, it is created on first save.

### Backend: `GET /org` (existing endpoint — response shape)

Already implemented. Response shape used by this feature:

```
GET /org
Response: {
  org: {
    name?: str,
    mission?: str,
    vision?: str,
    core_values?: str[],
    root_solution?: str,
    solutions?: str[],
    knowledge_channels?: Record<string, { producers: str[], consumers: str[] }>
  },
  routes: [{ source: str, target: str }]
}
```

Frontend uses `org.mission` presence to determine the empty-state checkmark and mission banner visibility. No changes to this endpoint — read-only.

### Backend: `PUT /org`

```
Request:  { name?, mission?, vision?, core_values?: string[] }
Response: { status: "saved", org: { name, mission, vision, core_values } }
```

- Merges supplied fields into existing `org.yaml`. Does not overwrite fields not included in the request.
- After writing, calls `org_loader.reload()` to keep the in-memory org state consistent with the file.
- Returns the updated org data as read back from file after reload.

---

## Feature 2: Empty state on Dashboard

When `GET /config/projects` returns zero solutions, the dashboard shows a two-step guidance card:

1. **"Define your organization"** — links to `/settings/organization`. Shown with a checkmark once `GET /org` returns a non-empty `mission` field. The frontend checks this once on mount via a single `GET /org` call — no polling.
2. **"Create your first solution"** — links to `/onboarding`. Always enabled (skippable — a Skip link is shown beneath it). User is not forced to complete step 1 first.

Once at least one solution exists, the empty state card is replaced by the normal dashboard content.

---

## Feature 3: Full-screen Onboarding page

**Route:** `/onboarding`
The onboarding wizard becomes a full-screen page (not a modal). The chat panel is not rendered while on this route — no conflict.

### LLM connectivity gate

At the top of the page, the existing `GET /health` heartbeat result is used:
- LLM connected → normal flow
- LLM not connected → amber warning banner: "LLM is not connected — [Go to Settings → LLM]". The "Scan & generate" and "Generate" buttons are disabled until health check passes.

### Mission banner

When org has a mission defined (`GET /org` returns a non-empty `mission` field), a banner is shown at the top of Step 1:

```
Building under — [Org Name]
[Mission statement text]
```

Uses the accent color CSS var with low opacity background. Always visible during the wizard.

### Step 1: Input mode toggle

Two tabs in Step 1:

**"Describe it" tab** (existing behaviour, unchanged):
- Description textarea + solution name input
- Compliance + integrations checkboxes
- "Generate" button calls existing `POST /onboarding/generate`

**"Import from folder" tab** (new):
- Folder path input + Browse button (opens native OS file picker via `<input type="file" webkitdirectory>`)
- Intent hint textarea: "What do you want to build from this?" — placeholder examples shown
- Solution name input
- "Scan & generate" button (disabled if LLM not connected)

---

## Feature 4: Folder Import Flow (`ImportFlow.tsx`)

### Step 2: Scanning (single request with spinner)

After "Scan & generate" is clicked, a single `POST /onboarding/scan-folder` request is made. While it is in flight the UI shows a static progress list with a spinner on the last active item:

- Reading README files
- Reading docs / specs
- Reading source files
- Generating solution YAML…

This is a visual indicator only — not streaming. The backend performs all steps synchronously and returns a single response. On error, the spinner is replaced with an inline error message (see error handling below).

### Error handling for scan-folder

| Condition | HTTP status | Frontend display |
|---|---|---|
| Folder path does not exist or is not accessible | 400 `{"error": "folder_not_found", "message": "Folder not found: <path>"}` | Inline error below path input: "Folder not found. Check the path and try again." |
| Folder is empty or has no readable files | 400 `{"error": "folder_empty"}` | "No readable files found in this folder." |
| LLM call fails / times out | 503 `{"error": "llm_unavailable"}` | "Could not reach the LLM. Check Settings → LLM and try again." |
| LLM returns unparseable YAML | 500 `{"error": "generation_failed"}` | "Generation failed. Try again or describe the solution manually." |

All errors replace the spinner with the message and a "Try again" button that returns to Step 1.

### Step 3: Review & refine (`ReviewPanel.tsx`)

Two tabs:

**Summary tab (default):**
- Solution name + icon initial (first letter of solution name)
- Plain-English description paragraph
- "What it can do" — bullet list of task types
- Compliance badges
- Integration badges

**YAML tab:**
- Sub-tabs: `project.yaml` / `prompts.yaml` / `tasks.yaml`
- Each sub-tab shows an editable textarea with the raw YAML

Both tabs include:

**Amber refine box:**
- Label: "Not quite right? Tell SAGE what to change:"
- Feedback textarea (free text, no limit)
- "Regenerate →" button — calls `POST /onboarding/refine` with previous YAML + feedback
- No iteration limit — user can refine as many times as needed

**Action buttons:**
- "Looks good — continue →" — proceeds to compliance/integrations step (or directly to solution-ready if already inferred from scan)
- "Start over" — returns to Step 1

---

## Backend: `POST /onboarding/scan-folder`

**New file:** `src/core/folder_scanner.py`

### FolderScanner

`scan(folder_path: str, max_tokens: int = 24000) -> str`

Walk the directory tree. For each file:
1. Validate `folder_path` exists and is a directory — raise `FileNotFoundError` if not
2. Skip: `.git/`, `node_modules/`, `__pycache__/`, binary files, files > 500KB
3. Priority order: README files first, then `docs/`, then source files by extension (`.py`, `.ts`, `.js`, `.c`, `.cpp`, `.h`, `.md`, `.yaml`, `.json`)
4. Accumulate content up to `max_tokens` (estimated as `len(content) // 4`)
5. Return concatenated content with file path headers (`# --- path/to/file.py ---`)

### Endpoint request/response

```
POST /onboarding/scan-folder
Request: {
  folder_path: str,
  intent: str,        # "what do you want to build"
  solution_name: str
}
Response: {
  solution_name: str,
  files: { "project.yaml": str, "prompts.yaml": str, "tasks.yaml": str },
  summary: {
    name: str,
    description: str,
    task_types: [{ name: str, description: str }],
    compliance_standards: str[],
    integrations: str[]
  }
}
```

`org_context` is NOT a request field — the API handler reads `org.yaml` internally and injects mission/vision/values into the LLM prompt. The frontend never sends it.

LLM system prompt includes:
- Org mission, vision, core values (loaded from `org.yaml` — omitted silently if not set)
- User's intent hint
- Scanned folder content
- Instruction to generate solution YAMLs shaped by the intent, not just reflecting the raw codebase

### `POST /onboarding/refine`

```
Request: {
  solution_name: str,
  current_files: { "project.yaml": str, "prompts.yaml": str, "tasks.yaml": str },
  feedback: str
}
Response: same shape as scan-folder response
```

`org_context` is NOT a request field — auto-loaded from `org.yaml` inside the handler. Calls LLM with current YAML + feedback + org context. Returns updated YAML and updated summary.

---

## Org Context Injection

Every call to `POST /onboarding/generate`, `POST /onboarding/scan-folder`, and `POST /onboarding/refine` automatically receives the org context (mission + vision + core values) loaded from `org.yaml` inside the API handler. The LLM system prompt includes:

```
Company context:
  Mission: [mission]
  Vision: [vision]
  Core values:
    - [value 1]
    - [value 2]
```

If `org.yaml` has no mission set, this section is omitted silently — no error.

---

## Traceability

All scan, refine, and org-save operations are logged via `audit_logger.log_event()`:

```python
audit_logger.log_event(
    actor="human_via_onboarding",
    action_type="ONBOARDING_SCAN",        # or ONBOARDING_REFINE / ONBOARDING_COMPLETE / ORG_SAVED
    input_context=intent,
    output_content=generated_yaml_snapshot,
    metadata={"solution_name": ..., "folder_path": ...}
)
```

- `ONBOARDING_COMPLETE` written when user clicks "Looks good — continue" with the final YAML snapshot in `output_content`
- `ORG_SAVED` written when `PUT /org` is called with the new mission/vision/values

---

## Files Changed

| File | Change |
|---|---|
| `src/core/folder_scanner.py` | NEW — directory walker + file reader + token budget |
| `src/interface/api.py` | Add `PUT /org`, `POST /onboarding/scan-folder`, `POST /onboarding/refine`; modify `POST /onboarding/generate` to inject org context |
| `web/src/App.tsx` | Add `<Route path="/settings/organization" element={<Organization />} />` |
| `web/src/api/client.ts` | Add `saveOrg()`, `scanFolder()`, `refineGeneration()` + response types |
| `web/src/pages/Onboarding.tsx` | Refactor to full-screen; import flow + mission banner + LLM gate |
| `web/src/pages/settings/Organization.tsx` | NEW — org settings form |
| `web/src/pages/Dashboard.tsx` | Add empty-state guidance card |
| `web/src/components/layout/Sidebar.tsx` | Add Organization nav entry under Admin area |
| `web/src/components/layout/Header.tsx` | Add `'/settings/organization': 'Admin'` to ROUTE_TO_AREA |
| `web/src/registry/modules.ts` | Add `'organization'` entry (`route: '/settings/organization'`) to MODULE_REGISTRY |
| `web/src/components/onboarding/ImportFlow.tsx` | NEW — 3-step folder import (path+intent → scan → review) |
| `web/src/components/onboarding/ReviewPanel.tsx` | NEW — Summary/YAML tab review + refine loop |
| `web/src/components/dashboard/EmptyState.tsx` | NEW — zero-solution guidance card |
| `tests/test_folder_scanner.py` | NEW — unit tests for FolderScanner |
| `tests/test_onboarding_endpoints.py` | NEW — tests for scan-folder + refine + PUT /org |
