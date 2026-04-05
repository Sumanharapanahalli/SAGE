"""
BFTS (Best-First Tree Search) Evaluator
=========================================

Inspired by AI-Scientist-v2: generates candidate solutions, scores them,
branches the best candidates, and prunes low-scoring paths.

Used by Agent Gym to explore solution spaces for exercises.
"""

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class SearchNode:
    """A node in the search tree."""
    solution: str
    score: float
    depth: int = 0
    parent: Optional["SearchNode"] = field(default=None, repr=False)
    children: list["SearchNode"] = field(default_factory=list)

    def add_child(self, solution: str, score: float) -> "SearchNode":
        child = SearchNode(solution=solution, score=score, depth=self.depth + 1, parent=self)
        self.children.append(child)
        return child


class TreeSearchEvaluator:
    """
    Best-first tree search over candidate solutions.

    Parameters:
        scorer: Function that takes a solution string and returns a score (0-1).
        max_depth: Maximum tree depth.
        branching_factor: How many children to generate per node.
        max_iterations: Hard cap on total scoring calls.
    """

    def __init__(
        self,
        scorer: Callable[[str], float],
        max_depth: int = 3,
        branching_factor: int = 3,
        max_iterations: int = 50,
    ):
        self.scorer = scorer
        self.max_depth = max_depth
        self.branching_factor = branching_factor
        self.max_iterations = max_iterations
        self.root: Optional[SearchNode] = None
        self.iterations = 0

    def evaluate(self, candidates: list[str]) -> Optional[SearchNode]:
        """Run tree search over initial candidates. Returns best node."""
        if not candidates:
            return None

        # Create virtual root
        self.root = SearchNode(solution="<root>", score=0.0)
        self.iterations = 0

        # Score all initial candidates
        frontier: list[SearchNode] = []
        for c in candidates:
            if self.iterations >= self.max_iterations:
                break
            score = self._score(c)
            node = self.root.add_child(c, score)
            frontier.append(node)

        # Best-first expansion
        while frontier and self.iterations < self.max_iterations:
            # Sort by score descending — expand best first
            frontier.sort(key=lambda n: n.score, reverse=True)

            # Take top-k for expansion
            to_expand = frontier[:self.branching_factor]
            frontier = frontier[self.branching_factor:]

            for node in to_expand:
                if node.depth >= self.max_depth:
                    continue
                if self.iterations >= self.max_iterations:
                    break
                # Generate variations (in real use, LLM would generate these)
                # For now, children inherit the parent solution with depth-based variation
                for i in range(self.branching_factor):
                    if self.iterations >= self.max_iterations:
                        break
                    variant = f"{node.solution}_v{node.depth + 1}_{i}"
                    score = self._score(variant)
                    child = node.add_child(variant, score)
                    frontier.append(child)

        # Find best node across entire tree
        return self._best_node(self.root)

    def _score(self, solution: str) -> float:
        self.iterations += 1
        try:
            return self.scorer(solution)
        except Exception as e:
            logger.warning("Scorer failed: %s", e)
            return 0.0

    def _best_node(self, node: SearchNode) -> Optional[SearchNode]:
        """DFS to find highest-scoring node in tree."""
        best = node if node.solution != "<root>" else None
        for child in node.children:
            candidate = self._best_node(child)
            if candidate and (best is None or candidate.score > best.score):
                best = candidate
        return best
