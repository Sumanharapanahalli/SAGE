"""
SAGE Evolutionary Layer

AlphaEvolve-inspired evolutionary improvement of prompts, code, and build plans.
Requires opt-in per solution via evolution.enabled config.
"""

from .candidate import Candidate
from .program_db import ProgramDatabase, get_evolution_db_path
from .evaluators import Evaluator, EnsembleEvaluator
from .orchestrator import EvolutionOrchestrator
from .prompt_evolver import PromptEvolver
from .prompt_evaluator import PromptEvaluator
from .code_evolver import CodeEvolver
from .code_evaluator import CodeEvaluator
from .build_evolver import BuildEvolver
from .build_evaluator import BuildEvaluator

__all__ = [
    "Candidate",
    "ProgramDatabase",
    "get_evolution_db_path",
    "Evaluator",
    "EnsembleEvaluator",
    "EvolutionOrchestrator",
    "PromptEvolver",
    "PromptEvaluator",
    "CodeEvolver",
    "CodeEvaluator",
    "BuildEvolver",
    "BuildEvaluator"
]
