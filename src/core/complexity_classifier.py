"""
Prompt Complexity Classifier
=============================

Classifies prompts into LOW / MEDIUM / HIGH complexity based on heuristics:
- Token count (length proxy)
- Presence of code blocks
- Tool/action keywords that imply multi-step reasoning
- System prompt context (safety-critical domains bump complexity)

Used by the LLM gateway for model routing: simple prompts go to fast/cheap
models, complex prompts go to capable/expensive models.
"""

import re
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# Keywords that indicate complex, multi-step reasoning
_TOOL_KEYWORDS = {
    "implementation_plan", "code_diff", "yaml_edit", "refactor",
    "security", "vulnerability", "architecture", "migration",
    "compliance", "regulatory", "safety-critical", "firmware",
    "review", "analyze", "debug", "optimize",
}

# Code block indicators
_CODE_PATTERNS = re.compile(r"```|def |class |function |import |from .+ import")

# Safety-critical domain keywords in system prompts
_SAFETY_KEYWORDS = {
    "safety-critical", "iec 62304", "iso 26262", "medical device",
    "firmware", "embedded", "compliance", "regulatory",
}


class Complexity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ComplexityClassifier:
    """Heuristic-based prompt complexity classifier."""

    def __init__(
        self,
        low_threshold: int = 15,
        high_threshold: int = 45,
    ):
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold

    def score(self, prompt: str, system_prompt: str = "") -> int:
        """Return a complexity score from 0-100."""
        s = 0

        # Length factor (0-40 points)
        tokens_est = len(prompt.split())
        if tokens_est > 200:
            s += 40
        elif tokens_est > 80:
            s += 30
        elif tokens_est > 20:
            s += 15
        else:
            s += 3

        # Code presence (0-20 points)
        code_matches = len(_CODE_PATTERNS.findall(prompt))
        s += min(20, code_matches * 5)

        # Tool/action keywords (0-25 points)
        lower = prompt.lower()
        keyword_hits = sum(1 for kw in _TOOL_KEYWORDS if kw in lower)
        s += min(25, keyword_hits * 7)

        # System prompt safety context (0-20 points)
        if system_prompt:
            sys_lower = system_prompt.lower()
            safety_hits = sum(1 for kw in _SAFETY_KEYWORDS if kw in sys_lower)
            s += min(20, safety_hits * 7)

        return min(100, s)

    def classify(self, prompt: str, system_prompt: str = "") -> Complexity:
        """Classify prompt complexity."""
        s = self.score(prompt, system_prompt)
        if s >= self.high_threshold:
            return Complexity.HIGH
        if s >= self.low_threshold:
            return Complexity.MEDIUM
        return Complexity.LOW


# Module-level singleton
complexity_classifier = ComplexityClassifier()


def route_to_model(
    complexity: Complexity,
    model_map: dict,
) -> Optional[str]:
    """Return the model name for a given complexity, or None if not configured."""
    return model_map.get(complexity.value)
