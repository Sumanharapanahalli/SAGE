"""Evolution experiment management endpoints — /evolution/*"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["evolution"])

# Mock storage - replace with proper database integration
_experiments: Dict[str, Dict] = {}
_candidates: Dict[str, Dict] = {}

# ── Request Models ────────────────────────────────────────────────────

class StartExperimentRequest(BaseModel):
    solution_name: str
    target_type: str  # 'prompt' | 'code' | 'build'
    population_size: int = 20
    max_generations: int = 50
    mutation_rate: float = 0.1
    crossover_rate: float = 0.7
    evaluator_weights: Optional[Dict[str, float]] = None

class ExperimentUpdateRequest(BaseModel):
    status: Optional[str] = None
    parameters: Optional[Dict] = None

class CandidateApprovalRequest(BaseModel):
    experiment_id: str
    candidate_id: str
    approved: bool
    feedback: Optional[str] = None

# ── Response Models ───────────────────────────────────────────────────

class ExperimentResponse(BaseModel):
    experiment_id: str
    status: str
    solution_name: str
    target_type: str
    current_generation: int
    max_generations: int
    population_size: int
    best_fitness: float
    created_at: str
    parameters: Dict

class ExperimentStatusResponse(BaseModel):
    status: str
    current_generation: int
    best_fitness: float
    population_health: str
    convergence_trend: str

class CandidateResponse(BaseModel):
    candidate_id: str
    experiment_id: str
    generation: int
    fitness_score: float
    status: str  # 'pending' | 'approved' | 'rejected'
    content: Dict
    feedback: Optional[str] = None

class ComplianceReportResponse(BaseModel):
    experiment_id: str
    total_candidates: int
    approved_candidates: int
    rejected_candidates: int
    average_fitness: float
    compliance_score: float
    risk_metrics: Dict

# ── Experiment Management ────────────────────────────────────────────

@router.get("/evolution/experiments")
async def list_experiments():
    """List all evolution experiments with their current status."""
    experiments = []
    for exp_id, exp_data in _experiments.items():
        experiments.append(ExperimentResponse(
            experiment_id=exp_id,
            status=exp_data["status"],
            solution_name=exp_data["solution_name"],
            target_type=exp_data["target_type"],
            current_generation=exp_data["current_generation"],
            max_generations=exp_data["max_generations"],
            population_size=exp_data["population_size"],
            best_fitness=exp_data["best_fitness"],
            created_at=exp_data["created_at"],
            parameters=exp_data["parameters"]
        ))

    return {"experiments": experiments}

@router.post("/evolution/experiments")
async def start_experiment(req: StartExperimentRequest):
    """Start a new evolution experiment."""
    experiment_id = str(uuid.uuid4())

    # Validate solution exists
    if not req.solution_name:
        raise HTTPException(status_code=400, detail="Solution name required")

    # Initialize experiment
    experiment_data = {
        "experiment_id": experiment_id,
        "status": "running",
        "solution_name": req.solution_name,
        "target_type": req.target_type,
        "current_generation": 0,
        "max_generations": req.max_generations,
        "population_size": req.population_size,
        "best_fitness": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "mutation_rate": req.mutation_rate,
            "crossover_rate": req.crossover_rate,
            "evaluator_weights": req.evaluator_weights or {
                "test_driven": 0.4,
                "semantic": 0.3,
                "integration": 0.3
            }
        }
    }

    _experiments[experiment_id] = experiment_data

    return {"experiment_id": experiment_id}

@router.get("/evolution/experiments/{experiment_id}")
async def get_experiment(experiment_id: str):
    """Get detailed experiment information."""
    if experiment_id not in _experiments:
        raise HTTPException(status_code=404, detail="Experiment not found")

    exp_data = _experiments[experiment_id]
    return ExperimentResponse(
        experiment_id=experiment_id,
        status=exp_data["status"],
        solution_name=exp_data["solution_name"],
        target_type=exp_data["target_type"],
        current_generation=exp_data["current_generation"],
        max_generations=exp_data["max_generations"],
        population_size=exp_data["population_size"],
        best_fitness=exp_data["best_fitness"],
        created_at=exp_data["created_at"],
        parameters=exp_data["parameters"]
    )

@router.get("/evolution/experiments/{experiment_id}/status")
async def get_experiment_status(experiment_id: str):
    """Get real-time experiment status and metrics."""
    if experiment_id not in _experiments:
        raise HTTPException(status_code=404, detail="Experiment not found")

    exp_data = _experiments[experiment_id]

    # Calculate population health and convergence
    population_health = "healthy"
    if exp_data["current_generation"] > 10 and exp_data["best_fitness"] < 0.3:
        population_health = "struggling"
    elif exp_data["current_generation"] > 20 and exp_data["best_fitness"] < 0.5:
        population_health = "converging"

    convergence_trend = "improving"
    if exp_data["current_generation"] > 5:
        convergence_trend = "plateauing" if exp_data["best_fitness"] > 0.8 else "improving"

    return ExperimentStatusResponse(
        status=exp_data["status"],
        current_generation=exp_data["current_generation"],
        best_fitness=exp_data["best_fitness"],
        population_health=population_health,
        convergence_trend=convergence_trend
    )

@router.put("/evolution/experiments/{experiment_id}")
async def update_experiment(experiment_id: str, req: ExperimentUpdateRequest):
    """Update experiment parameters or status (pause/resume)."""
    if experiment_id not in _experiments:
        raise HTTPException(status_code=404, detail="Experiment not found")

    exp_data = _experiments[experiment_id]

    if req.status:
        if req.status not in ["running", "paused", "stopped"]:
            raise HTTPException(status_code=400, detail="Invalid status")
        exp_data["status"] = req.status

    if req.parameters:
        exp_data["parameters"].update(req.parameters)

    return {"message": "Experiment updated successfully"}

@router.delete("/evolution/experiments/{experiment_id}")
async def stop_experiment(experiment_id: str):
    """Stop and cleanup evolution experiment."""
    if experiment_id not in _experiments:
        raise HTTPException(status_code=404, detail="Experiment not found")

    _experiments[experiment_id]["status"] = "stopped"

    return {"message": "Experiment stopped"}

# ── Candidate Management ─────────────────────────────────────────────

@router.get("/evolution/experiments/{experiment_id}/candidates")
async def list_candidates(experiment_id: str):
    """List all candidates for an experiment."""
    if experiment_id not in _experiments:
        raise HTTPException(status_code=404, detail="Experiment not found")

    candidates = []
    for cand_id, cand_data in _candidates.items():
        if cand_data["experiment_id"] == experiment_id:
            candidates.append(CandidateResponse(
                candidate_id=cand_id,
                experiment_id=cand_data["experiment_id"],
                generation=cand_data["generation"],
                fitness_score=cand_data["fitness_score"],
                status=cand_data["status"],
                content=cand_data["content"],
                feedback=cand_data.get("feedback")
            ))

    return {"candidates": candidates}

@router.post("/evolution/candidates/approve")
async def approve_candidate(req: CandidateApprovalRequest):
    """Approve or reject a candidate with feedback."""
    candidate_key = f"{req.experiment_id}_{req.candidate_id}"

    if candidate_key not in _candidates:
        # Create mock candidate for testing
        _candidates[candidate_key] = {
            "candidate_id": req.candidate_id,
            "experiment_id": req.experiment_id,
            "generation": 1,
            "fitness_score": 0.75,
            "status": "pending",
            "content": {"type": "mock", "data": "test candidate"},
            "feedback": None
        }

    candidate = _candidates[candidate_key]
    candidate["status"] = "approved" if req.approved else "rejected"
    if req.feedback:
        candidate["feedback"] = req.feedback

    return {
        "candidate_id": req.candidate_id,
        "status": candidate["status"],
        "message": f"Candidate {'approved' if req.approved else 'rejected'}"
    }

# ── Compliance & Reporting ───────────────────────────────────────────

@router.get("/evolution/experiments/{experiment_id}/compliance")
async def get_compliance_report(experiment_id: str):
    """Generate compliance report for an experiment."""
    if experiment_id not in _experiments:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Calculate compliance metrics
    exp_candidates = [c for c in _candidates.values() if c["experiment_id"] == experiment_id]

    total_candidates = len(exp_candidates)
    approved_candidates = sum(1 for c in exp_candidates if c["status"] == "approved")
    rejected_candidates = sum(1 for c in exp_candidates if c["status"] == "rejected")

    if total_candidates > 0:
        average_fitness = sum(c["fitness_score"] for c in exp_candidates) / total_candidates
        compliance_score = (approved_candidates / total_candidates) * 0.7 + (average_fitness * 0.3)
    else:
        average_fitness = 0.0
        compliance_score = 0.0

    risk_metrics = {
        "diversity_risk": "low" if total_candidates > 10 else "high",
        "convergence_risk": "medium" if average_fitness > 0.5 else "low",
        "human_oversight": "adequate" if approved_candidates + rejected_candidates > 0 else "insufficient"
    }

    return ComplianceReportResponse(
        experiment_id=experiment_id,
        total_candidates=total_candidates,
        approved_candidates=approved_candidates,
        rejected_candidates=rejected_candidates,
        average_fitness=round(average_fitness, 3),
        compliance_score=round(compliance_score, 3),
        risk_metrics=risk_metrics
    )