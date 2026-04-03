"""
Product Owner Agent Routes
==========================

API endpoints for the Product Owner agent that converts customer inputs
into structured product requirements.
"""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class QAEntry(BaseModel):
    question: str
    answer: str
    topic: str


class RequirementsGatheringRequest(BaseModel):
    customer_input: str
    follow_up_qa: Optional[List[QAEntry]] = None


class Question(BaseModel):
    question: str
    topic: str
    importance: str
    follow_up_needed: bool = False


class UserPersona(BaseModel):
    name: str
    description: str
    goals: List[str]
    pain_points: List[str]
    technical_comfort: str


class UserStory(BaseModel):
    id: str
    title: str
    description: str
    persona: str
    acceptance_criteria: List[str]
    priority: str
    story_points: int
    business_value: str
    dependencies: List[str]


class ProductBacklog(BaseModel):
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


class RequirementsGatheringResponse(BaseModel):
    status: str
    questions: Optional[List[Question]] = None
    analysis: Optional[Dict] = None
    backlog: Optional[ProductBacklog] = None
    error: Optional[str] = None
    customer_input: Optional[str] = None
    handoff_ready: Optional[bool] = None


@router.post("/product-owner/requirements", response_model=RequirementsGatheringResponse)
async def gather_requirements(request: RequirementsGatheringRequest):
    """
    Gather requirements from customer input using the Product Owner agent.

    Converts basic customer inputs into structured product requirements following
    proper Product Management principles with clarifying questions if needed.
    """
    try:
        # Import here to avoid circular dependency
        from src.agents.product_owner import product_owner_agent

        # Convert Pydantic models to dicts for the agent
        follow_up_qa = None
        if request.follow_up_qa:
            follow_up_qa = [
                {
                    "question": qa.question,
                    "answer": qa.answer,
                    "topic": qa.topic
                }
                for qa in request.follow_up_qa
            ]

        # Call the Product Owner agent
        result = product_owner_agent.gather_requirements(
            customer_input=request.customer_input,
            follow_up_qa=follow_up_qa
        )

        # Convert result to response format
        if result["status"] == "needs_clarification":
            questions = []
            for q in result.get("questions", []):
                questions.append(Question(
                    question=q["question"],
                    topic=q.get("topic", "general"),
                    importance=q.get("importance", "medium"),
                    follow_up_needed=q.get("follow_up_needed", False)
                ))

            return RequirementsGatheringResponse(
                status=result["status"],
                questions=questions,
                analysis=result.get("analysis"),
                customer_input=result.get("customer_input")
            )

        elif result["status"] == "complete":
            backlog_data = result.get("backlog", {})

            # Convert backlog data to Pydantic models
            personas = []
            for p in backlog_data.get("personas", []):
                personas.append(UserPersona(
                    name=p["name"],
                    description=p["description"],
                    goals=p["goals"],
                    pain_points=p["pain_points"],
                    technical_comfort=p["technical_comfort"]
                ))

            user_stories = []
            for story in backlog_data.get("user_stories", []):
                user_stories.append(UserStory(
                    id=story["id"],
                    title=story["title"],
                    description=story["description"],
                    persona=story["persona"],
                    acceptance_criteria=story["acceptance_criteria"],
                    priority=story["priority"],
                    story_points=story["story_points"],
                    business_value=story["business_value"],
                    dependencies=story["dependencies"]
                ))

            backlog = ProductBacklog(
                product_name=backlog_data.get("product_name", ""),
                vision=backlog_data.get("vision", ""),
                target_audience=backlog_data.get("target_audience", ""),
                success_metrics=backlog_data.get("success_metrics", []),
                personas=personas,
                user_stories=user_stories,
                technical_constraints=backlog_data.get("technical_constraints", []),
                business_constraints=backlog_data.get("business_constraints", []),
                created_at=backlog_data.get("created_at", ""),
                po_notes=backlog_data.get("po_notes", "")
            )

            return RequirementsGatheringResponse(
                status=result["status"],
                backlog=backlog,
                handoff_ready=result.get("handoff_ready", True)
            )

        elif result["status"] == "error":
            return RequirementsGatheringResponse(
                status=result["status"],
                error=result.get("error", "Unknown error occurred")
            )

        else:
            return RequirementsGatheringResponse(
                status="error",
                error="Unexpected response from Product Owner agent"
            )

    except Exception as exc:
        logger.error("Product Owner requirements gathering failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))