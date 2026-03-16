"""
SAGE Conversational Onboarding — Session Manager
=================================================
Manages multi-turn chat sessions that gather enough domain info to generate
a new SAGE solution (project.yaml, prompts.yaml, tasks.yaml).

Each session progresses through:
  intro  → gathering → ready → generating → complete

The LLM drives the conversation: it receives the full chat history + gathered
info, then either asks another question or signals it has enough.
"""

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("OnboardingSession")

_SESSION_TTL = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ChatMessage:
    role: str          # "assistant" | "user"
    content: str
    ts: float = field(default_factory=time.time)


@dataclass
class GatheredInfo:
    description: str = ""
    solution_name: str = ""
    compliance_standards: List[str] = field(default_factory=list)
    integrations: List[str] = field(default_factory=list)
    team_context: str = ""


@dataclass
class OnboardingSession:
    session_id: str
    state: str          # "gathering" | "ready" | "generating" | "complete"
    messages: List[ChatMessage] = field(default_factory=list)
    info: GatheredInfo = field(default_factory=GatheredInfo)
    proposal_trace_id: Optional[str] = None
    solution_name_final: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "session_id":         self.session_id,
            "state":              self.state,
            "messages":           [{"role": m.role, "content": m.content, "ts": m.ts}
                                   for m in self.messages],
            "info": {
                "description":          self.info.description,
                "solution_name":        self.info.solution_name,
                "compliance_standards": self.info.compliance_standards,
                "integrations":         self.info.integrations,
                "team_context":         self.info.team_context,
            },
            "proposal_trace_id":  self.proposal_trace_id,
            "solution_name_final": self.solution_name_final,
        }


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

_sessions: Dict[str, OnboardingSession] = {}


def _purge_expired():
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s.updated_at > _SESSION_TTL]
    for sid in expired:
        del _sessions[sid]
        logger.debug("Purged expired onboarding session %s", sid)


# ---------------------------------------------------------------------------
# System prompt for the conversation guide LLM
# ---------------------------------------------------------------------------

_GUIDE_SYSTEM_PROMPT = """
You are SAGE's friendly onboarding assistant. Your job is to gather enough info
about a user's domain to generate a complete SAGE solution configuration.

You need to collect (in any order, naturally):
1. What the team builds and their domain (e.g. "We make medical devices", "We run a game studio")
2. A short snake_case name for the solution (e.g. "medical_devices", "game_studio")
3. Any compliance standards they follow (ISO 13485, GDPR, FDA, etc.) — optional
4. Which integrations they use (gitlab, github, slack, jira, etc.) — optional
5. Brief team context (team size, main roles) — optional but helpful

Guidelines:
- Ask ONE focused question at a time
- Keep messages short and friendly — no walls of text
- After 3-5 exchanges you should have enough to generate. Don't over-ask.
- When you have a description AND solution_name AND the user seems satisfied, set ready=true

ALWAYS respond with valid JSON only — no markdown, no preamble:
{
  "reply": "<your conversational message to the user>",
  "extracted": {
    "description":          "<what the domain/business does — leave blank if not yet known>",
    "solution_name":        "<snake_case folder name — leave blank if not yet known>",
    "compliance_standards": ["<standard1>", ...],
    "integrations":         ["<tool1>", ...],
    "team_context":         "<brief team description — leave blank if not yet known>"
  },
  "ready": false
}

Set ready=true only when you have: description (non-empty) AND solution_name (non-empty).
""".strip()


# ---------------------------------------------------------------------------
# LLM conversation turn
# ---------------------------------------------------------------------------

def _run_conversation_turn(session: OnboardingSession, user_message: str) -> str:
    """
    Send the conversation history + new user message to the LLM.
    Parse the JSON response; fall back gracefully if parsing fails.
    Returns the assistant reply text.
    """
    try:
        from src.core.llm_gateway import llm_gateway
    except Exception:
        return "Sorry, the LLM is unavailable right now. Please try again later."

    # Build the conversation prompt
    history_lines = []
    for msg in session.messages[-10:]:   # keep last 10 messages to stay within context
        prefix = "SAGE" if msg.role == "assistant" else "User"
        history_lines.append(f"{prefix}: {msg.content}")
    history_lines.append(f"User: {user_message}")

    # Current gathered state for the LLM's context
    info = session.info
    gathered_summary = (
        f"Currently gathered:\n"
        f"  description:          {info.description or '(not yet gathered)'}\n"
        f"  solution_name:        {info.solution_name or '(not yet gathered)'}\n"
        f"  compliance_standards: {info.compliance_standards or '(not asked yet)'}\n"
        f"  integrations:         {info.integrations or '(not asked yet)'}\n"
        f"  team_context:         {info.team_context or '(not yet gathered)'}"
    )

    prompt = (
        f"{gathered_summary}\n\n"
        f"Conversation so far:\n"
        + "\n".join(history_lines)
        + "\n\nRespond with JSON only."
    )

    raw = llm_gateway.generate(
        prompt=prompt,
        system_prompt=_GUIDE_SYSTEM_PROMPT,
        trace_name="onboarding_conversation",
    )

    # Parse JSON response
    reply_text = ""
    try:
        # Strip markdown fences if present
        clean = re.sub(r"```(?:json)?\s*\n?", "", raw)
        clean = re.sub(r"\n?```", "", clean).strip()
        # Find the JSON object
        match = re.search(r'\{.*\}', clean, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            data = json.loads(clean)

        reply_text = data.get("reply", "")
        extracted = data.get("extracted", {})
        ready = bool(data.get("ready", False))

        # Merge extracted info into session
        if extracted.get("description"):
            session.info.description = extracted["description"]
        if extracted.get("solution_name"):
            # Sanitize to snake_case
            name = re.sub(r"[^a-z0-9_]", "_", extracted["solution_name"].lower())
            name = re.sub(r"_+", "_", name).strip("_")
            session.info.solution_name = name or session.info.solution_name
        if extracted.get("compliance_standards"):
            session.info.compliance_standards = extracted["compliance_standards"]
        if extracted.get("integrations"):
            session.info.integrations = extracted["integrations"]
        if extracted.get("team_context"):
            session.info.team_context = extracted["team_context"]

        if ready and session.info.description and session.info.solution_name:
            session.state = "ready"
            logger.info("Onboarding session %s is ready to generate", session.session_id)

    except Exception as e:
        logger.warning("Failed to parse LLM JSON response: %s — raw: %s", e, raw[:200])
        # Fall back: use raw text as reply, don't update extracted info
        reply_text = raw.strip() if raw.strip() else "Could you tell me more about what you build?"

    return reply_text or "Thanks! Can you tell me a bit more?"


# ---------------------------------------------------------------------------
# Public session API
# ---------------------------------------------------------------------------

def create_session() -> OnboardingSession:
    """Create a new onboarding session with the opening SAGE message."""
    _purge_expired()
    session_id = str(uuid.uuid4())
    session = OnboardingSession(
        session_id=session_id,
        state="gathering",
    )
    opening = (
        "Hi! I'm SAGE's onboarding assistant. I'll help you set up a new solution "
        "tailored to your team and domain.\n\n"
        "To start — tell me what your team builds and what problems you're solving. "
        "No need to be formal, just describe it in your own words."
    )
    session.messages.append(ChatMessage(role="assistant", content=opening))
    _sessions[session_id] = session
    logger.info("Created onboarding session %s", session_id)
    return session


def get_session(session_id: str) -> Optional[OnboardingSession]:
    """Retrieve a session by ID, or None if not found / expired."""
    _purge_expired()
    return _sessions.get(session_id)


def send_message(session_id: str, user_message: str) -> dict:
    """
    Process a user message and return the assistant response.
    Returns: {"reply": str, "state": str, "info": dict, "session_id": str}
    """
    session = get_session(session_id)
    if session is None:
        return {"error": "Session not found or expired. Start a new session."}

    if session.state in ("generating", "complete"):
        return {
            "reply":   "Your solution is already being generated. Check the Proposals panel to approve it.",
            "state":   session.state,
            "info":    session.info.__dict__.copy(),
            "session_id": session_id,
        }

    # Append user message
    session.messages.append(ChatMessage(role="user", content=user_message))
    session.updated_at = time.time()

    # Get LLM response
    reply = _run_conversation_turn(session, user_message)

    # Append assistant reply
    session.messages.append(ChatMessage(role="assistant", content=reply))
    session.updated_at = time.time()

    return {
        "reply":      reply,
        "state":      session.state,
        "info":       session.info.__dict__.copy(),
        "session_id": session_id,
    }


def request_generate(session_id: str) -> dict:
    """
    Trigger YAML generation for a ready session.
    Creates an onboarding_generate HITL proposal.
    Returns the proposal info.
    """
    session = get_session(session_id)
    if session is None:
        return {"error": "Session not found or expired."}

    if not session.info.description:
        return {"error": "Not enough information gathered yet. Continue the conversation."}

    if session.state not in ("ready", "gathering"):
        return {"error": f"Session is in state '{session.state}' — cannot generate now."}

    session.state = "generating"
    session.updated_at = time.time()

    try:
        from src.core.proposal_store import get_proposal_store, RiskClass
        store = get_proposal_store()
        from src.interface.api import _get_required_role
        proposal = store.create(
            action_type   = "onboarding_generate",
            risk_class    = RiskClass.STATEFUL,
            payload       = {
                "description":          session.info.description,
                "solution_name":        session.info.solution_name or "my_solution",
                "compliance_standards": session.info.compliance_standards,
                "integrations":         session.info.integrations,
            },
            description   = (
                f"Generate new SAGE solution: '{session.info.solution_name or 'my_solution'}' "
                f"— {session.info.description[:60]}…"
            ),
            reversible    = False,
            proposed_by   = "onboarding-wizard",
            required_role = _get_required_role("onboarding_generate"),
        )
        session.proposal_trace_id = proposal.trace_id
        session.solution_name_final = session.info.solution_name or "my_solution"
        session.state = "complete"

        completion_msg = (
            f"Your solution configuration is ready to generate.\n\n"
            f"Solution: **{session.solution_name_final}**\n\n"
            f"Go to the **Proposals** panel and approve this to create your solution files. "
            f"Once approved, you can switch to it from the header."
        )
        session.messages.append(ChatMessage(role="assistant", content=completion_msg))

        logger.info(
            "Onboarding generate proposed: session=%s trace=%s",
            session_id, proposal.trace_id,
        )
        return {
            "trace_id":      proposal.trace_id,
            "description":   proposal.description,
            "solution_name": session.solution_name_final,
            "state":         session.state,
        }

    except Exception as e:
        session.state = "ready"   # revert so user can retry
        logger.error("Onboarding generate failed: %s", e)
        return {"error": str(e)}
