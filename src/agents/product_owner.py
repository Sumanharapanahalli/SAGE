"""
SAGE[ai] - Product Owner Agent
==============================
Converts basic customer inputs into structured product requirements following
proper Product Management principles.

The Product Owner Agent acts as the interface between customer voice and engineering
requirements. Instead of expecting humans to write perfect product descriptions,
this agent takes basic inputs like "I want a fitness app" and converts them into
proper user stories, acceptance criteria, and prioritized backlogs.

Pattern: Requirements Gathering -> User Story Creation -> Backlog Management
  1. LLM conducts structured interview with customer
  2. Identifies user personas, journeys, and value propositions
  3. Creates user stories with acceptance criteria
  4. Prioritizes features using MoSCoW method
  5. Outputs structured product backlog — pending human approval (HITL gate)

SAGE Law 1: gather_requirements() returns status="pending_approval".
Only approve_backlog() may set handoff_ready=True, and only after explicit
human sign-off. The agent proposes; the human decides.
"""

import json
import logging
import re
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, TypedDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input limits
# ---------------------------------------------------------------------------

_MAX_INPUT_CHARS = 2_000
_MAX_INPUT_LEN = 100_000
_MIN_INPUT_WORDS = 5
_MIN_CLARITY_SCORE = 6


# ---------------------------------------------------------------------------
# TypedDicts for internal LLM response shapes
# ---------------------------------------------------------------------------

class AnalysisResult(TypedDict, total=False):
    needs_clarification: bool
    clarity_score: int
    identified_domain: str
    potential_personas: List[str]
    core_value_prop: Optional[str]
    missing_info: List[str]
    assumptions: List[str]


class ClarifyingQuestion(TypedDict, total=False):
    question: str
    topic: str
    importance: str
    follow_up_needed: bool


# ---------------------------------------------------------------------------
# Domain dataclasses
# ---------------------------------------------------------------------------

@dataclass
class UserPersona:
    name: str
    description: str
    goals: List[str]
    pain_points: List[str]
    technical_comfort: str  # "low" | "medium" | "high"


@dataclass
class UserStory:
    id: str
    title: str
    description: str   # "As a [persona], I want [capability] so that [benefit]"
    persona: str
    acceptance_criteria: List[str]
    priority: str      # "Must Have" | "Should Have" | "Could Have" | "Won't Have"
    story_points: int
    business_value: str
    dependencies: List[str]


@dataclass
class ProductBacklog:
    product_name: str
    vision: str
    target_audience: str
    success_metrics: List[str]
    personas: List[UserPersona]
    user_stories: List[UserStory]
    technical_constraints: List[str]
    business_constraints: List[str]
    created_at: str
    po_notes: str


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions, no LLM dependency)
# ---------------------------------------------------------------------------

def _validate_input(text: str) -> None:
    """Raise ValueError for empty or oversized input."""
    if not text or not text.strip():
        raise ValueError("customer_input must not be empty")
    if len(text) > _MAX_INPUT_LEN:
        raise ValueError(
            f"customer_input exceeds maximum length ({len(text)} chars, limit {_MAX_INPUT_LEN})"
        )


def _sanitise_input(text: str) -> str:
    """Truncate and XML-delimit customer input to prevent prompt injection."""
    truncated = text.strip()[:_MAX_INPUT_CHARS]
    return f"<customer_input>\n{truncated}\n</customer_input>"


def _parse_json_object(text: str) -> Dict:
    """
    Extract the first valid JSON object from an LLM response.
    Uses raw_decode to correctly handle } inside string values.
    """
    try:
        result = json.loads(text.strip())
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    for match in re.finditer(r'\{', text):
        try:
            obj, _ = json.JSONDecoder().raw_decode(text, match.start())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue

    raise json.JSONDecodeError("No valid JSON object found in LLM response", text, 0)


def _parse_json_array(text: str) -> List:
    """Extract the first valid JSON array from an LLM response."""
    try:
        result = json.loads(text.strip())
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    for match in re.finditer(r'\[', text):
        try:
            arr, _ = json.JSONDecoder().raw_decode(text, match.start())
            if isinstance(arr, list):
                return arr
        except json.JSONDecodeError:
            continue

    raise json.JSONDecodeError("No valid JSON array found in LLM response", text, 0)


def _format_qa_context(follow_up_qa: Optional[List[Dict]]) -> str:
    if not follow_up_qa:
        return ""
    lines = "\n".join(
        f"Q: {qa.get('question', '')}\nA: {qa.get('answer', '')}"
        for qa in follow_up_qa
    )
    return f"\n\nCUSTOMER ANSWERS:\n{lines}"


def _validate_backlog_standards(data: Dict) -> None:
    """
    Raise ValueError if any story violates GWT (Testable/INVEST) constraints.
    Each story needs >= 2 acceptance criteria, each in Given-When-Then format.
    """
    gwt_keywords = ("given ", "when ", "then ")
    for story in data.get("user_stories", []):
        sid = story.get("id", "?")
        criteria = story.get("acceptance_criteria", [])
        if len(criteria) < 2:
            raise ValueError(
                f"Story {sid} has fewer than 2 acceptance criteria (INVEST: Testable)"
            )
        for criterion in criteria:
            lower = criterion.lower()
            if not all(kw in lower for kw in gwt_keywords):
                raise ValueError(
                    f"Story {sid} criterion not in Given-When-Then format: {criterion!r}"
                )


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------

class ProductOwnerAgent:
    """
    Product Owner Agent - converts customer inputs into structured requirements.

    Usage:
        from src.agents.product_owner import product_owner_agent
        result = product_owner_agent.gather_requirements("I want a fitness app")
        # result["status"] == "pending_approval"
        # Human reviews backlog, then:
        approved = product_owner_agent.approve_backlog(result["backlog"], approver_id="alice")
        # approved["handoff_ready"] == True
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("ProductOwnerAgent")
        self._llm_gateway = None
        self._audit_logger = None
        self._init_lock = threading.Lock()

    # -- lazy, thread-safe properties ----------------------------------------

    @property
    def llm(self):
        if self._llm_gateway is None:
            with self._init_lock:
                if self._llm_gateway is None:
                    from src.core.llm_gateway import llm_gateway
                    self._llm_gateway = llm_gateway
        return self._llm_gateway

    @property
    def audit(self):
        if self._audit_logger is None:
            with self._init_lock:
                if self._audit_logger is None:
                    from src.memory.audit_logger import audit_logger
                    self._audit_logger = audit_logger
        return self._audit_logger

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def gather_requirements(
        self,
        customer_input: str,
        follow_up_qa: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Convert customer input into a structured product backlog proposal.

        Returns status="pending_approval" - NEVER "complete".
        Only approve_backlog() may set handoff_ready=True (SAGE Law 1).
        """
        try:
            _validate_input(customer_input)
            self.logger.info("Starting requirements gathering: %.100s", customer_input)

            analysis = self._analyze_customer_input(customer_input, follow_up_qa)

            if self._requires_clarification(customer_input, analysis):
                questions = self._generate_clarifying_questions(
                    customer_input, analysis, follow_up_qa
                )
                self.audit.log_event(
                    "requirements_clarification_requested",
                    {
                        "customer_input": customer_input[:200],
                        "question_count": len(questions),
                    },
                )
                return {
                    "status": "needs_clarification",
                    "questions": questions,
                    "analysis": analysis,
                    "customer_input": customer_input,
                    "handoff_ready": False,
                }

            backlog = self._create_product_backlog(customer_input, analysis, follow_up_qa)
            self.audit.log_event(
                "requirements_proposed",
                {
                    "customer_input": customer_input[:200],
                    "backlog_stories": len(backlog.user_stories),
                    "personas": len(backlog.personas),
                },
            )
            # HITL gate: human must call approve_backlog() before handoff_ready=True
            return {
                "status": "pending_approval",
                "backlog": asdict(backlog),
                "handoff_ready": False,
            }

        except ValueError as exc:
            self.logger.error("Invalid input: %s", exc)
            self.audit.log_event(
                "requirements_error",
                {"error": str(exc), "customer_input": (customer_input or "")[:200]},
            )
            return {
                "status": "error",
                "error": str(exc),
                "fallback_suggestion": "Please provide more specific details about your product vision",
            }
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            self.logger.error("Requirements gathering failed: %s", exc)
            self.audit.log_event(
                "requirements_error",
                {"error": str(exc), "customer_input": customer_input[:200]},
            )
            return {
                "status": "error",
                "error": str(exc),
                "fallback_suggestion": "Please provide more specific details about your product vision",
            }

    def approve_backlog(
        self,
        backlog: Dict,
        approver_id: str,
    ) -> Dict:
        """
        HITL gate: human explicitly approves a proposed backlog.
        The ONLY method that may set handoff_ready=True (SAGE Law 1).
        """
        self.audit.log_event(
            "backlog_approved",
            {
                "approver_id": approver_id,
                "product_name": backlog.get("product_name"),
            },
        )
        return {
            "status": "complete",
            "backlog": backlog,
            "handoff_ready": True,
            "approved_by": approver_id,
        }

    def refine_backlog(
        self,
        backlog: Dict,
        refinement_notes: str,
        requester_id: str,
    ) -> Dict:
        """
        Incorporate stakeholder refinement notes into an existing backlog.
        Enforces INVEST criteria and GWT acceptance criteria in the prompt.
        Always returns pending_approval - never auto-promotes to handoff_ready.
        """
        if not refinement_notes or not refinement_notes.strip():
            raise ValueError("refinement_notes must not be empty")

        safe_notes = _sanitise_input(refinement_notes)

        prompt = f"""You are a senior Product Owner refining a product backlog based on stakeholder feedback.

EXISTING BACKLOG:
{json.dumps(backlog, indent=2)}

REFINEMENT NOTES:
{safe_notes}

Update the backlog to incorporate the feedback. ALL stories MUST satisfy:

1. INVEST CRITERIA:
   - Independent, Negotiable, Valuable, Estimable, Small, Testable

2. GIVEN-WHEN-THEN ACCEPTANCE CRITERIA (minimum 2 per story):
   Format: "Given [precondition], When [actor action], Then [observable outcome]"

3. MOSCOW PRIORITIZATION: Must Have <= 60% of total stories

Return the complete updated backlog using the exact same JSON structure as the input."""

        try:
            response = self.llm.generate(prompt)
            updated = _parse_json_object(response)
            self.audit.log_event(
                "backlog_refined",
                {
                    "requester_id": requester_id,
                    "product_name": backlog.get("product_name"),
                    "notes_length": len(refinement_notes),
                    "story_count": len(updated.get("user_stories", [])),
                },
            )
            return {
                "status": "pending_approval",
                "backlog": updated,
                "handoff_ready": False,
                "refined_by": requester_id,
            }
        except json.JSONDecodeError as exc:
            self.logger.error("Backlog refinement returned invalid JSON: %s", exc)
            self.audit.log_event("refinement_error", {"error": str(exc), "requester_id": requester_id})
            return {"status": "error", "error": str(exc)}
        except KeyError as exc:
            self.logger.error("Unexpected refinement response shape: %s", exc)
            self.audit.log_event("refinement_error", {"error": str(exc), "requester_id": requester_id})
            return {"status": "error", "error": str(exc)}

    def prioritize_stories(
        self,
        stories: List[Dict],
        business_context: str = "",
    ) -> Dict:
        """
        Re-prioritize a list of user stories using MoSCoW method.
        Enforces a hard 60% Must Have cap in code (not just in the prompt).
        Returns pending_approval - requires human sign-off before backlog update.
        """
        if not stories:
            raise ValueError("stories must not be empty")

        safe_context = _sanitise_input(business_context) if business_context else "Not provided"

        prompt = f"""You are a senior Product Owner applying MoSCoW prioritization.

BUSINESS CONTEXT: {safe_context}

USER STORIES ({len(stories)} total):
{json.dumps(stories, indent=2)}

Apply strict MoSCoW rules. HARD CAP: Must Have <= 60% of total stories.

For each story preserve all existing fields and ADD:
  "priority": "Must Have" | "Should Have" | "Could Have" | "Won't Have"
  "priority_rationale": one sentence explaining the assignment

Return JSON:
{{
    "must_have":   [ /* stories */ ],
    "should_have": [ /* stories */ ],
    "could_have":  [ /* stories */ ],
    "wont_have":   [ /* stories */ ],
    "total_story_points": integer,
    "must_have_percentage": float,
    "prioritization_rationale": "string"
}}"""

        try:
            response = self.llm.generate(prompt)
            result = _parse_json_object(response)

            # Hard 60% cap enforcement — LLM may exceed cap despite the instruction
            all_stories = (
                result.get("must_have", [])
                + result.get("should_have", [])
                + result.get("could_have", [])
                + result.get("wont_have", [])
            )
            total = len(all_stories)
            cap = int(total * 0.60)
            if total > 0 and len(result.get("must_have", [])) > cap:
                self.logger.warning(
                    "LLM assigned %d/%d stories as Must Have (>60%%) — capping to %d",
                    len(result["must_have"]), total, cap,
                )
                overflow = result["must_have"][cap:]
                result["must_have"] = result["must_have"][:cap]
                for s in overflow:
                    s["priority"] = "Should Have"
                    s.setdefault("priority_rationale", "Reclassified: Must Have cap exceeded")
                result["should_have"] = overflow + result.get("should_have", [])

            self.audit.log_event(
                "stories_prioritized",
                {
                    "total": total,
                    "must_have": len(result.get("must_have", [])),
                    "should_have": len(result.get("should_have", [])),
                    "could_have": len(result.get("could_have", [])),
                    "wont_have": len(result.get("wont_have", [])),
                },
            )
            return {
                "status": "pending_approval",
                "prioritized_stories": result,
                "handoff_ready": False,
            }

        except json.JSONDecodeError as exc:
            self.logger.error("MoSCoW prioritization returned invalid JSON: %s", exc)
            self.audit.log_event("prioritization_error", {"error": str(exc)})
            return {"status": "error", "error": str(exc)}
        except KeyError as exc:
            self.logger.error("Unexpected prioritization response shape: %s", exc)
            self.audit.log_event("prioritization_error", {"error": str(exc)})
            return {"status": "error", "error": str(exc)}

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _requires_clarification(
        self,
        customer_input: str,
        analysis: AnalysisResult,
    ) -> bool:
        """Hard floors applied before trusting LLM opinion."""
        if len(customer_input.split()) < _MIN_INPUT_WORDS:
            return True
        try:
            if int(analysis.get("clarity_score", 0)) < _MIN_CLARITY_SCORE:
                return True
        except (ValueError, TypeError):
            return True
        return bool(analysis.get("needs_clarification", True))

    def _analyze_customer_input(
        self,
        customer_input: str,
        follow_up_qa: Optional[List[Dict]] = None,
    ) -> AnalysisResult:
        safe_input = _sanitise_input(customer_input)
        qa_context = _format_qa_context(follow_up_qa)

        prompt = f"""As an expert Product Owner, analyze this customer input for completeness:

CUSTOMER INPUT: {safe_input}{qa_context}

Return JSON with:
{{
    "needs_clarification": boolean,
    "clarity_score": 1-10,
    "identified_domain": "string",
    "potential_personas": ["list"],
    "core_value_prop": "string or null",
    "missing_info": ["list of gaps"],
    "assumptions": ["list of assumptions to validate"]
}}"""

        try:
            response = self.llm.generate(prompt)
            return _parse_json_object(response)
        except json.JSONDecodeError as exc:
            self.logger.warning("LLM returned invalid JSON in analysis: %s", exc)
            return {
                "needs_clarification": True,
                "clarity_score": 1,
                "missing_info": ["unclear requirements"],
                "assumptions": [],
            }
        except KeyError as exc:
            self.logger.warning("Unexpected LLM response shape in analysis: %s", exc)
            return {"needs_clarification": True, "clarity_score": 1}

    def _generate_clarifying_questions(
        self,
        customer_input: str,
        analysis: AnalysisResult,
        follow_up_qa: Optional[List[Dict]] = None,
    ) -> List[ClarifyingQuestion]:
        _DEFAULT: List[ClarifyingQuestion] = [
            {
                "question": "Who are the primary users of this product?",
                "topic": "personas",
                "importance": "high",
                "follow_up_needed": False,
            }
        ]
        safe_input = _sanitise_input(customer_input)
        missing_info = analysis.get("missing_info", [])
        domain = analysis.get("identified_domain", "unknown")

        asked_context = ""
        if follow_up_qa:
            asked = {qa.get("topic", "") for qa in follow_up_qa}
            asked_context = f"\n\nAlready Asked About: {', '.join(asked)}"

        prompt = f"""As an expert Product Owner, generate 3-5 smart clarifying questions:

CUSTOMER INPUT: {safe_input}
DOMAIN: {domain}
MISSING INFO: {missing_info}{asked_context}

Return JSON array:
[{{
    "question": "string",
    "topic": "personas|journeys|value_prop|success_metrics|constraints|technical",
    "importance": "high|medium|low",
    "follow_up_needed": boolean
}}]"""

        try:
            response = self.llm.generate(prompt)
            questions = _parse_json_array(response)
            valid: List[ClarifyingQuestion] = []
            for q in questions[:5]:
                if isinstance(q, dict) and "question" in q:
                    q.setdefault("topic", "general")
                    q.setdefault("importance", "medium")
                    q.setdefault("follow_up_needed", False)
                    valid.append(q)
            return valid or _DEFAULT
        except json.JSONDecodeError as exc:
            self.logger.warning("LLM returned invalid JSON for questions: %s", exc)
            return _DEFAULT
        except (KeyError, TypeError) as exc:
            self.logger.warning("Unexpected question structure: %s", exc)
            return _DEFAULT

    def _create_product_backlog(
        self,
        customer_input: str,
        analysis: AnalysisResult,
        follow_up_qa: Optional[List[Dict]] = None,
    ) -> ProductBacklog:
        safe_input = _sanitise_input(customer_input)
        qa_context = _format_qa_context(follow_up_qa)
        now = datetime.now(timezone.utc).isoformat()

        prompt = f"""You are a senior Product Owner creating a comprehensive product backlog.

CUSTOMER INPUT:
{safe_input}

ANALYSIS:
{json.dumps(analysis, indent=2)}{qa_context}

=== MANDATORY STANDARDS ===

INVEST CRITERIA: every story must satisfy Independent, Negotiable, Valuable,
Estimable, Small (1 sprint), Testable.

ACCEPTANCE CRITERIA — Given-When-Then format, minimum 2 per story:
  OK:  "Given I am logged in, When I tap Log Workout, Then the form appears in 2s"
  NOT OK: "The system should be fast"

MOSCOW: Must Have <= 60% of all stories.

Return valid JSON only:
{{
    "product_name": "string",
    "vision": "string",
    "target_audience": "string",
    "success_metrics": ["string"],
    "personas": [{{"name":"string","description":"string","goals":[],"pain_points":[],"technical_comfort":"low|medium|high"}}],
    "user_stories": [{{
        "id": "US-001",
        "title": "string",
        "description": "As a [persona], I want [capability] so that [benefit]",
        "persona": "string",
        "acceptance_criteria": ["Given ..., When ..., Then ...","Given ..., When ..., Then ..."],
        "priority": "Must Have|Should Have|Could Have|Won't Have",
        "story_points": 1,
        "business_value": "string",
        "dependencies": []
    }}],
    "technical_constraints": [],
    "business_constraints": [],
    "created_at": "{now}",
    "po_notes": "string"
}}

Create 8-15 user stories covering the MVP and key features."""

        try:
            response = self.llm.generate(prompt)
            data = _parse_json_object(response)
            _validate_backlog_standards(data)

            personas = [UserPersona(**p) for p in data.get("personas", [])]
            user_stories = [UserStory(**us) for us in data.get("user_stories", [])]

            return ProductBacklog(
                product_name=data.get("product_name", "Unnamed Product"),
                vision=data.get("vision", ""),
                target_audience=data.get("target_audience", ""),
                success_metrics=data.get("success_metrics", []),
                personas=personas,
                user_stories=user_stories,
                technical_constraints=data.get("technical_constraints", []),
                business_constraints=data.get("business_constraints", []),
                created_at=data.get("created_at", now),
                po_notes=data.get("po_notes", ""),
            )
        except json.JSONDecodeError as exc:
            self.logger.error("Backlog creation returned invalid JSON: %s", exc)
            raise
        except (KeyError, TypeError, ValueError) as exc:
            self.logger.error("Backlog response missing required fields: %s", exc)
            raise


# Singleton instance
product_owner_agent = ProductOwnerAgent()
