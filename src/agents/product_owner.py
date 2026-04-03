"""
SAGE[ai] - Product Owner Agent
==============================
Converts basic customer inputs into structured product requirements following
proper Product Management principles.

The Product Owner Agent acts as the interface between customer voice and engineering
requirements. Instead of expecting humans to write perfect product descriptions,
this agent takes basic inputs like "I want a fitness app" and converts them into
proper user stories, acceptance criteria, and prioritized backlogs.

Pattern: Requirements Gathering → User Story Creation → Backlog Management
  1. LLM conducts structured interview with customer
  2. Identifies user personas, journeys, and value propositions
  3. Creates user stories with acceptance criteria
  4. Prioritizes features using MoSCoW method
  5. Outputs structured product backlog for System Engineer

Lean Principles Applied:
- Voice of Customer (capture real user needs)
- Value Stream Mapping (identify user journeys)
- Just-in-Time Requirements (gather details when needed)
- Continuous Customer Feedback (iterative refinement)
"""

import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class UserPersona:
    """Represents a user persona with characteristics and goals."""
    name: str
    description: str
    goals: List[str]
    pain_points: List[str]
    technical_comfort: str  # "low", "medium", "high"


@dataclass
class UserStory:
    """Represents a user story with acceptance criteria."""
    id: str
    title: str
    description: str  # "As a [persona], I want [capability] so that [benefit]"
    persona: str
    acceptance_criteria: List[str]
    priority: str  # "Must Have", "Should Have", "Could Have", "Won't Have"
    story_points: int
    business_value: str
    dependencies: List[str]


@dataclass
class ProductBacklog:
    """Represents a complete product backlog with metadata."""
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


class ProductOwnerAgent:
    """
    Product Owner Agent that converts customer inputs into structured requirements.

    Usage:
        from src.agents.product_owner import product_owner_agent
        backlog = product_owner_agent.gather_requirements("I want a fitness app")
    """

    def __init__(self):
        self.logger = logging.getLogger("ProductOwnerAgent")
        self._llm_gateway = None
        self._audit_logger = None

    @property
    def llm(self):
        if self._llm_gateway is None:
            from src.core.llm_gateway import llm_gateway
            self._llm_gateway = llm_gateway
        return self._llm_gateway

    @property
    def audit(self):
        if self._audit_logger is None:
            from src.memory.audit_logger import audit_logger
            self._audit_logger = audit_logger
        return self._audit_logger

    # -----------------------------------------------------------------------
    # Requirements Gathering (Customer Interview)
    # -----------------------------------------------------------------------

    def gather_requirements(self, customer_input: str, follow_up_qa: Optional[List[Dict]] = None) -> Dict:
        """
        Main entry point: Convert basic customer input into structured product backlog.

        Args:
            customer_input: Basic description like "I want a fitness app"
            follow_up_qa: Optional Q&A from iterative refinement

        Returns:
            Dictionary containing the structured product backlog and clarifying questions
        """
        try:
            self.logger.info("Starting requirements gathering for: %s", customer_input[:100])

            # Phase 1: Analyze customer input and identify gaps
            analysis = self._analyze_customer_input(customer_input, follow_up_qa)

            # Phase 2: Generate clarifying questions if needed
            if analysis.get("needs_clarification", True):
                questions = self._generate_clarifying_questions(customer_input, analysis, follow_up_qa)
                return {
                    "status": "needs_clarification",
                    "questions": questions,
                    "analysis": analysis,
                    "customer_input": customer_input
                }

            # Phase 3: Create structured product backlog
            backlog = self._create_product_backlog(customer_input, analysis, follow_up_qa)

            self.audit.log_event(
                "requirements_gathered",
                {
                    "customer_input": customer_input,
                    "backlog_stories": len(backlog.user_stories),
                    "personas": len(backlog.personas)
                }
            )

            return {
                "status": "complete",
                "backlog": asdict(backlog),
                "handoff_ready": True
            }

        except Exception as exc:
            self.logger.error("Requirements gathering failed: %s", exc)
            return {
                "status": "error",
                "error": str(exc),
                "fallback_suggestion": "Please provide more specific details about your product vision"
            }

    def _analyze_customer_input(self, customer_input: str, follow_up_qa: Optional[List[Dict]] = None) -> Dict:
        """
        Analyze customer input to understand completeness and identify gaps.
        """
        qa_context = ""
        if follow_up_qa:
            qa_context = "\n\nPrevious Q&A:\n" + "\n".join([
                f"Q: {qa['question']}\nA: {qa['answer']}" for qa in follow_up_qa
            ])

        prompt = f"""As an expert Product Owner, analyze this customer input for completeness:

CUSTOMER INPUT: {customer_input}{qa_context}

Analyze the following dimensions:

1. CLARITY: How clear is the customer's vision?
2. USER FOCUS: Are target users identified?
3. VALUE PROPOSITION: Is the core value clear?
4. SCOPE: Is the scope well-defined?
5. SUCCESS METRICS: Are success criteria mentioned?
6. TECHNICAL CONSTRAINTS: Any technical limitations mentioned?
7. BUSINESS CONTEXT: Market, competition, business model clarity?

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

            # Extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)

            # Fallback if JSON extraction fails
            return {
                "needs_clarification": True,
                "clarity_score": 3,
                "identified_domain": "unknown",
                "missing_info": ["unclear requirements"],
                "assumptions": []
            }

        except Exception as exc:
            self.logger.warning("Input analysis failed: %s", exc)
            return {"needs_clarification": True, "clarity_score": 1}

    def _generate_clarifying_questions(self, customer_input: str, analysis: Dict, follow_up_qa: Optional[List[Dict]] = None) -> List[Dict]:
        """
        Generate smart clarifying questions based on analysis gaps.
        """
        missing_info = analysis.get("missing_info", [])
        domain = analysis.get("identified_domain", "unknown")

        qa_context = ""
        if follow_up_qa:
            asked_topics = {qa.get("topic", "") for qa in follow_up_qa}
            qa_context = f"\n\nAlready Asked About: {', '.join(asked_topics)}"

        prompt = f"""As an expert Product Owner, generate 3-5 smart clarifying questions for this customer:

CUSTOMER INPUT: {customer_input}
DOMAIN: {domain}
MISSING INFO: {missing_info}
ANALYSIS: {json.dumps(analysis, indent=2)}{qa_context}

Generate questions that follow the 5W1H method (Who, What, When, Where, Why, How) to understand:

1. USER PERSONAS: Who will use this? What are their characteristics?
2. USER JOURNEYS: What are the key workflows/use cases?
3. VALUE PROPOSITION: Why do users need this? What problem does it solve?
4. SUCCESS CRITERIA: How will you measure success?
5. CONSTRAINTS: Any technical, budget, or timeline constraints?

Return JSON array with:
{{
    "question": "string",
    "topic": "personas|journeys|value_prop|success_metrics|constraints|technical",
    "importance": "high|medium|low",
    "follow_up_needed": boolean
}}

Make questions conversational and specific to their domain. Avoid generic questions."""

        try:
            response = self.llm.generate(prompt)

            start_idx = response.find('[')
            end_idx = response.rfind(']') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                questions = json.loads(json_str)

                # Validate and limit questions
                valid_questions = []
                for q in questions[:5]:  # Max 5 questions
                    if isinstance(q, dict) and "question" in q:
                        q.setdefault("topic", "general")
                        q.setdefault("importance", "medium")
                        valid_questions.append(q)

                return valid_questions

            return [{"question": "Can you tell me more about who would use this product?", "topic": "personas", "importance": "high"}]

        except Exception as exc:
            self.logger.warning("Question generation failed: %s", exc)
            return [{"question": "Could you provide more details about your product vision?", "topic": "general", "importance": "high"}]

    def _create_product_backlog(self, customer_input: str, analysis: Dict, follow_up_qa: Optional[List[Dict]] = None) -> ProductBacklog:
        """
        Create a structured product backlog from gathered requirements.
        """
        qa_context = ""
        if follow_up_qa:
            qa_context = "\n\nCUSTOMER ANSWERS:\n" + "\n".join([
                f"Q: {qa['question']}\nA: {qa['answer']}" for qa in follow_up_qa
            ])

        prompt = f"""As an expert Product Owner, create a structured product backlog from these requirements:

CUSTOMER INPUT: {customer_input}
ANALYSIS: {json.dumps(analysis, indent=2)}{qa_context}

Create a complete product backlog following these principles:
1. User-centered design (personas based on real user needs)
2. Value-driven prioritization (MoSCoW method)
3. INVEST criteria for user stories (Independent, Negotiable, Valuable, Estimable, Small, Testable)
4. Clear acceptance criteria (Given-When-Then format where applicable)

Return JSON with this exact structure:
{{
    "product_name": "string",
    "vision": "one sentence describing the product vision",
    "target_audience": "primary target market description",
    "success_metrics": ["list of measurable success criteria"],
    "personas": [
        {{
            "name": "string",
            "description": "string",
            "goals": ["list of user goals"],
            "pain_points": ["list of current pain points"],
            "technical_comfort": "low|medium|high"
        }}
    ],
    "user_stories": [
        {{
            "id": "US001",
            "title": "short descriptive title",
            "description": "As a [persona], I want [capability] so that [benefit]",
            "persona": "persona name",
            "acceptance_criteria": ["list of testable criteria"],
            "priority": "Must Have|Should Have|Could Have|Won't Have",
            "story_points": 1-13,
            "business_value": "high|medium|low",
            "dependencies": ["list of other user story IDs if dependent"]
        }}
    ],
    "technical_constraints": ["list of technical limitations or requirements"],
    "business_constraints": ["list of business/budget/timeline constraints"]
}}

Create 8-15 user stories covering the MVP and key features. Prioritize using MoSCoW method."""

        try:
            response = self.llm.generate(prompt)

            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                backlog_data = json.loads(json_str)

                # Convert to ProductBacklog dataclass
                personas = [UserPersona(**p) for p in backlog_data.get("personas", [])]
                user_stories = [UserStory(**us) for us in backlog_data.get("user_stories", [])]

                return ProductBacklog(
                    product_name=backlog_data.get("product_name", "Unnamed Product"),
                    vision=backlog_data.get("vision", ""),
                    target_audience=backlog_data.get("target_audience", ""),
                    success_metrics=backlog_data.get("success_metrics", []),
                    personas=personas,
                    user_stories=user_stories,
                    technical_constraints=backlog_data.get("technical_constraints", []),
                    business_constraints=backlog_data.get("business_constraints", []),
                    created_at=datetime.now(timezone.utc).isoformat(),
                    po_notes="Generated from customer requirements gathering"
                )

        except Exception as exc:
            self.logger.warning("Backlog creation failed: %s", exc)

            # Fallback minimal backlog
            return ProductBacklog(
                product_name=analysis.get("identified_domain", "Product"),
                vision=customer_input,
                target_audience="To be defined",
                success_metrics=["User satisfaction", "Product adoption"],
                personas=[],
                user_stories=[],
                technical_constraints=[],
                business_constraints=[],
                created_at=datetime.now(timezone.utc).isoformat(),
                po_notes="Fallback backlog - requires manual refinement"
            )

    # -----------------------------------------------------------------------
    # Backlog Refinement
    # -----------------------------------------------------------------------

    def refine_backlog(self, backlog: Dict, feedback: str, changes: Dict) -> Dict:
        """
        Refine existing backlog based on stakeholder feedback.

        Args:
            backlog: Existing product backlog
            feedback: Stakeholder feedback text
            changes: Specific changes requested

        Returns:
            Refined backlog
        """
        # Implementation for backlog refinement based on feedback
        # This would handle prioritization changes, story updates, etc.
        pass

    def prioritize_stories(self, backlog: Dict, criteria: Dict) -> Dict:
        """
        Re-prioritize user stories based on new criteria.

        Args:
            backlog: Product backlog
            criteria: Prioritization criteria (business value, effort, risk, etc.)

        Returns:
            Backlog with updated priorities
        """
        # Implementation for story prioritization
        pass


# Singleton instance
product_owner_agent = ProductOwnerAgent()