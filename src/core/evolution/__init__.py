"""
SAGE Evolutionary Layer

AlphaEvolve-inspired evolutionary improvement of prompts, code, and build plans.
Requires opt-in per solution via evolution.enabled config.
"""

from .candidate import Candidate
from .program_db import ProgramDatabase, get_evolution_db_path
from .evaluators import Evaluator, EnsembleEvaluator
from .prompt_evolver import PromptEvolver

__all__ = [
    "Candidate",
    "ProgramDatabase",
    "get_evolution_db_path",
    "Evaluator",
    "EnsembleEvaluator",
    "PromptEvolver"
]
