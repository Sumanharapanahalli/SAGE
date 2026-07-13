# SAGE Feature Review — `knowledge`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/knowledge.py`  
**Frontend:** `Knowledge.tsx`  
**Review time:** 77s

---

## Verdict
The knowledge browsing feature is barely functional for basic read/write operations but is fundamentally dangerous to run in a regulated production environment due to compliance-breaking audit trails and a highly inefficient pagination bottleneck.

**Works:** partly
**Score:** 4/10

---

## What Actually Works
- **Stats Retrieval:** Calling `knowledge.stats` successfully queries and returns the collection name, active solution, database backend ("full" or "minimal"), and total counts. (Verified by live evidence: `{"total": 14, "collection": "four_in_a_line_knowledge", "backend": "full", "solution": "four_in_a_line"}`).
- **Entry Browsing (Read):** Calling `knowledge.list` fetches serialized records, including UUIDs, text strings, and structured metadata like `trace_id` and `user_id`. (Verified by live evidence returning 5 records).
- **Semantic/Keyword Search:** Calling `knowledge.search` executes queries against vector memory and returns matching objects with their respective scores/metadata. (Verified by query `"test"` returning 2 match hits).

---

## System-Level Findings

### 1. Critical Audit Trail & Compliance Bypass (High Severity)
*SAGE's core mandate is "Agents propose, humans decide."* The knowledge module bypasses the proposal queue entirely for manual operator `add` and `delete` actions. However, the backend handler `knowledge.py` mutates vector memory directly **without generating any persistent, non-repudiable system audit log events**. 
Because this vector memory holds critical audit trails of rejected actions (e.g., `"[user:operator] Rejected test_action: nope"`), an operator can silently delete rejection logs to cover up mistakes. This completely invalidates the integrity of SAGE as a regulatory compliance record.

### 2. Catastrophic Pagination Bottleneck (High Severity)
In `knowledge.py` (`list_entries`):
```python
raw = vm.list_entries(limit=offset + limit)
...
entries = [ ... for r in raw[offset : offset + limit] ]
```
To show page 200 (e.g., offset 10,000, limit 50), the system pulls **10,050 records from ChromaDB into Python memory**, processes them, and slices them locally. Under normal operational scaling, this will cause extreme latency spikes, high memory overhead, and eventually crash the sidecar process.

### 3. Deceptive Database Error Swallowing (Medium Severity)
In `_total(vm)` and `_collection_name(vm)`, wide-open `except Exception:` blocks swallow all database connection errors, returning fallback values like `0` or `"unknown"`. If ChromaDB crashes, `knowledge.stats` will return `total: 0` instead of throwing an error. This tricks the operator into believing the database is empty (unseeded) rather than broken.

### 4. Leakage Risks via Module-Level Globals (Medium Severity)
The globals `_vm` and `_solution_name` are shared across the module. If SAGE switches solution contexts or operates in a multi-tenant environment, concurrent requests are highly susceptible to race conditions and state leakage.

---

## Usability Findings

### 1. Cryptic Error Masking in UI
In `Knowledge.tsx`, the `errorMessage` function only inspects three explicit error kinds:
```typescript
if (error.kind === "InvalidParams" || error.kind === "SidecarDown" || error.kind === "SolutionUnavailable")
```
When `_require_vm()` or query execution raises a standard `RpcError(RPC_SIDECAR_ERROR)`, it fails the conditional block and returns a generic, useless fallback string: `"Failed (SidecarError)."`. This hides critical connection/DB issues from operators attempting to diagnose errors.

### 2. No Search State Feedback
In the search tab, if an operator submits a query that returns zero results, the UI lacks explicit feedback indicating "No matching results found for '[query]'". Combined with "minimal" backend constraints, operators are left guessing if the search failed, if ChromaDB is missing, or if the search actually completed.

### 3. Destructive Deletion Layout
The list entries feature deletion rows, but they lack a "Confirm Delete" modal or double-action state. An operator misclicking a trash icon will instantly and permanently purge a compliance record from vector memory.

---

## Top 3 Fixes (optimizer-ready)

### 1. Implement Immutable Audit Logging for Direct Mutations
- **Task:** Update the `add` and `delete` RPC handlers in `knowledge.py` to trigger a call to SAGE's central compliance/logger module prior to executing any direct vector database modification.
- **Acceptance Criteria:** Verify that invoking `knowledge.delete` writes an immutable record to the system-wide audit trail detailing the deleted entry's ID, its original text, and the active operator's credential.

### 2. Fix Database-Side Slicing in `list_entries`
- **Task:** Refactor `list_entries` in `knowledge.py` to pass both `limit` and `offset` constraints directly into the underlying `vm.list_entries` query, removing the `offset + limit` memory-slice bypass.
- **Acceptance Criteria:** Verify that database query logs confirm ChromaDB is only asked to fetch and return the explicit page size block (e.g., exactly 50 records) rather than retrieving all preceding rows.

### 3. Handle Detailed Sidecar Errors in Frontend Banner
- **Task:** Modify `errorMessage` in `Knowledge.tsx` to explicitly parse `SidecarError` and extract the inner detail payload.
- **Acceptance Criteria:** Simulate a vector store connection timeout and verify the red UI alert banner displays the actual database driver exception string instead of `"Failed (SidecarError)."`.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    knowledge.stats
  -> {"total": 14, "collection": "four_in_a_line_knowledge", "backend": "full", "solution": "four_in_a_line"}

[LIVE OK]    knowledge.list
  -> {"entries": [{"id": "5b715fd4-c293-4af7-8d22-923093828554", "text": "[user:operator] Rejected test_action: nope", "metadata": {"type": "long_term", "action_type": "test_action", "user_id": "operator", "trace_id": "54f32b28-551e-431a-92db-d70a7e60b89d"}}, {"id": "c9ff026c-1f45-4b4c-9ea2-aced40b74d8d", "text": "[user:Dana Scully] Rejected yaml_edit: wrong module", "metadata": {"type": "long_term", "trace_id": "118e5296-8f39-4b15-b0fe-51827d89d2ec", "user_id": "Dana Scully", "action_type": "yaml_edit"}}, {"id": "4a794d5e-1423-402f-bec0-190214f955b1", "text": "[user:operator] Rejected test_action: nope", "metadata": {"trace_id": "2846faad-287b-43f1-81d0-30b14a8521cf", "user_id": "operator", "type": "long_term", "action_type": "test_action"}}, {"id": "8914a8d5-2822-485d-845a-91335e653683", "text": "[user:Dana Scully] Rejected yaml_edit: wrong module", "metadata": {"action_type": "yaml_edit", "user_id": "Dana Scully", "trace_id": "809f652b-af35-469f-a840-575e210488d8", "type": "long_term"}}, {"id": "9784a6b5-0f46-40af-a12e-7432c7797f51", "text": "[user:operator] Rejected test_action: nope", "metadata": {"trace_id": "c5d062db-cc9d-4f84-8d04-6ead30a2e2d4", "type": "long_term", "user_id": "operator", "action_type": "test_action"}}], "total": 14, "limit": 5, "offset": 0}

[LIVE OK]    knowledge.search
  -> {"query": "test", "results": [{"text": "[user:operator] Rejected test_action: nope"}, {"text": "[user:operator] Rejected test_action: nope"}], "count": 2}
```
