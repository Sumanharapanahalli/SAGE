# Action-Aware Chat — Design Spec

**Date:** 2026-03-20
**Status:** Ready for implementation
**Builds on:** `docs/superpowers/specs/2026-03-20-contextual-chat-window.md`

---

## Goal

Upgrade the existing ChatPanel from a pure Q&A interface into an action-routing intelligent assistant that can guide users through reviewing proposals, queuing tasks, and querying knowledge — always with a confirm-before-execute gate and full audit traceability.

---

## User Stories

1. User sees a pending proposal and types "approve it" — chat identifies the proposal from page context, says "I'll approve the YAML edit for analyst.py — proceed?", user clicks Confirm, proposal is approved.
2. User types "queue a firmware review for MR !42" — chat creates a REVIEW_MR task after confirmation.
3. User asks "what does PRECISERR mean?" — chat answers inline with no confirmation card (pure answer).
4. User says "change the analyst prompt to check HIPAA" — chat creates a `yaml_edit` proposal through the normal HITL flow (not executed directly), with a confirmation card explaining what will be created.
5. Every interaction — question, proposed action, confirmation, cancellation, execution result — is permanently recorded in the audit trail.

---

## Architecture

### Intent Classification

The `/chat` endpoint sends the user message to the LLM with a structured system prompt that declares available actions and their parameters. The LLM responds with either:

```json
{ "type": "answer", "reply": "..." }
```
or:
```json
{
  "type": "action",
  "action": "approve_proposal",
  "params": { "trace_id": "abc123" },
  "confirmation_prompt": "I'll approve the YAML edit proposal for analyst.py threshold — proceed?"
}
```

### `src/core/chat_router.py` (new)

Single responsibility: build the routing system prompt, call the LLM, parse and validate the structured response. Returns a `ChatRouterResponse` dataclass. Does not execute anything.

Available action types:

| Action | Parameters | Executes via |
|---|---|---|
| `approve_proposal` | `trace_id` | existing approve logic |
| `reject_proposal` | `trace_id`, `reason` | existing reject logic |
| `undo_proposal` | `trace_id` | `/proposals/{id}/undo` |
| `submit_task` | `task_type`, `payload` | task queue |
| `query_knowledge` | `query` | vector store (read — returns inline, no card) |
| `propose_yaml_edit` | `file`, `change_description` | creates `yaml_edit` proposal via HITL |
| `answer` | — | LLM reply rendered as message bubble |

### `/chat` endpoint (enhanced)

Same request shape. Response gains a `response_type` field:
- `"answer"` — existing behaviour, `reply` field populated
- `"action"` — `action`, `params`, `confirmation_prompt` fields populated

`query_knowledge` is handled server-side within `/chat` (vector store searched, result injected into LLM reply). No confirmation card needed.

### `POST /chat/execute` (new endpoint)

```json
// Request
{ "action": "approve_proposal", "params": { "trace_id": "abc123" },
  "user_id": "...", "session_id": "...", "solution": "..." }

// Response
{ "status": "success"|"error", "message": "Proposal abc123 approved.", "result": {} }
```

Routes the confirmed action to the correct existing API logic. Writes to `compliance_audit_log` with `actor="human_via_chat"`.

---

## Traceability Model

`chat_messages` table gains two new columns (added via migration, no data loss):
- `message_type TEXT` — one of: `user`, `answer`, `action_proposed`, `action_confirmed`, `action_cancelled`, `action_executed`
- `metadata TEXT` — JSON blob: action name, params, linked `trace_id` or `task_id`

`compliance_audit_log` receives an entry for every `chat/execute` call:
- `actor = "human_via_chat"`
- `action_type = "CHAT_EXECUTE_APPROVE_PROPOSAL"` etc.
- `metadata` includes `session_id`, `user_id`, linked `trace_id`

`DELETE /chat/history` clears `chat_messages` (display history) but never touches `compliance_audit_log` (immutable).

---

## Frontend Changes

### `ChatContext.tsx`

Adds `PendingAction` interface and `pendingAction` / `setPendingAction` state. A pending action blocks new messages from being sent (input is disabled until confirmed or cancelled).

### `useChat.ts`

- Builds rich `page_context` JSON from React Query cache: on `/approvals` injects up to 5 pending proposal summaries; on `/queue` injects pending task summaries; always includes active solution + domain.
- Handles structured `/chat` response: if `response_type === "action"` and action is not `query_knowledge`, sets `pendingAction` state instead of inserting an assistant bubble.
- `confirmAction()` — calls `POST /chat/execute`, clears `pendingAction`, inserts system message with result.
- `cancelAction()` — clears `pendingAction`, inserts "Cancelled." system message, logs to backend.

### `ChatPanel.tsx`

New render paths alongside existing message bubbles:

**Confirmation card** (rendered when `pendingAction !== null`):
- Amber left border, dark background
- Action type badge (e.g. `approve_proposal` in small pill)
- `confirmation_prompt` text
- `[Confirm]` (green) and `[Cancel]` (muted) buttons
- Replaces the input area while pending — user cannot type until resolved

**System message** (slim, muted, centred):
- Used for execution results ("Proposal approved."), cancellations, and errors
- Visually distinct from user/assistant bubbles

All colors use existing CSS vars (`--sage-sidebar-bg`, `--sage-user-accent`) — color combos apply automatically.

---

## Files Changed

| File | Change |
|---|---|
| `src/core/chat_router.py` | NEW — intent classification + response parsing |
| `src/memory/audit_logger.py` | Add `message_type` + `metadata` columns + migration |
| `src/interface/api.py` | Enhance `/chat`, add `/chat/execute` + `ChatExecuteRequest` |
| `web/src/api/client.ts` | Add `executeChat()` + `ChatExecuteRequest` type |
| `web/src/context/ChatContext.tsx` | Add `PendingAction` type + state |
| `web/src/hooks/useChat.ts` | Rich page context, action routing, confirm/cancel |
| `web/src/components/ui/ChatPanel.tsx` | Confirmation card + system message render modes |
| `tests/test_chat_router.py` | NEW — unit tests for router |
| `tests/test_chat_execute_endpoint.py` | NEW — endpoint tests for each action type |
