# Contextual Chat Window — Design Spec

**Date:** 2026-03-20
**Status:** Backlog — ready for implementation

---

## Goal

Add a persistent, collapsible chat panel at the bottom-centre of the SAGE UI that lets the user have a direct conversation with the LLM about whatever is currently on screen — a pending proposal, a YAML diff, a firmware fault analysis, or a general question about the framework.

Context is per-user and per-session (not shared between users). The chat history can optionally be scoped to the active solution.

---

## User Stories

1. **Reviewing a proposal**: User sees an agent-proposed YAML edit. Instead of approve/reject, they want to ask "What happens if I change this threshold from 2.2 to 2.0?" — they type it in the chat and the LLM responds in context.
2. **Understanding an analysis**: Analyst returns a RED severity result. User asks "Can you explain what PRECISERR means in ARM Cortex-M terms?"
3. **Framework help**: User asks "How do I add a new module to my solution?" and the LLM answers using SAGE-specific knowledge.
4. **YAML editing**: User says "Change the analyst prompt to also check for HIPAA violations" — the LLM suggests the edit and offers to create a proposal for it.

---

## Architecture

### Backend

**New endpoint:** `POST /chat`

```python
# Request
{
  "message":      "string — user message",
  "user_id":      "string — from auth context",
  "session_id":   "string — UUID per browser session",
  "page_context": "string — current route + any focused proposal/analysis JSON (optional)",
  "solution":     "string — active solution name"
}

# Response (streaming SSE or JSON)
{
  "reply":       "string — LLM response",
  "session_id":  "string",
  "message_id":  "string"
}
```

**Chat history storage:** `SQLite` table `chat_messages` in the solution's `.sage/audit_log.db`

```sql
CREATE TABLE chat_messages (
  id         TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL,
  session_id TEXT NOT NULL,
  solution   TEXT NOT NULL,
  role       TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
  content    TEXT NOT NULL,
  page_context TEXT,
  created_at TEXT NOT NULL
);
```

**Context injection:** The system prompt for chat includes:
- Active solution name, domain, and compliance standards (from project_config)
- Active page route (passed from frontend)
- Last 10 messages from this user's session (rolling window)
- If a proposal/analysis JSON is focused, inject it as context

**Streaming:** `POST /chat/stream` returns SSE tokens for responsive feel.

---

### Frontend

**Component:** `web/src/components/ui/ChatPanel.tsx`

**Position:** Fixed, bottom-centre of viewport. Does NOT overlap the sidebar or header.

```
Layout:
┌────────────────────────────────────────────┐
│ [Collapse ▼]  SAGE Chat  [Clear] [x Close] │
├────────────────────────────────────────────┤
│                                            │
│  assistant: What would you like to know    │
│             about this analysis?           │
│                                            │
│  user:     What does PRECISERR mean?       │
│                                            │
│  assistant: PRECISERR is an ARM Cortex-M   │
│             Bus Fault...                   │
│                                            │
├────────────────────────────────────────────┤
│  [ Type a message...              ] [Send] │
└────────────────────────────────────────────┘
```

**Size:** 520px wide, 380px tall when expanded. Collapses to a 44px tab at the bottom with unread count badge.

**Trigger:**
- Chat icon in the header bar (next to the avatar button)
- Keyboard shortcut: `Ctrl+J`

**Context awareness:**
- On the Analyst page: if an analysis result is shown, the chat automatically has that JSON in context
- On the Approvals page: if a proposal card is focused/expanded, that proposal is in context
- On the YAML editor: current file content is in context
- Otherwise: general SAGE framework context

**User scoping:**
- Chat history stored by `userId` (from `useAuth().user.sub`)
- History is NOT shared between users
- History IS shared across routes within the same solution (so conversation carries over when navigating)
- Option to scope history to solution (clear chat when switching solutions) — default: ON

---

## UI Design Details

**Panel states:**
- `closed` — invisible, only the trigger icon is visible in header
- `minimised` — 44px tall tab at bottom with "SAGE Chat" label and unread badge
- `expanded` — full 380px panel

**Styling:** Matches SAGE dark theme. Uses `--sage-sidebar-bg` for the panel header, `--sage-content-bg` for the message area.

**Message bubbles:**
- User messages: right-aligned, accent background
- Assistant messages: left-aligned, card background with a small SAGE logo

**Streaming:** Assistant messages stream token-by-token (same as LLM output) with a blinking cursor.

**Clear history button:** Clears `chat_messages` for the current user + solution from SQLite.

---

## Context Injection Spec

The LLM system prompt for chat is assembled as:

```
You are SAGE's embedded assistant for the {solution_name} solution.
Domain: {domain}
Active page: {page_route}

{if proposal_context:}
The user is currently viewing this proposal:
{proposal_json}

{if analysis_context:}
The user is currently viewing this analysis result:
{analysis_json}

Answer concisely. If asked to make a change to a YAML file or proposal, describe
the change and offer to create a SAGE proposal for it (but do NOT execute it).
Always keep patient safety and compliance implications in mind for regulated solutions.
```

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `web/src/components/ui/ChatPanel.tsx` | Create — panel UI component |
| `web/src/hooks/useChat.ts` | Create — chat state, send/stream, history |
| `web/src/context/ChatContext.tsx` | Create — provides chat state app-wide |
| `web/src/App.tsx` | Modify — add ChatProvider + ChatPanel at root |
| `web/src/components/layout/Header.tsx` | Modify — add chat icon trigger button |
| `web/src/api/client.ts` | Modify — add postChat(), streamChat() |
| `src/interface/api.py` | Modify — add POST /chat and POST /chat/stream |
| `src/memory/audit_logger.py` | Modify — add chat_messages table schema |

---

## Out of Scope

- Multi-user shared chat / team channels (future)
- Persistent cross-device history sync (future — currently localStorage + SQLite)
- File uploads / image sharing in chat (future)
- The chat does NOT create proposals autonomously — it only suggests them
