# Action-Aware Chat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the existing ChatPanel from Q&A-only into an action-routing assistant — classify user intent via LLM, present confirmation cards for actions, execute on confirm, record everything in the audit trail.

**Architecture:** New `chat_router.py` handles LLM-as-router (builds prompt, parses structured JSON response). `/chat` endpoint enhanced to use router. New `/chat/execute` endpoint dispatches confirmed actions. Frontend gains confirmation card UI + rich page context injection.

**Tech Stack:** Python 3.11, FastAPI, SQLite, React 18 + TypeScript, existing LLMGateway, existing ProposalStore + TaskQueue

**Spec:** `docs/superpowers/specs/2026-03-20-action-aware-chat-design.md`

---

## File Structure

### New files
- `src/core/chat_router.py` — LLM routing: system prompt builder + response parser
- `tests/test_chat_router.py` — unit tests for routing logic
- `tests/test_chat_execute_endpoint.py` — endpoint tests for execute actions

### Modified files
- `src/memory/audit_logger.py` — add `message_type` + `metadata` cols + migration
- `src/interface/api.py` — enhance `/chat` response shape, add `/chat/execute` + `ChatExecuteRequest`
- `web/src/api/client.ts` — add `executeChat()` + types
- `web/src/context/ChatContext.tsx` — add `PendingAction` type + state
- `web/src/hooks/useChat.ts` — rich page context, handle action response, confirm/cancel
- `web/src/components/ui/ChatPanel.tsx` — confirmation card + system message render modes

---

## Task 1: `src/core/chat_router.py` — LLM-as-router

**Context:** `llm_gateway.generate()` in `src/core/llm_gateway.py` takes `(prompt, system_prompt)`. We build a system prompt that describes available actions and instructs the LLM to return pure JSON. We parse the response into a `ChatRouterResponse` dataclass.

**Files:**
- Create: `tests/test_chat_router.py`
- Create: `src/core/chat_router.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_chat_router.py
import pytest
from unittest.mock import patch, MagicMock


def test_parse_answer_response():
    """parse_router_response extracts answer type correctly."""
    from src.core.chat_router import parse_router_response
    raw = '{"type": "answer", "reply": "Proposals are HITL-gated actions."}'
    result = parse_router_response(raw)
    assert result["type"] == "answer"
    assert "Proposals" in result["reply"]


def test_parse_action_response():
    """parse_router_response extracts action type with params."""
    from src.core.chat_router import parse_router_response
    raw = '{"type": "action", "action": "approve_proposal", "params": {"trace_id": "abc"}, "confirmation_prompt": "Approve?"}'
    result = parse_router_response(raw)
    assert result["type"] == "action"
    assert result["action"] == "approve_proposal"
    assert result["params"]["trace_id"] == "abc"
    assert result["confirmation_prompt"] == "Approve?"


def test_parse_malformed_falls_back_to_answer():
    """If LLM returns non-JSON, treat as plain answer."""
    from src.core.chat_router import parse_router_response
    raw = "Sure, here is the explanation."
    result = parse_router_response(raw)
    assert result["type"] == "answer"
    assert result["reply"] == raw


def test_build_router_system_prompt_includes_actions():
    """System prompt contains all action names."""
    from src.core.chat_router import build_router_system_prompt
    prompt = build_router_system_prompt(solution="test", domain="testing", page_context="")
    for action in ["approve_proposal", "reject_proposal", "undo_proposal",
                   "submit_task", "query_knowledge", "propose_yaml_edit"]:
        assert action in prompt


def test_route_calls_llm_and_returns_parsed():
    """route() calls llm_gateway.generate and returns parsed dict."""
    from src.core.chat_router import route
    mock_gw = MagicMock()
    mock_gw.generate.return_value = '{"type": "answer", "reply": "Hello"}'
    with patch("src.core.chat_router.llm_gateway", mock_gw):
        result = route("Hello", solution="test", domain="", page_context="")
    assert result["type"] == "answer"
    assert mock_gw.generate.called
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/sandbox/SAGE && .venv/Scripts/pytest tests/test_chat_router.py -v
```
Expected: FAIL — `ModuleNotFoundError: src.core.chat_router`

- [ ] **Step 3: Create `src/core/chat_router.py`**

```python
"""
chat_router.py — LLM-as-router for action-aware chat.

Builds a structured system prompt that instructs the LLM to classify the
user's message as either a plain answer or an actionable intent, then parses
the LLM's JSON response into a dict consumed by the /chat endpoint.
"""
import json
import logging

logger = logging.getLogger(__name__)

AVAILABLE_ACTIONS = """
Available actions (use ONLY these action names):

- approve_proposal: Approve a pending HITL proposal.
  params: {"trace_id": "<string>"}

- reject_proposal: Reject a pending HITL proposal with a reason.
  params: {"trace_id": "<string>", "reason": "<string>"}

- undo_proposal: Revert an already-approved proposal.
  params: {"trace_id": "<string>"}

- submit_task: Queue a new agent task.
  params: {"task_type": "<ANALYZE_LOG|REVIEW_MR|CREATE_MR|FLASH_FIRMWARE>", "payload": {}}

- query_knowledge: Search the solution knowledge base. Returns result inline.
  params: {"query": "<string>"}

- propose_yaml_edit: Create a yaml_edit HITL proposal (does NOT apply immediately).
  params: {"file": "<prompts|project|tasks>", "change_description": "<string>"}
"""


def build_router_system_prompt(solution: str, domain: str, page_context: str) -> str:
    return f"""You are SAGE's embedded action-aware assistant for the '{solution}' solution (domain: {domain or 'general'}).

Current page context:
{page_context or 'No page context provided.'}

Your job is to classify the user's message and respond with PURE JSON — no markdown, no code fences, no explanation outside the JSON.

{AVAILABLE_ACTIONS}

Response format:

If the message is a question or explanation request:
{{"type": "answer", "reply": "<your response>"}}

If the message maps to one of the available actions:
{{"type": "action", "action": "<action_name>", "params": {{...}}, "confirmation_prompt": "<one sentence describing exactly what will happen, referencing specific IDs if available>"}}

Rules:
- ONLY return one of these two JSON shapes. Nothing else.
- For actions, ALWAYS include a confirmation_prompt that the human will read before approving.
- If the page context includes proposal or task IDs, reference the specific ID in the confirmation_prompt.
- If you cannot determine the required params (e.g. trace_id not in context), return an answer asking the user to clarify.
- For query_knowledge, always use type "action" so it is logged, but no confirmation card will be shown.
"""


def parse_router_response(raw: str) -> dict:
    """Parse LLM raw text into a typed router response dict.

    Falls back to {"type": "answer", "reply": raw} if JSON is malformed.
    """
    raw = raw.strip()
    # Strip markdown code fences if LLM wraps in ```json ... ```
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        parsed = json.loads(raw)
        if parsed.get("type") in ("answer", "action"):
            return parsed
        # Unexpected shape — treat as answer
        return {"type": "answer", "reply": raw}
    except (json.JSONDecodeError, AttributeError):
        return {"type": "answer", "reply": raw}


def route(
    message: str,
    solution: str,
    domain: str,
    page_context: str,
    history_text: str = "",
) -> dict:
    """Send message through the LLM router and return a parsed response dict."""
    from src.core.llm_gateway import llm_gateway

    system_prompt = build_router_system_prompt(solution, domain, page_context)
    prompt = f"{history_text}User: {message}\nAssistant:"
    try:
        raw = llm_gateway.generate(prompt, system_prompt=system_prompt)
        return parse_router_response(raw)
    except Exception as exc:
        logger.error("chat_router LLM error: %s", exc)
        return {"type": "answer", "reply": f"Sorry, I could not reach the LLM: {exc}"}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/sandbox/SAGE && .venv/Scripts/pytest tests/test_chat_router.py -v
```
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/core/chat_router.py tests/test_chat_router.py
git commit -m "feat(chat): chat_router — LLM-as-router with structured JSON response"
```

---

## Task 2: Audit logger — add `message_type` and `metadata` columns

**Context:** `src/memory/audit_logger.py` line ~92 creates `chat_messages`. We add two columns via `ALTER TABLE` migration (safe on existing DBs) and update `save_chat_message` to accept them.

**Files:**
- Modify: `src/memory/audit_logger.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_audit_logger.py (or create new file tests/test_chat_audit.py)

def test_chat_message_type_and_metadata_columns():
    """save_chat_message accepts message_type and metadata without error."""
    import tempfile, os
    from src.memory.audit_logger import AuditLogger
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        al = AuditLogger(db_path=db_path)
        msg_id = al.save_chat_message(
            user_id="u1", session_id="s1", solution="test",
            role="assistant", content="Hello",
            message_type="action_proposed",
            metadata={"action": "approve_proposal", "trace_id": "abc"},
        )
        assert msg_id is not None
        # Verify columns exist by reading back
        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT message_type, metadata FROM chat_messages WHERE id=?", (msg_id,)
        ).fetchone()
        conn.close()
        assert row[0] == "action_proposed"
        assert "approve_proposal" in row[1]
    finally:
        os.unlink(db_path)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/sandbox/SAGE && .venv/Scripts/pytest tests/test_audit_logger.py::test_chat_message_type_and_metadata_columns -v 2>/dev/null || .venv/Scripts/pytest tests/test_chat_audit.py -v
```
Expected: FAIL — `TypeError: save_chat_message() got unexpected keyword argument 'message_type'`

- [ ] **Step 3: Add migration + update `save_chat_message`**

In `src/memory/audit_logger.py`, inside `__init__` after the existing `ALTER TABLE` try/except blocks (around line 85), add:

```python
        # chat_messages — add message_type and metadata columns (migration)
        for col_def in [
            "ALTER TABLE chat_messages ADD COLUMN message_type TEXT DEFAULT 'user'",
            "ALTER TABLE chat_messages ADD COLUMN metadata TEXT",
        ]:
            try:
                cursor.execute(col_def)
            except Exception:
                pass  # column already exists
```

Update `save_chat_message` signature (around line 107):

```python
    def save_chat_message(
        self,
        user_id: str,
        session_id: str,
        solution: str,
        role: str,
        content: str,
        page_context: str = None,
        message_type: str = "user",
        metadata: dict = None,
    ) -> str:
        """Persist a chat message with type and optional action metadata."""
        import json as _json
        msg_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        meta_str = _json.dumps(metadata) if metadata else None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """INSERT INTO chat_messages
                   (id, user_id, session_id, solution, role, content,
                    page_context, created_at, message_type, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (msg_id, user_id, session_id, solution, role, content,
                 page_context, created_at, message_type, meta_str),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            self.logger.error("Failed to save chat message: %s", exc)
        return msg_id
```

- [ ] **Step 4: Run tests**

```bash
cd C:/sandbox/SAGE && .venv/Scripts/pytest tests/ -x -q
```
Expected: all existing tests still pass + new test passes

- [ ] **Step 5: Commit**

```bash
git add src/memory/audit_logger.py
git commit -m "feat(chat): add message_type + metadata columns to chat_messages"
```

---

## Task 3: `api.py` — enhance `/chat` + add `/chat/execute`

**Context:** Current `/chat` returns `{reply, session_id, message_id}`. Enhanced version returns `{response_type, reply?, action?, params?, confirmation_prompt?, session_id, message_id}`. New `POST /chat/execute` endpoint dispatches confirmed actions.

**Files:**
- Create: `tests/test_chat_execute_endpoint.py`
- Modify: `src/interface/api.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_chat_execute_endpoint.py
from fastapi.testclient import TestClient


def test_execute_unknown_action_returns_400():
    from src.interface.api import app
    client = TestClient(app)
    resp = client.post("/chat/execute", json={
        "action": "nonexistent_action", "params": {},
        "user_id": "u1", "session_id": "s1", "solution": "test"
    })
    assert resp.status_code == 400


def test_execute_approve_unknown_trace_returns_404():
    from src.interface.api import app
    client = TestClient(app)
    resp = client.post("/chat/execute", json={
        "action": "approve_proposal",
        "params": {"trace_id": "does-not-exist"},
        "user_id": "u1", "session_id": "s1", "solution": "test"
    })
    assert resp.status_code == 404


def test_execute_endpoint_exists():
    from src.interface.api import app
    routes = [r.path for r in app.routes]
    assert "/chat/execute" in routes


def test_chat_response_has_response_type():
    """Enhanced /chat always returns response_type field."""
    from src.interface.api import app
    from unittest.mock import patch
    client = TestClient(app)
    mock_result = {"type": "answer", "reply": "Hello"}
    with patch("src.core.chat_router.route", return_value=mock_result):
        resp = client.post("/chat", json={"message": "hi", "user_id": "u1"})
    assert resp.status_code == 200
    assert "response_type" in resp.json()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/sandbox/SAGE && .venv/Scripts/pytest tests/test_chat_execute_endpoint.py -v
```
Expected: FAIL — `/chat/execute` route doesn't exist, `/chat` missing `response_type`

- [ ] **Step 3: Add `ChatExecuteRequest` model**

After the `ChatRequest` model (around line 146 in `api.py`), add:

```python
class ChatExecuteRequest(BaseModel):
    action: str
    params: dict = {}
    user_id: str = "anonymous"
    session_id: str = ""
    solution: str = ""
```

- [ ] **Step 4: Enhance `POST /chat` to use chat_router**

Replace the existing `/chat` handler body. Key changes:
1. Call `chat_router.route()` instead of raw `llm_gateway.generate()`
2. Save user message with `message_type="user"`
3. Save assistant response with `message_type="answer"` or `message_type="action_proposed"`
4. Return `response_type` field

Replace the body of `async def chat(req: ChatRequest):` with:

```python
    from src.core.project_loader import project_config
    from src.core.chat_router import route as chat_route
    from src.memory.audit_logger import audit_logger
    import json as _json

    solution = req.solution or (project_config.project_name if project_config else "sage")
    session_id = req.session_id or str(uuid.uuid4())

    domain = ""
    try:
        domain = project_config.domain or ""
    except Exception:
        pass

    # Build rolling history for context
    history = audit_logger.get_chat_history(req.user_id, session_id, solution, limit=10)
    history_text = ""
    for msg in history:
        prefix = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{prefix}: {msg['content']}\n"
    if history_text:
        history_text += "\n"

    # Save user message
    audit_logger.save_chat_message(
        user_id=req.user_id, session_id=session_id, solution=solution,
        role="user", content=req.message, page_context=req.page_context,
        message_type="user",
    )

    # Route through LLM classifier
    result = chat_route(
        message=req.message, solution=solution, domain=domain,
        page_context=req.page_context or "", history_text=history_text,
    )

    response_type = result.get("type", "answer")

    if response_type == "action":
        action_name = result.get("action", "")
        params = result.get("params", {})
        confirmation_prompt = result.get("confirmation_prompt", "")

        # query_knowledge executes server-side immediately (read-only)
        if action_name == "query_knowledge":
            try:
                from src.memory.vector_store import vector_store
                hits = vector_store.search(params.get("query", req.message), n_results=3)
                knowledge_text = "\n".join(h.get("content", "") for h in hits) if hits else "No results found."
                reply = f"From the knowledge base:\n\n{knowledge_text}"
            except Exception as exc:
                reply = f"Knowledge search unavailable: {exc}"
            message_id = audit_logger.save_chat_message(
                user_id=req.user_id, session_id=session_id, solution=solution,
                role="assistant", content=reply, page_context=req.page_context,
                message_type="answer",
            )
            return {"response_type": "answer", "reply": reply, "session_id": session_id, "message_id": message_id}

        # All other actions: return as action_proposed
        message_id = audit_logger.save_chat_message(
            user_id=req.user_id, session_id=session_id, solution=solution,
            role="assistant", content=confirmation_prompt, page_context=req.page_context,
            message_type="action_proposed",
            metadata={"action": action_name, "params": params},
        )
        return {
            "response_type": "action",
            "action": action_name,
            "params": params,
            "confirmation_prompt": confirmation_prompt,
            "session_id": session_id,
            "message_id": message_id,
        }

    # Plain answer
    reply = result.get("reply", "")
    message_id = audit_logger.save_chat_message(
        user_id=req.user_id, session_id=session_id, solution=solution,
        role="assistant", content=reply, page_context=req.page_context,
        message_type="answer",
    )
    return {"response_type": "answer", "reply": reply, "session_id": session_id, "message_id": message_id}
```

- [ ] **Step 5: Add `POST /chat/execute` endpoint**

Add after the `/chat` handler:

```python
@app.post("/chat/execute")
async def chat_execute(req: ChatExecuteRequest):
    """Execute a chat-proposed action after human confirmation."""
    from src.core.project_loader import project_config
    from src.memory.audit_logger import audit_logger

    solution = req.solution or (project_config.project_name if project_config else "sage")
    session_id = req.session_id or str(uuid.uuid4())
    action = req.action
    params = req.params

    SUPPORTED_ACTIONS = {
        "approve_proposal", "reject_proposal", "undo_proposal",
        "submit_task", "propose_yaml_edit",
    }
    if action not in SUPPORTED_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")

    # Log confirmation
    audit_logger.save_chat_message(
        user_id=req.user_id, session_id=session_id, solution=solution,
        role="user", content=f"[Confirmed: {action}]", page_context=None,
        message_type="action_confirmed",
        metadata={"action": action, "params": params},
    )

    result_msg = ""
    result_data = {}

    try:
        if action == "approve_proposal":
            trace_id = params.get("trace_id", "")
            store = _get_proposal_store()
            proposal = store.get(trace_id)
            if proposal is None:
                raise HTTPException(status_code=404, detail=f"Proposal '{trace_id}' not found.")
            executor = _get_proposal_executor()
            import asyncio
            asyncio.ensure_future(executor.execute(proposal))
            store.approve(trace_id)
            result_msg = f"Proposal {trace_id} approved."
            result_data = {"trace_id": trace_id}

        elif action == "reject_proposal":
            trace_id = params.get("trace_id", "")
            reason = params.get("reason", "Rejected via chat.")
            store = _get_proposal_store()
            proposal = store.get(trace_id)
            if proposal is None:
                raise HTTPException(status_code=404, detail=f"Proposal '{trace_id}' not found.")
            store.reject(trace_id, reason)
            result_msg = f"Proposal {trace_id} rejected."
            result_data = {"trace_id": trace_id}

        elif action == "undo_proposal":
            trace_id = params.get("trace_id", "")
            store = _get_proposal_store()
            proposal = store.get(trace_id)
            if proposal is None:
                raise HTTPException(status_code=404, detail=f"Proposal '{trace_id}' not found.")
            if proposal.action_type == "code_diff":
                from src.core.proposal_executor import _revert_code_diff
                import asyncio
                asyncio.ensure_future(_revert_code_diff(proposal))
            result_msg = f"Undo triggered for proposal {trace_id}."
            result_data = {"trace_id": trace_id}

        elif action == "submit_task":
            from src.core.queue_manager import task_queue
            task_type = params.get("task_type", "")
            payload = params.get("payload", {})
            task_id = task_queue.submit(task_type=task_type, payload=payload, source="chat")
            result_msg = f"Task {task_id} ({task_type}) queued."
            result_data = {"task_id": task_id}

        elif action == "propose_yaml_edit":
            file_name = params.get("file", "prompts")
            change_desc = params.get("change_description", "")
            store = _get_proposal_store()
            from src.core.proposal_store import RiskClass
            p = store.create(
                action_type="yaml_edit",
                risk_class=RiskClass.STATEFUL,
                payload={"file": file_name, "change_description": change_desc},
                description=f"YAML edit via chat: {change_desc[:80]}",
                reversible=True,
            )
            result_msg = f"YAML edit proposal created (trace_id: {p.trace_id}). Review it in Approvals."
            result_data = {"trace_id": p.trace_id}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("chat/execute error for action %s: %s", action, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    # Write execution result to chat history
    audit_logger.save_chat_message(
        user_id=req.user_id, session_id=session_id, solution=solution,
        role="assistant", content=result_msg, page_context=None,
        message_type="action_executed",
        metadata={"action": action, **result_data},
    )

    # Write to compliance audit log
    _get_audit_logger().log_event(
        actor="human_via_chat",
        action_type=f"CHAT_EXECUTE_{action.upper()}",
        input_context=f"session={session_id} user={req.user_id}",
        output_content=result_msg,
        metadata={"action": action, "params": params, "session_id": session_id, **result_data},
    )

    return {"status": "success", "message": result_msg, "result": result_data}
```

- [ ] **Step 6: Run tests**

```bash
cd C:/sandbox/SAGE && .venv/Scripts/pytest tests/test_chat_execute_endpoint.py tests/test_chat_router.py -v
```
Expected: all pass

- [ ] **Step 7: Run full suite**

```bash
cd C:/sandbox/SAGE && .venv/Scripts/pytest tests/ -x -q
```
Expected: 480+ passed

- [ ] **Step 8: Commit**

```bash
git add src/interface/api.py tests/test_chat_execute_endpoint.py
git commit -m "feat(chat): enhance /chat with action routing + add /chat/execute endpoint"
```

---

## Task 4: `client.ts` — add `executeChat`

**Files:**
- Modify: `web/src/api/client.ts`

- [ ] **Step 1: Add types and function**

In `web/src/api/client.ts`, after `postChat`, add:

```typescript
export interface ChatExecuteRequest {
  action: string
  params: Record<string, unknown>
  user_id: string
  session_id: string
  solution: string
}

export interface ChatExecuteResponse {
  status: 'success' | 'error'
  message: string
  result: Record<string, unknown>
}

export const executeChat = (req: ChatExecuteRequest) =>
  post<ChatExecuteResponse>('/chat/execute', req)
```

Also update `postChat` return type — the response now includes `response_type`. Find the existing `postChat` function and update its return type:

```typescript
export interface ChatResponse {
  response_type: 'answer' | 'action'
  reply?: string
  action?: string
  params?: Record<string, unknown>
  confirmation_prompt?: string
  session_id: string
  message_id: string
}

export const postChat = (req: {
  message: string; user_id: string; session_id: string
  page_context?: string; solution: string
}) => post<ChatResponse>('/chat', req)
```

- [ ] **Step 2: TypeScript check**

```bash
cd C:/sandbox/SAGE/web && npx tsc --noEmit 2>&1 | grep -v "global"
```
Expected: no new errors

- [ ] **Step 3: Commit**

```bash
git add web/src/api/client.ts
git commit -m "feat(chat): add executeChat API function + ChatResponse types"
```

---

## Task 5: `ChatContext.tsx` — add `PendingAction` state

**Files:**
- Modify: `web/src/context/ChatContext.tsx`

- [ ] **Step 1: Add `PendingAction` interface and state**

At the top of `web/src/context/ChatContext.tsx`, after the `ChatMessage` interface, add:

```typescript
export interface PendingAction {
  action: string
  params: Record<string, unknown>
  confirmation_prompt: string
  message_id: string
}
```

Add to `ChatContextValue` interface:
```typescript
  pendingAction: PendingAction | null
  setPendingAction: (a: PendingAction | null) => void
```

Add state inside `ChatProvider`:
```typescript
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null)
```

Add `pendingAction` and `setPendingAction` to the context value.

Also add a new `ChatMessage` role variant for system messages. Change the role type:
```typescript
  role: 'user' | 'assistant' | 'system'
```

- [ ] **Step 2: TypeScript check**

```bash
cd C:/sandbox/SAGE/web && npx tsc --noEmit 2>&1 | grep -v "global"
```
Expected: no errors (or only existing ones)

- [ ] **Step 3: Commit**

```bash
git add web/src/context/ChatContext.tsx
git commit -m "feat(chat): add PendingAction state + system message role to ChatContext"
```

---

## Task 6: `useChat.ts` — action routing, page context enrichment, confirm/cancel

**Context:** `useChat` currently calls `postChat` and always treats response as a text reply. We now check `response_type`, set `pendingAction` for actions, and build a rich `page_context` JSON string from the React Query cache.

**Files:**
- Modify: `web/src/hooks/useChat.ts`

- [ ] **Step 1: Rewrite `useChat.ts`**

Replace the full file with:

```typescript
import { useEffect, useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../context/AuthContext'
import { useProjectConfig } from './useProjectConfig'
import { useChatContext } from '../context/ChatContext'
import { postChat, executeChat } from '../api/client'

function getSessionId(): string {
  try {
    let id = sessionStorage.getItem('sage_chat_session')
    if (!id) { id = crypto.randomUUID(); sessionStorage.setItem('sage_chat_session', id) }
    return id
  } catch { return 'anon-session' }
}

function buildPageContext(pathname: string, queryClient: ReturnType<typeof useQueryClient>, solution: string): string {
  const ctx: Record<string, unknown> = { route: pathname, solution }
  try {
    if (pathname === '/approvals' || pathname.startsWith('/approvals')) {
      const proposals = queryClient.getQueryData<{ proposals?: unknown[] }>(['proposals'])
      const pending = (proposals?.proposals ?? []).filter((p: any) => p.status === 'pending')
      ctx.pending_proposals = pending.slice(0, 5).map((p: any) => ({
        trace_id: p.trace_id, description: p.description, action_type: p.action_type,
      }))
    }
    if (pathname === '/queue' || pathname.startsWith('/queue')) {
      const tasks = queryClient.getQueryData<unknown[]>(['queue'])
      ctx.pending_tasks = (tasks ?? []).slice(0, 5)
    }
    const projectData = queryClient.getQueryData<any>(['projectConfig'])
    if (projectData) {
      ctx.domain = projectData.domain ?? ''
      ctx.compliance = projectData.compliance_standards ?? []
    }
  } catch { /* cache miss — non-fatal */ }
  return JSON.stringify(ctx)
}

export function useChat() {
  const { pathname } = useLocation()
  const { user } = useAuth()
  const { data: projectData } = useProjectConfig()
  const queryClient = useQueryClient()
  const {
    panelState, messages, isLoading,
    openChat, closeChat, minimiseChat,
    seedMessage, clearSeedMessage,
    addMessage, updateLastAssistantMessage, setMessages, setIsLoading,
    clearUnread, incrementUnread,
    pendingAction, setPendingAction,
  } = useChatContext()

  const userId = (user as any)?.sub ?? 'anonymous'
  const solution = (projectData as any)?.project ?? ''
  const sessionId = getSessionId()

  useEffect(() => {
    if (panelState === 'expanded' && seedMessage) {
      const seed = seedMessage
      clearSeedMessage()
      sendMessage(seed)
    }
  }, [panelState, seedMessage]) // eslint-disable-line react-hooks/exhaustive-deps

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return
    // Auto-cancel any pending action
    if (pendingAction) setPendingAction(null)

    const userMsg = { id: crypto.randomUUID(), role: 'user' as const, content: text }
    addMessage(userMsg)
    setIsLoading(true)
    addMessage({ id: crypto.randomUUID(), role: 'assistant', content: '', streaming: true })

    try {
      const pageContext = buildPageContext(pathname, queryClient, solution)
      const res = await postChat({
        message: text, user_id: userId, session_id: sessionId,
        page_context: pageContext, solution,
      })

      if (res.response_type === 'action' && res.action !== 'query_knowledge') {
        // Remove streaming bubble, show nothing — confirmation card replaces it
        setMessages(prev => prev.filter(m => !m.streaming))
        setPendingAction({
          action: res.action!,
          params: res.params ?? {},
          confirmation_prompt: res.confirmation_prompt ?? '',
          message_id: res.message_id,
        })
      } else {
        // Plain answer
        updateLastAssistantMessage(res.reply ?? '', true)
        if (panelState !== 'expanded') incrementUnread()
      }
    } catch {
      updateLastAssistantMessage('Sorry, I could not reach the SAGE backend.', true)
    } finally {
      setIsLoading(false)
    }
  }, [isLoading, pendingAction, userId, sessionId, pathname, solution, panelState,
      queryClient, addMessage, setMessages, setIsLoading, updateLastAssistantMessage,
      incrementUnread, setPendingAction])

  const confirmAction = useCallback(async () => {
    if (!pendingAction) return
    setIsLoading(true)
    const action = pendingAction
    setPendingAction(null)
    try {
      const res = await executeChat({
        action: action.action, params: action.params,
        user_id: userId, session_id: sessionId, solution,
      })
      addMessage({
        id: crypto.randomUUID(), role: 'system' as any,
        content: res.message,
      })
      if (panelState !== 'expanded') incrementUnread()
    } catch (err: any) {
      addMessage({
        id: crypto.randomUUID(), role: 'system' as any,
        content: `Error: ${err.message ?? 'Action failed'}`,
      })
    } finally {
      setIsLoading(false)
    }
  }, [pendingAction, userId, sessionId, solution, panelState,
      addMessage, setIsLoading, incrementUnread, setPendingAction])

  const cancelAction = useCallback(() => {
    if (!pendingAction) return
    setPendingAction(null)
    addMessage({ id: crypto.randomUUID(), role: 'system' as any, content: 'Cancelled.' })
  }, [pendingAction, addMessage, setPendingAction])

  const clearHistory = useCallback(() => {
    setMessages([])
    setPendingAction(null)
    try {
      const params = new URLSearchParams({ user_id: userId, solution })
      fetch(`/api/chat/history?${params}`, { method: 'DELETE' }).catch(() => {})
    } catch {}
  }, [userId, solution, setMessages, setPendingAction])

  return {
    messages, isLoading, sendMessage, clearHistory,
    panelState, openChat, closeChat, minimiseChat, clearUnread,
    pendingAction, confirmAction, cancelAction,
  }
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd C:/sandbox/SAGE/web && npx tsc --noEmit 2>&1 | grep -v "global"
```
Expected: no new errors

- [ ] **Step 3: Commit**

```bash
git add web/src/hooks/useChat.ts
git commit -m "feat(chat): rich page context injection + action routing + confirm/cancel in useChat"
```

---

## Task 7: `ChatPanel.tsx` — confirmation card + system message render

**Context:** The existing message map renders `user` (right-aligned blue) and `assistant` (left-aligned dark) bubbles. We add two new render paths: `system` (slim centred muted) and a confirmation card that replaces the input area when `pendingAction !== null`.

**Files:**
- Modify: `web/src/components/ui/ChatPanel.tsx`

- [ ] **Step 1: Update imports and add `CheckCircle`, `XCircle` icons**

At the top of `ChatPanel.tsx`, update the lucide import to include `CheckCircle` and `XCircle`:

```typescript
import { X, Minus, MessageSquare, Send, Trash2, CheckCircle, XCircle } from 'lucide-react'
```

- [ ] **Step 2: Destructure `pendingAction`, `confirmAction`, `cancelAction` from `useChat`**

Update the destructure line in `ChatPanel`:

```typescript
const {
  messages, isLoading, sendMessage, clearHistory,
  panelState, closeChat, minimiseChat,
  pendingAction, confirmAction, cancelAction,
} = useChat()
```

- [ ] **Step 3: Update the message render loop**

Replace the `{messages.map(msg => (` block with:

```tsx
{messages.map(msg => {
  // System message — slim centred muted line
  if ((msg.role as string) === 'system') {
    return (
      <div key={msg.id} style={{
        textAlign: 'center', fontSize: '11px', color: '#475569',
        padding: '2px 8px', fontStyle: 'italic',
      }}>
        {msg.content}
      </div>
    )
  }
  // User / assistant bubble
  return (
    <div
      key={msg.id}
      style={{
        display: 'flex',
        flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
        alignItems: 'flex-start',
        gap: '8px',
      }}
    >
      <div style={{
        maxWidth: '80%',
        padding: '7px 11px',
        fontSize: '12px', lineHeight: 1.5,
        backgroundColor: msg.role === 'user' ? '#1d4ed8' : '#1e293b',
        color: '#e2e8f0',
        whiteSpace: 'pre-wrap', wordBreak: 'break-word',
      }}>
        {msg.content}
        {msg.streaming && (
          <span style={{
            display: 'inline-block', width: '6px', height: '12px',
            backgroundColor: '#60a5fa', marginLeft: '2px',
            animation: 'sage-cursor-blink 1s step-end infinite',
          }} />
        )}
      </div>
    </div>
  )
})}
```

- [ ] **Step 4: Replace input area with confirmation card when `pendingAction` is set**

Replace the `{/* Input */}` section at the bottom of the expanded panel with:

```tsx
{/* Confirmation card or input */}
{pendingAction ? (
  <div style={{
    borderTop: '2px solid #d97706', flexShrink: 0,
    backgroundColor: '#0f172a', padding: '10px 12px',
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
      <span style={{
        fontSize: '10px', fontWeight: 700, color: '#d97706',
        backgroundColor: '#1c1003', padding: '2px 6px', letterSpacing: '0.04em',
      }}>
        {pendingAction.action.toUpperCase().replace(/_/g, ' ')}
      </span>
    </div>
    <p style={{ fontSize: '12px', color: '#cbd5e1', margin: '0 0 10px', lineHeight: 1.5 }}>
      {pendingAction.confirmation_prompt}
    </p>
    <div style={{ display: 'flex', gap: '8px' }}>
      <button
        onClick={confirmAction}
        disabled={isLoading}
        style={{
          flex: 1, padding: '6px 0', fontSize: '12px', fontWeight: 600,
          backgroundColor: '#166534', color: '#bbf7d0', border: 'none',
          cursor: isLoading ? 'not-allowed' : 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px',
        }}
      >
        <CheckCircle size={13} /> Confirm
      </button>
      <button
        onClick={cancelAction}
        disabled={isLoading}
        style={{
          flex: 1, padding: '6px 0', fontSize: '12px', fontWeight: 600,
          backgroundColor: '#1e293b', color: '#64748b', border: 'none',
          cursor: isLoading ? 'not-allowed' : 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px',
        }}
      >
        <XCircle size={13} /> Cancel
      </button>
    </div>
  </div>
) : (
  <div style={{
    display: 'flex', gap: '8px', padding: '10px 12px',
    borderTop: '1px solid #1e293b', flexShrink: 0,
    backgroundColor: '#0f172a',
  }}>
    <input
      ref={inputRef}
      value={input}
      onChange={e => setInput(e.target.value)}
      onKeyDown={handleKeyDown}
      placeholder="Type a message..."
      disabled={isLoading}
      style={{
        flex: 1, background: '#020617', border: '1px solid #1e293b',
        color: '#e2e8f0', fontSize: '12px', padding: '6px 10px',
        outline: 'none',
      }}
    />
    <button
      onClick={handleSend}
      disabled={isLoading || !input.trim()}
      style={{
        backgroundColor: '#1d4ed8', border: 'none', color: '#fff',
        cursor: isLoading || !input.trim() ? 'not-allowed' : 'pointer',
        opacity: isLoading || !input.trim() ? 0.5 : 1,
        padding: '6px 10px', display: 'flex', alignItems: 'center',
      }}
    >
      <Send size={13} />
    </button>
  </div>
)}
```

- [ ] **Step 5: TypeScript check**

```bash
cd C:/sandbox/SAGE/web && npx tsc --noEmit 2>&1 | grep -v "global"
```
Expected: no new errors

- [ ] **Step 6: Run full backend test suite**

```bash
cd C:/sandbox/SAGE && .venv/Scripts/pytest tests/ -x -q
```
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add web/src/components/ui/ChatPanel.tsx
git commit -m "feat(chat): confirmation card + system message render in ChatPanel"
```

---

## Task 8: Final verification + push

- [ ] **Step 1: Run full test suite**

```bash
cd C:/sandbox/SAGE && .venv/Scripts/pytest tests/ -x -q
```
Expected: all pass

- [ ] **Step 2: TypeScript final check**

```bash
cd C:/sandbox/SAGE/web && npx tsc --noEmit 2>&1 | grep -v "global"
```
Expected: no new errors

- [ ] **Step 3: Git log — verify all 7 feature commits present**

```bash
git log --oneline -8
```
Expected: 7 new commits on top of the branch

- [ ] **Step 4: Push to remote**

```bash
git push -u origin feature/intelligence-layer-proposals
```
