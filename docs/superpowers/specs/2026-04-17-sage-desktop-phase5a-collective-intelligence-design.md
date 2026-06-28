# Phase 5a — Collective Intelligence Browser Design

**Date:** 2026-04-17
**Branch:** feature/sage-desktop-phase5b (continuation branch; Phase 5a stacks on top of 5b and 5c)
**Status:** approved

## 1. Goal

Expose SAGE's cross-solution knowledge-sharing surface
(`src/core/collective_memory.py` → `CollectiveMemory`) in sage-desktop
so operators can browse, search, publish, validate, and triage help
requests without FastAPI. Collective intelligence is the "knowledge
that compounds across teams" surface (Collective Intelligence doc
§Overview) — making it a first-class desktop page turns it from a
web-only inspection tool into the primary UI for multi-solution
knowledge curation in air-gapped / port-restricted environments.

Phase 5c already shipped the *intra-solution* memory browser
(`/knowledge`). Phase 5a ships its *cross-solution* counterpart
(`/collective`): git-backed learnings and help requests shared across
every solution on this host.

## 2. Non-goals

- No attempt to ship a new git client or credential manager — the
  existing `CollectiveMemory._git_run` subprocess calls handle push /
  pull with the environment's ambient git config. Offline repos
  (`_git_available = False`) degrade to read/write-local only.
- No remote-URL or auto-push configuration from the desktop — those
  are repo-level setup concerns owned by whoever bootstraps the
  `.collective` directory. The UI displays the current state but does
  not edit `config.yaml`.
- No constitution-style proposal editor for *agent-authored* learning
  drafts. Agents publishing learnings still flow through the existing
  `collective_publish` proposal action, unchanged. The desktop shows
  gated trace_ids in the Approvals page (Phase 1, already shipped).
- No CRUD for validation entries beyond the existing
  `validate_learning` call (which increments `validation_count` and
  boosts `confidence`). Un-validating is not an operation the Python
  surface supports, so the UI doesn't invent one.
- No bulk-import of learnings from external sources. The
  `extract_learning_from_result` static helper exists for agent
  pipelines, not operator hand-typing.
- No dedicated help-request inbox routing or notifications. The page
  is pull-based (operator opens it to triage). Cross-session alerts
  are a later phase.

## 3. RPC surface

Twelve new methods under the `collective.*` namespace. All methods
call into the module-level lazy singleton from
`get_collective_memory()`, wrapped by a `_require_cm` guard that
returns a typed `SidecarError` when import fails.

| Method | Params | Result |
|---|---|---|
| `collective.list_learnings` | `{ solution?, topic?, limit?, offset? }` | `{ entries, total, limit, offset }` |
| `collective.get_learning` | `{ id }` | `{ learning }` or `{ learning: null }` |
| `collective.search_learnings` | `{ query, tags?, solution?, limit? }` | `{ query, results, count }` |
| `collective.publish_learning` | `{ author_agent, author_solution, topic, title, content, tags?, confidence?, source_task_id?, proposed_by? }` | `{ id, gated, trace_id? }` |
| `collective.validate_learning` | `{ id, validated_by }` | `{ learning }` |
| `collective.list_help_requests` | `{ status?, expertise? }` | `{ entries, count }` |
| `collective.create_help_request` | `{ title, requester_agent, requester_solution, urgency?, required_expertise?, context? }` | `{ id }` |
| `collective.claim_help_request` | `{ id, agent, solution }` | `{ request }` |
| `collective.respond_to_help_request` | `{ id, responder_agent, responder_solution, content }` | `{ request }` |
| `collective.close_help_request` | `{ id }` | `{ request }` |
| `collective.sync` | `{}` | `{ pulled, indexed }` |
| `collective.stats` | `{}` | `{ learning_count, help_request_count, help_requests_closed, topics, contributors, git_available, repo_path }` |

**`list_learnings`** — direct pass-through to
`CollectiveMemory.list_learnings(solution, topic, limit, offset)`.
`limit` defaults to 50 and is clamped to `[1, 500]`. `offset` defaults
to 0 and must be `>= 0`. Since the Python method already slices
`[offset:offset+limit]` internally, the handler also re-reads the
full glob to compute `total` (the underlying count of YAML files
matching the filters). This matches the Phase 5c knowledge pattern.

**`get_learning`** — pass-through with `{ learning: null }` when not
found (distinct from error — "not found" is a valid result here).

**`search_learnings`** — pass-through. `query` may be empty (the
Python code treats empty query as "return filter-matched entries"),
so the handler allows `query: ""` as long as it's a string. `limit`
default 10, clamped to `[1, 50]`.

**`publish_learning`** — the interesting one. Calls
`CollectiveMemory.publish_learning(learning_dict, proposed_by)`. If
the singleton has `require_approval=True`, the return value is a
proposal `trace_id` and the handler returns
`{ id: null, gated: true, trace_id: <string> }`. If approval is off,
the return value is the learning id and the handler returns
`{ id: <uuid>, gated: false }`. The UI uses `gated` to choose between
"Published" and "Submitted as proposal" toasts.

**`validate_learning`** — pass-through. `validated_by` is required
(sidecar rejects empty strings with `InvalidParams`) so every
validation is attributable in the git log.

**`list_help_requests`** — pass-through. `status` defaults to
`"open"`, clamped to `{open, closed}`. `expertise` is optional list
of strings; the Python side treats it as OR-match against
`required_expertise`. The handler also returns a top-level `count`
for convenience (= `len(entries)`).

**`create_help_request`** — pass-through. `title`,
`requester_agent`, and `requester_solution` are required
(`InvalidParams` if empty). `urgency` defaults to `"medium"`,
clamped to `{low, medium, high, critical}`.

**`claim_help_request`** — pass-through. Already-claimed errors from
the Python layer become `SidecarError` with the original message.

**`respond_to_help_request`** — pass-through. `content` is required
and non-empty.

**`close_help_request`** — pass-through. Moves file from `open/` to
`closed/` and commits.

**`sync`** — pass-through to `CollectiveMemory.sync()`, which pulls
from remote (no-op when `_git_available` or `remote_url` are false)
and rebuilds the vector index. Returns `{ pulled: bool, indexed:
int }` directly.

**`stats`** — calls `CollectiveMemory.get_stats()` and augments with
`git_available` (read from the singleton's `_git_available` flag) and
`repo_path`. These two are display-only so the UI can show the repo
location and whether commits are being recorded.

**Error mapping:**
- Invalid params (missing field, wrong type, out-of-range
  limit/offset, unknown status/urgency) → `InvalidParams` (-32602)
- `CollectiveMemory` singleton import or construction failure →
  `SidecarError` (-32000) with message
  `"collective handlers are not wired"`
- Underlying `ValueError` from the Python layer (e.g., help request
  not found, already claimed) → `SidecarError` (-32000) with the
  original message
- Git subprocess failures inside `CollectiveMemory` already degrade
  to warnings + `_git_available = False`; the handler surfaces this
  through the `stats.git_available` field rather than as an error

## 4. Page layout — `/collective`

```
┌──────────────────────────────────────────────────────────────────┐
│ Collective Intelligence                                          │
│ repo: <path>     git: available|offline     [ Sync ]             │
│ N learnings · M open help · K closed                             │
│                                                                  │
│ [ Learnings ] [ Help Requests ] [ Stats ]                        │
│                                                                  │
│ ┌── Learnings tab ─────────────────────────────────────────────┐ │
│ │ Filters: solution [___]  topic [___]  tags [__,__]           │ │
│ │ Search:  [__________]  [Go]                                  │ │
│ │ ────                                                         │ │
│ │ title       solution/topic   conf 0.85   vc 3    [✓ Validate]│ │
│ │ content preview (200 chars) ▶ expand                         │ │
│ │ ────                                                         │ │
│ │ < Prev   (1–50 of N)   Next >                                │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ ── Publish learning (collapsible, below tabs) ──                 │
│  title / topic / author_agent / author_solution / content        │
│  tags (comma-separated) / confidence (0–1) / source_task_id (opt)│
│  [ Publish ]  → "Published id=<uuid>"  or                        │
│                  "Submitted as proposal trace_id=<uuid>"         │
└──────────────────────────────────────────────────────────────────┘
```

**Help Requests tab:**

```
[ Open ] [ Closed ]      expertise filter: [__, __]

┌──────────────────────────────────────────────────────────────────┐
│ [hr-abc123]  I2C bus recovery help             urgency: HIGH     │
│ requester: developer @ automotive                                │
│ expertise needed: i2c, stm32                                     │
│ context preview...                            ▶ expand           │
│                                                                  │
│ [ Claim ]   [ Respond ]   [ Close ]                              │
│                                                                  │
│ Responses (2):                                                   │
│   firmware_eng @ iot_medical — "Try bus recovery sequence..."    │
│   analyst @ medtech — "Also check pull-ups..."                   │
└──────────────────────────────────────────────────────────────────┘

── Create help request (collapsible) ──
 title / requester_agent / requester_solution / urgency dropdown
 required_expertise (comma-separated) / context
 [ Create ]
```

When `git_available = false`, the header shows "git: offline
(local-only commits suppressed)" in amber and the Sync button is
disabled. All other operations still work — the Python layer writes
YAML directly and skips the commit step.

**Stats tab:** simple table layout — topics histogram (topic → count,
sorted desc), contributors histogram (solution → count, sorted desc),
and a summary block with the four global counters. No charts library;
horizontal bars are CSS-only `div` widths.

## 5. File structure

```
sage-desktop/
├─ sidecar/
│  ├─ handlers/
│  │  └─ collective.py                 (new — 12 methods + _require_cm)
│  └─ tests/
│     └─ test_collective.py            (new — ~25 tests, fake + real roundtrip)
├─ src-tauri/
│  └─ src/commands/
│     └─ collective.rs                 (new — 12 proxies)
└─ src/
   ├─ api/
   │  ├─ types.ts                      (+ CollectiveLearning, HelpRequest,
   │  │                                   HelpRequestResponse,
   │  │                                   CollectiveListResult,
   │  │                                   CollectiveSearchResult,
   │  │                                   CollectiveStats,
   │  │                                   CollectivePublishResult)
   │  └─ client.ts                     (+ 12 client functions)
   ├─ hooks/
   │  └─ useCollective.ts              (queries + mutations)
   ├─ components/domain/
   │  ├─ LearningRow.tsx               (collapse/expand, metadata, validate)
   │  ├─ PublishLearningForm.tsx       (title/topic/content/tags/confidence)
   │  ├─ HelpRequestCard.tsx           (claim/respond/close actions)
   │  ├─ CreateHelpRequestForm.tsx
   │  ├─ RespondForm.tsx               (inline response textarea)
   │  └─ CollectiveStats.tsx           (histograms + counters)
   ├─ pages/
   │  └─ Collective.tsx                (composes above, tabs + header)
   └─ __tests__/
      ├─ hooks/useCollective.test.ts
      ├─ components/LearningRow.test.tsx
      ├─ components/HelpRequestCard.test.tsx
      ├─ components/PublishLearningForm.test.tsx
      ├─ components/CreateHelpRequestForm.test.tsx
      ├─ components/CollectiveStats.test.tsx
      └─ pages/Collective.test.tsx
```

Route wiring updates:
- `src/App.tsx` — `<Route path="collective" element={<Collective />} />`
- `src/components/layout/Sidebar.tsx` — new entry `{ to: "/collective", label: "Collective" }` below Knowledge
- `src/components/layout/Header.tsx` — title mapping `"/collective": "Collective Intelligence"`

## 6. Wire contract (TypeScript)

```typescript
export interface CollectiveLearning {
  id: string;
  author_agent: string;
  author_solution: string;
  topic: string;
  title: string;
  content: string;
  tags: string[];
  confidence: number;
  validation_count: number;
  created_at: string;
  updated_at: string;
  source_task_id: string;
}

export interface HelpRequestResponse {
  responder_agent: string;
  responder_solution: string;
  content: string;
  created_at: string;
}

export interface HelpRequestClaim {
  agent: string;
  solution: string;
  claimed_at: string;
}

export type HelpRequestStatus = "open" | "claimed" | "closed";
export type HelpRequestUrgency = "low" | "medium" | "high" | "critical";

export interface HelpRequest {
  id: string;
  title: string;
  requester_agent: string;
  requester_solution: string;
  status: HelpRequestStatus;
  urgency: HelpRequestUrgency;
  required_expertise: string[];
  context: string;
  created_at: string;
  claimed_by: HelpRequestClaim | null;
  responses: HelpRequestResponse[];
  resolved_at: string | null;
}

export interface CollectiveListResult {
  entries: CollectiveLearning[];
  total: number;
  limit: number;
  offset: number;
}

export interface CollectiveSearchResult {
  query: string;
  results: CollectiveLearning[];
  count: number;
}

export interface CollectivePublishResult {
  id: string | null;
  gated: boolean;
  trace_id?: string;
}

export interface CollectiveHelpListResult {
  entries: HelpRequest[];
  count: number;
}

export interface CollectiveStats {
  learning_count: number;
  help_request_count: number;
  help_requests_closed: number;
  topics: Record<string, number>;
  contributors: Record<string, number>;
  git_available: boolean;
  repo_path: string;
}
```

## 7. Testing targets

- **Sidecar** (`sidecar/tests/test_collective.py`): +25 tests covering
  - 12 happy-path method calls (one per method)
  - 8 `InvalidParams` rejections (missing required fields, wrong
    types, out-of-range limit/offset, unknown status/urgency)
  - 2 `publish_learning` flows — one with `require_approval=True`
    returning `gated/trace_id`, one with `require_approval=False`
    returning `id`
  - 2 error-propagation cases (help request not found,
    already-claimed)
  - 1 full roundtrip with a real `CollectiveMemory` bound to a
    temporary directory (creates the git repo, publishes a learning,
    lists it, searches for it, validates it)
  - Total sidecar: 176 → 201
- **Rust** (`src-tauri`): no new tests — proxy-only, same pattern as
  Phase 5b and 5c.
- **React** (`src/__tests__/`): +25 tests
  - 6 hook tests (list/search/stats queries, publish/validate/create
    mutations with invalidation assertions)
  - 3 `LearningRow` (render metadata, expand/collapse, validate click)
  - 3 `HelpRequestCard` (claim/respond/close state transitions)
  - 3 `PublishLearningForm` (submit payload, disabled until valid,
    tag comma-split)
  - 3 `CreateHelpRequestForm` (submit payload, urgency dropdown,
    disabled until valid)
  - 2 `CollectiveStats` (histogram rendering, empty-state)
  - 3 `Collective` page (tab switching, sync button, offline banner)
  - +1 Sidebar entry test (existing `Sidebar.test.tsx`)
  - +1 route test (existing page/route tests)
  - Total vitest: 152 → 177
- **Integration**: extend `tests/test_sage_desktop_e2e.py` (existing
  Phase 1 e2e harness) with one roundtrip subprocess call —
  `collective.stats` against a temp-dir sidecar — to confirm the
  handler wires through NDJSON end-to-end.

## 8. Law 1 positioning

The Five Laws (CLAUDE.md) mandate "Agents propose. Humans decide.
Always." This phase interacts with the approval gate in two distinct
ways, and the distinction must be explicit in code and UI.

**Agent-authored publishes go through the proposal queue.** When
`CollectiveMemory` is constructed with `require_approval=True`
(default, production config), `publish_learning` creates a
`collective_publish` proposal and returns the `trace_id`. The desktop
surfaces this as `gated: true` in the response and displays
"Submitted as proposal `<trace_id>`" — the operator then reviews and
approves in the existing Phase 1 `/approvals` page. Identical
behavior to the FastAPI `/collective/learnings` route.

**Operator-driven actions in the desktop UI bypass the queue.** When
an operator presses Validate, Claim, Respond, or Close, the desktop
calls the RPC directly — no proposal is created. This matches the
Law 1 pattern already established by Phase 3b (YAML authoring),
Phase 5b (Constitution), and Phase 5c (Knowledge adds/deletes):
**the human pressing the button IS the approval**. The audit trail
is the git commit log, not the proposal store.

**Operator-driven publishes follow the framework's approval policy
— we do not add a desktop-side override.** The
`CollectiveMemory` singleton's `require_approval` flag (default
`True` in production config) decides whether any publish — from an
agent or from the operator — is gated. The desktop passes
`proposed_by = "operator@desktop"` (or a user-identity string when
available) on the RPC so the proposal, if one is created, is clearly
attributed. The UI then reacts to whatever the Python layer returns:
`gated: true` ⇒ "Submitted as proposal `<trace_id>`"; `gated: false`
⇒ "Published id=`<uuid>`". This keeps a single source of truth for
approval policy and prevents the desktop from silently writing
past a framework-mandated gate.

**Help request operations are never gated.** `create_help_request`,
`claim_help_request`, `respond_to_help_request`, and
`close_help_request` have no proposal-queue path in the Python layer
and never will — help requests are collaborative workflow artifacts,
not proposals. The desktop calls them directly.

**Destructive ops require confirmation in the UI.**
`close_help_request` is reversible at the filesystem level (move
back from closed/ to open/) but not through any exposed API, so the
UI treats it as destructive: two-click confirm, same pattern as
Phase 5c Knowledge delete. `sync` is also surfaced as an explicit
button (never auto-fired) because git pull can conflict.

## 9. Documentation updates

- **`.claude/docs/interfaces/desktop-gui.md`** — add Phase 5a section
  mirroring Phase 5c format: scope, RPC surface, Law 1 positioning,
  acceptance criteria. Update phase matrix.
- **`.claude/docs/features/collective-intelligence.md`** — add a
  "sage-desktop integration" note pointing to the `/collective`
  route.
- **`CLAUDE.md`** — extend the sage-desktop blurb with Phase 5a: "…
  Phase 5a adds the `/collective` route + `collective.*` RPC so
  operators can browse, search, publish, validate learnings and
  triage help requests across every solution on this host."

## 10. Acceptance criteria

- `/collective` page loads; header shows repo path, git
  availability, and the three counters from `stats`.
- Learnings tab paginates through entries 50 at a time; filters for
  solution/topic/tags narrow the result; search bar runs
  `search_learnings` with the current filters applied.
- Validate button on a learning row increments `validation_count`
  and bumps `confidence` within the displayed row (cache
  invalidation refreshes the list).
- Help Requests tab toggles between Open and Closed; expertise filter
  narrows results; Claim / Respond / Close actions all succeed and
  refresh the card without a full page reload.
- Publish form submits and displays either "Published" (ungated) or
  "Submitted as proposal `<trace_id>`" (gated) depending on the
  framework setting.
- Create help request form submits and the new request appears in
  the Open list.
- Sync button triggers `collective.sync` and displays `pulled/
  indexed` counts; disabled when `git_available = false`.
- Stats tab renders the four counters + two histograms.
- When the `CollectiveMemory` singleton is unwired
  (import failure), every tab shows a typed `SidecarError` with the
  message `"collective handlers are not wired"` and no operations
  are attempted.
- All new tests green; no regressions in the existing 176 sidecar /
  ~20 Rust / 152 vitest suites.
