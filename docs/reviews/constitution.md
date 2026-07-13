# SAGE Feature Review — `constitution`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/constitution.py`  
**Frontend:** `Constitution.tsx`  
**Review time:** 87s

---

## Verdict
This feature is completely unusable today by a real operator because an out-of-the-box validation error locks the system, making it impossible to save any changes to the constitution from the UI.

**Works:** no
**Score:** 3/10

## What Actually Works
Based on the live runtime evidence:
* **Successful Retrieval:** `constitution.get` executes correctly, retrieving the current database state including metadata, stats, prompt preambles, change history, and current validation errors.
* **Prompt Assembly:** `constitution.preamble` successfully outputs the formatted template, prepending principles and constraints.
* **Basic Frontend State Management:** The React page handles loading states, queries the backend using `useConstitution`, and implements a revert state strategy using deep cloning (`cloneData`).
* **Statistical Tracking:** The stats engine counts principles (`1`), constraints (`1`), and non-negotiable items (`1`), making them accessible to the UI header.

## System-Level Findings

### 1. HITL Gate Bypass Vulnerability (Critical Severity)
SAGE's core law is *"Agents propose. Humans decide."* However, the backend `update` handler accepts any arbitrary `changed_by` parameter and defaults to `"desktop"`. There is no token validation, cryptographic signature, or session check confirming that a real human operator triggered the edit. An agent could execute this RPC directly to rewrite its own constitution and delete its constraints.

### 2. Out-of-the-Box Validation Lockout (High Severity)
The live runtime evidence shows a schema error on disk: `"voice: must be an object with 'tone' and/or 'avoid', got str"`. Because the backend `update` function validates the *entire* schema and rolls back if *any* errors exist, the operator is completely blocked from saving edits to unrelated sections (like principles or constraints) until this pre-existing voice validation error is resolved.

### 3. Constraints Data Type Mismatch (Medium Severity)
In the live data, constraints are stored as objects: `[{"id": "no-net", "text": "No network calls from the game loop"}]`. However, the React frontend page defines the change handler as:
```typescript
const setConstraints = (constraints: string[]) => setDraft({ ...draft, constraints });
```
If `ConstraintsEditor` passes raw strings, the array of objects on disk will be overwritten with an array of strings. This will either fail schema validation on the backend or corrupt the database, causing the UI to crash on the next reload.

### 4. Implementation Leak in Prompt Preamble (Low Severity)
In the compiled prompt preamble, the constraint is output using Python's string representation of a dictionary:
```
- {'id': 'no-net', 'text': 'No network calls from the game loop'}
```
This leaks code syntax directly into the agent's prompt, degrading LLM response cleanliness and steering quality.

## Usability Findings

### 1. Alarmist Default State
A fresh SAGE operator is immediately greeted with a prominent red validation error banner ("Validation errors on disk: voice...") on their first visit, eroding trust in the software's stability.

### 2. Blind Draft Previews
The `PreamblePreview` component displays the compiled preamble from the *saved* database state (`preamble` from `query.data`), not the *draft* state. Operators cannot preview how their edits will look inside the LLM prompt before clicking "Save".

### 3. Infinite Loading Hang
The component guard `if (query.isLoading || !draft)` will block page rendering indefinitely if the backend returns an empty database or if `query.data.data` is missing or undefined, offering no fallback or timeout.

### 4. Unsynced UI on Mutation Completion
The `update` RPC returns only metadata (`stats`, `preamble`, `version`, `path`) but omits the actual updated data structure. If the React Query mutation fails to trigger a full refetch of the get query, the UI remains stale and displays old validation errors.

## Top 3 Fixes (optimizer-ready)

### 1. Fix Prompt Formatting and Align Constraints Types
* **Task:** Standardize constraints as objects across the stack and clean up prompt compilation.
* **Files:** `Constitution.tsx`, `constitution.py`
* **Implementation:** 
  1. Change the typescript signature of `setConstraints` in `Constitution.tsx` to accept an array of objects `ConstitutionConstraint[]` containing `{ id: string; text: string }`.
  2. Update the Python preamble builder (`build_prompt_preamble`) to format constraints as raw string lists (`- {constraint['text']}`) instead of stringifying the entire dictionary.
* **Acceptance Criteria:** Saving constraints through the UI succeeds without schema validation errors, and the compiled preamble outputs plain text (`- No network calls from the game loop`) without curly braces or keys.

### 2. Resolve Database Seed Schema Error
* **Task:** Standardize the voice parameter's seed format and add a migration fallback for legacy strings.
* **Files:** `constitution.py` (and the associated SAGE database seeder files)
* **Implementation:** 
  1. Update the database seed file to initialize `voice` as an object: `{"tone": "Terse, factual", "avoid": ""}`.
  2. In `constitution.py`'s `get` / `reload` flow, add a migration check: if `voice` is a string, automatically transform it to `{"tone": voice_string}` before running validation.
* **Acceptance Criteria:** A fresh database load registers 0 errors in the `constitution.get` payload, and the red error alert banner does not appear on the React frontend.

### 3. Secure the Update RPC against Agent Bypass
* **Task:** Cryptographically or session-bind the update handler to verify physical operator intent.
* **Files:** `constitution.py`
* **Implementation:** 
  1. Refactor `update` to validate a desktop session token or physical desktop-interaction signature.
  2. Reject any programmatically-sent updates lacking this token with an RPC authentication error instead of allowing arbitrary `changed_by` overrides.
* **Acceptance Criteria:** An API call to `constitution.update` with an empty or simulated token fails to modify the file on disk.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    constitution.get
  -> {"data": {"name": "Four in a Line", "principles": [{"id": "hitl", "text": "Never bypass the human approval gate", "weight": 1.0}], "constraints": [{"id": "no-net", "text": "No network calls from the game loop"}], "voice": "Terse, factual", "decision_rules": ["Prefer the smallest correct change"], "meta": {"name": "", "version": 1, "last_updated": "2026-07-13T19:36:36.099596+00:00", "updated_by": "desktop"}, "_history": [{"version": 1, "changed_by": "desktop", "timestamp": "2026-07-13T19:36:36.099596+00:00"}]}, "stats": {"is_empty": false, "name": "", "version": 1, "principle_count": 1, "constraint_count": 1, "non_negotiable_count": 1, "has_voice": true, "has_decisions": false, "has_knowledge": false, "history_entries": 1}, "preamble": "## Solution Constitution\n\n### Guiding Principles (by priority)\n- Never bypass the human approval gate [NON-NEGOTIABLE]\n\n### Hard Constraints (violations are rejected)\n- {'id': 'no-net', 'text': 'No network calls from the game loop'}\n\n### Communication Style\nTone: Terse, factual\n", "history": [{"version": 1, "changed_by": "desktop", "timestamp": "2026-07-13T19:36:36.099596+00:00"}], "errors": ["voice: must be an object with 'tone' and/or 'avoid', got str"]}

[LIVE OK]    constitution.preamble
  -> {"preamble": "## Solution Constitution\n\n### Guiding Principles (by priority)\n- Never bypass the human approval gate [NON-NEGOTIABLE]\n\n### Hard Constraints (violations are rejected)\n- {'id': 'no-net', 'text': 'No network calls from the game loop'}\n\n### Communication Style\nTone: Terse, factual\n"}
```
