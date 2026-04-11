"""
Evolutionary prompt improvement via SDK subagent mutations.

PromptEvolver uses a two-tier strategy:
- Breadth: Haiku subagents for diverse, fast mutations
- Depth: Opus subagents for high-quality refinement of top candidates

Mutation strategies include enhance specificity, improve clarity, add constraints,
remove redundancy, optimize for task type, and more.
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from .candidate import Candidate

logger = logging.getLogger(__name__)


class PromptEvolver:
    """
    Evolutionary prompt improvement via SDK subagent mutations.

    Uses two-tier strategy:
    - Breadth: Haiku subagents for diverse, fast mutations
    - Depth: Opus subagents for high-quality refinement of top candidates

    Mutation strategies: enhance specificity, improve clarity, add constraints,
    remove redundancy, optimize for task type, etc.
    """

    def __init__(self, mutation_rate: float = 0.6, crossover_rate: float = 0.4):
        """
        Initialize PromptEvolver with reproduction strategy weights.

        Args:
            mutation_rate: Probability of single-parent mutation (vs crossover)
            crossover_rate: Probability of two-parent crossover (vs mutation)

        Note: mutation_rate + crossover_rate should equal 1.0 (warning if not)
        """
        if mutation_rate + crossover_rate != 1.0:
            logger.warning(
                f"Mutation rate {mutation_rate} + crossover rate {crossover_rate} != 1.0. "
                f"Will normalize to {mutation_rate} and {crossover_rate}."
            )

        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate

        # Mutation strategies - different approaches for prompt improvement
        self._mutation_strategies = {
            "enhance_specificity": "Make the prompt more specific and detailed for better task performance",
            "improve_clarity": "Rewrite the prompt to be clearer and more understandable",
            "add_constraints": "Add helpful constraints and guidelines to improve output quality",
            "remove_redundancy": "Remove redundant or unnecessary parts while preserving meaning",
            "optimize_for_task": "Optimize the prompt specifically for the target task type",
            "add_examples": "Add helpful examples or formatting instructions",
        }

        logger.info(
            f"PromptEvolver initialized: mutation={mutation_rate}, crossover={crossover_rate}"
        )

    def get_mutation_strategies(self) -> List[str]:
        """Get list of available mutation strategy names."""
        return list(self._mutation_strategies.keys())

    def should_crossover(self) -> bool:
        """Decide whether to use crossover (vs mutation) based on configured rates."""
        return random.random() < self.crossover_rate

    async def crossover(self, parent1: Candidate, parent2: Candidate) -> Candidate:
        """
        Create child candidate by combining two parent prompts.

        Uses SDK subagent to intelligently merge the best aspects of both parents.

        Args:
            parent1: First parent prompt candidate
            parent2: Second parent prompt candidate

        Returns:
            Child candidate with combined genetic material from both parents
        """
        crossover_prompt = f"""
        Combine these two system prompts into a single improved prompt that takes the best elements from both:

        Prompt A: {parent1.content}

        Prompt B: {parent2.content}

        Create a new prompt that:
        - Combines the strengths of both prompts
        - Maintains clarity and coherence
        - Is more effective than either parent alone
        - Keeps the same general purpose/role

        Return only the new prompt text, no explanations.
        """

        result = await self._call_mutation_subagent(crossover_prompt, use_opus=True)

        child = Candidate(
            id=f"cross-{uuid.uuid4().hex[:8]}",
            content=result.strip(),
            candidate_type="prompt",
            fitness=0.0,  # Uneval
            parent_ids=[parent1.id, parent2.id],
            generation=max(parent1.generation, parent2.generation) + 1,
            metadata={
                "mutation_type": "crossover",
                "parent_fitness": [parent1.fitness, parent2.fitness]
            },
            created_at=datetime.now(timezone.utc)
        )

        logger.debug(f"Crossover: {parent1.id} + {parent2.id} → {child.id}")
        return child

    async def mutate(
        self, parent: Candidate, strategy: Optional[str] = None
    ) -> Candidate:
        """
        Create mutated child candidate from single parent.

        Uses specified strategy or picks random one.

        Args:
            parent: Parent prompt candidate to mutate
            strategy: Optional mutation strategy name. If None, selects randomly.

        Returns:
            Mutated child candidate
        """
        if strategy is None:
            strategy = random.choice(self.get_mutation_strategies())

        strategy_description = self._mutation_strategies[strategy]

        mutation_prompt = f"""
        Improve this system prompt using the following strategy: {strategy_description}

        Current prompt: {parent.content}

        Create an improved version that:
        - Applies the improvement strategy effectively
        - Maintains the core purpose and role
        - Is measurably better than the original
        - Uses clear, professional language

        Return only the improved prompt text, no explanations.
        """

        # Use Haiku for breadth mutations (faster, cheaper)
        result = await self._call_mutation_subagent(mutation_prompt, use_opus=False)

        mutant = Candidate(
            id=f"mut-{uuid.uuid4().hex[:8]}",
            content=result.strip(),
            candidate_type="prompt",
            fitness=0.0,  # Uneval
            parent_ids=[parent.id],
            generation=parent.generation + 1,
            metadata={
                "mutation_type": "mutation",
                "mutation_strategy": strategy,
                "parent_fitness": parent.fitness,
                "role_id": parent.metadata.get("role_id", "unknown")
            },
            created_at=datetime.now(timezone.utc)
        )

        logger.debug(f"Mutation: {parent.id} → {mutant.id} (strategy: {strategy})")
        return mutant

    async def _call_mutation_subagent(self, prompt: str, use_opus: bool = False) -> str:
        """
        Call SDK subagent for prompt mutation.

        In real implementation, this would use AgentSDKRunner with proper
        model selection (Haiku for breadth, Opus for depth).

        Args:
            prompt: The mutation instruction prompt for the subagent
            use_opus: If True, use Opus model. If False, use Haiku for speed.

        Returns:
            Improved prompt text from the subagent
        """
        # Placeholder for SDK integration - will be implemented when AgentSDKRunner
        # has run_with_evolution() method. Tests can mock this method.
        model = "opus" if use_opus else "haiku"
        logger.debug(f"Mutation subagent call ({model}): {prompt[:50]}...")

        # For now, return the prompt (tests can mock this method)
        return prompt
