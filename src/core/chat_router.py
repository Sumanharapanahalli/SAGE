"""
chat_router.py — LLM-as-router for action-aware chat.

Builds a structured system prompt that instructs the LLM to classify the
user's message as either a plain answer or an actionable intent, then parses
the LLM's JSON response into a dict consumed by the /chat endpoint.
"""
import json
import logging

logger = logging.getLogger(__name__)

# Module-level reference populated on first import of llm_gateway.
# Declared here so tests can patch src.core.chat_router.llm_gateway directly.
try:
    from src.core.llm_gateway import llm_gateway
except Exception:  # pragma: no cover — gateway may not be configured in test env
    llm_gateway = None  # type: ignore[assignment]

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
    if llm_gateway is None:
        logger.error("chat_router: llm_gateway not available")
        return {"type": "answer", "reply": "LLM gateway is not configured."}
    system_prompt = build_router_system_prompt(solution, domain, page_context)
    prompt = f"{history_text}User: {message}\nAssistant:"
    try:
        raw = llm_gateway.generate(prompt, system_prompt=system_prompt)
        return parse_router_response(raw)
    except Exception as exc:
        logger.error("chat_router LLM error: %s", exc)
        return {"type": "answer", "reply": "Sorry, I could not process your message right now. Please try again."}
