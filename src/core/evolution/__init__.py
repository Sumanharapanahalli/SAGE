"""
SAGE Evolutionary Layer

AlphaEvolve-inspired evolutionary improvement of prompts, code, and build plans.
Requires opt-in per solution via evolution.enabled config.
"""

from .candidate import Candidate

__all__ = ["Candidate"]
