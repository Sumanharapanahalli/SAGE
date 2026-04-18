# Phase 5c — Knowledge Browser Design

**Date:** 2026-04-17
**Branch:** feature/sage-desktop-phase5c (off main)
**Status:** approved

## 1. Goal

Expose the active solution's vector memory (`src/memory/vector_store.py`
→ `VectorMemory`) in sage-desktop so operators can browse, search, add,
and delete entries without FastAPI. The vector store is the
"compounding intelligence" surface (Law 3) — making it visible is what
turns it from a black box into an inspectable training signal.

## 2. Non-goals

- No audit-log exposure — already shipped under `/audit`.
- No collective-intelligence browser — that's cross-solution,
  git-backed, and deserves its own phase.
- No approval-queue integration for operator-driven add/delete. Same
  rationale as Phase 3b YAML authoring and Phase 5b Constitution: the
  human typing in the UI is the human's own action, not an agent
  proposal. Agent-proposed add/delete still flows through the existing
  STATEFUL/DESTRUCTIVE proposal kinds, unchanged.
- No bulk-import UI. The `/knowledge/sync` FastAPI route exists for
  crawling a directory and ingesting chunks, but it's out of scope for
  the operator-facing inspection surface.

## 3. RPC surface

Five new methods:

| Method | Params | Result |
|---|---|---|
| `knowledge.list` | `{ limit?, offset? }` | `{ entries, total, limit, offset }` |
| `knowledge.search` | `{ query, top_k? }` | `{ query, results, count }` |
| `knowledge.add` | `{ text, metadata? }` | `{ id, text, metadata }` |
| `knowledge.delete` | `{ id }` | `{ id, deleted }` |
| `knowledge.stats` | `{}` | `{ total, collection, backend, solution }` |

`list` — returns the entries slice and the total count. Defaults:
`limit=50`, `offset=0`. `limit` is clamped to `[1, 500]`.

`search` — calls `VectorMemory.search(query, k=top_k)`. Default
`top_k=10`, clamped to `[1, 50]`. Returns the raw strings from the
search backend. The result shape keeps `results` as an array of
`{ text, score?, metadata? }` so a future backend that returns scores
can populate them without breaking the wire contract.

`add` — calls `add_entry(text, metadata)`. Validates `text` is a
non-empty string. Returns the generated id.

`delete` — calls `delete_entry(id)`. Returns `{ id, deleted }` where
`deleted` is whatever the underlying `delete_entry` reports; false
means the id didn't exist.

`stats` — surfaces the three degradation modes (`full | lite |
minimal`) so the UI can tell operators when semantic search is
unavailable. `collection` is the chroma collection name.

Error mapping:
- Invalid params (wrong type, empty string, out-of-range limit) →
  `InvalidParams` (-32602)
- Vector store unavailable (solution not wired, or VectorMemory import
  failed) → `SidecarError` (-32000) with
  `message: "knowledge handlers are not wired"`
- Underlying I/O or embedding failures → `SidecarError` with the
  original message

## 4. Page layout — `/knowledge`

```
┌───────────────────────────────────────────────────────────────────┐
│ Knowledge                                                         │
│ <solution>  <collection>   backend: full|lite|minimal   N entries │
│                                                                   │
│ [ Browse ]  [ Search ]                                            │
│ ┌───────────────────────────────────────────────────────────────┐ │
│ │ (browse)                         │ (search)                   │ │
│ │ offset 0 / 50  of N              │ query: [_________] [Go]    │ │
│ │ < Prev    Next >                 │ top_k: [10]                │ │
│ │ ─────────────────────────────    │ ──────────────────────     │ │
│ │ [id] metadata tags …    Delete   │ [score]  text preview      │ │
│ │ text preview (200 chars)         │                            │ │
│ │ ▶ expand                         │                            │ │
│ └───────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ ── Add entry ──                                                   │
│  textarea (full width)                                            │
│  metadata: [key] [value]  [+ add pair]                            │
│  [ Add ]                                                          │
└───────────────────────────────────────────────────────────────────┘
```

When `backend = minimal`, the search tab shows a banner: "Semantic
search is unavailable — ChromaDB is not installed. Only exact-match
browse is available."

When the vector store is unwired (no solution, or import failed),
every tab shows a single disabled state with the error message from
`SidecarError`.

## 5. File structure

```
sage-desktop/
├─ sidecar/
│  ├─ handlers/
│  │  └─ knowledge.py          (new — 5 methods + _require_ctx)
│  └─ tests/
│     └─ test_knowledge.py     (new — ~15 tests, fake + real roundtrip)
├─ src-tauri/
│  └─ src/commands/
│     └─ knowledge.rs          (new — 5 proxies)
└─ src/
   ├─ api/
   │  ├─ types.ts              (+ KnowledgeEntry, KnowledgeStats,
   │  │                          KnowledgeListResult,
   │  │                          KnowledgeSearchResult,
   │  │                          KnowledgeSearchHit,
   │  │                          KnowledgeBackend)
   │  └─ client.ts             (+ 5 client functions)
   ├─ hooks/
   │  └─ useKnowledge.ts       (list/search/stats queries +
   │                            add/delete mutations)
   ├─ components/domain/
   │  ├─ KnowledgeEntryRow.tsx    (collapse/expand, metadata tags, delete)
   │  ├─ KnowledgeSearchResults.tsx (ranked list)
   │  └─ AddKnowledgeForm.tsx     (textarea + metadata KV pairs)
   ├─ pages/
   │  └─ Knowledge.tsx         (composes above)
   └─ __tests__/
      ├─ hooks/useKnowledge.test.ts
      ├─ components/KnowledgeEntryRow.test.tsx
      ├─ components/AddKnowledgeForm.test.tsx
      └─ pages/Knowledge.test.tsx
```

## 6. Wire contract (TypeScript)

```typescript
export type KnowledgeBackend = "full" | "lite" | "minimal";

export interface KnowledgeEntry {
  id: string;
  text: string;
  metadata: Record<string, unknown>;
}

export interface KnowledgeListResult {
  entries: KnowledgeEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface KnowledgeSearchHit {
  text: string;
  id?: string;
  score?: number;
  metadata?: Record<string, unknown>;
}

export interface KnowledgeSearchResult {
  query: string;
  results: KnowledgeSearchHit[];
  count: number;
}

export interface KnowledgeStats {
  total: number;
  collection: string;
  backend: KnowledgeBackend;
  solution: string;
}
```

## 7. Testing targets

- Sidecar: +15 unit tests (`handlers/knowledge`) including a real
  `VectorMemory` roundtrip → 173 total.
- Rust: no new tests (proxy-only).
- React: +5 hook tests, +3 `KnowledgeEntryRow`, +2 `AddKnowledgeForm`,
  +2 `Knowledge` page, +1 Sidebar entry → ~150 total.

## 8. Law 1 note

Operator-authored additions and deletions bypass the proposal queue
— consistent with Phase 3b YAML authoring and Phase 5b Constitution.
An *agent* that wants to add or delete a memory still flows through
the existing STATEFUL / DESTRUCTIVE proposal kinds, unchanged.

The sidecar audit logger is *not* wired for this handler by design:
the web UI's approval path already writes to audit, and the desktop
edit is the operator's own action (same trust model as direct file
edits in their solution). Deletions are intentionally destructive —
`delete_entry` removes the row from ChromaDB; the UI must show a
confirmation prompt before sending.

## 9. Acceptance criteria

- `/knowledge` page loads the current solution's entries; header shows
  total count, collection name, backend mode.
- Browse tab paginates through entries 50 at a time with < Prev /
  Next > buttons.
- Search tab returns top-k hits for a query; shows a banner when the
  backend is `minimal`.
- Delete button on each row removes the entry after confirmation.
- Add form accepts text + arbitrary metadata key/value pairs; save
  appends to the store and refreshes the browse list.
- When the vector store is unwired, every tab shows a typed error
  from the sidecar.
- All new tests green; no regressions in the 158-sidecar /
  20-Rust / 138-vitest suites.
