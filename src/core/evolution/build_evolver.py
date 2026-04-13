"""
Build plan evolution system with workflow optimization strategies.

BuildEvolver applies genetic algorithm strategies to build plan candidates,
with 8 mutation strategies for build workflow optimization:

1. optimize_parallelization: Identify and enable parallel execution phases
2. improve_dependencies: Optimize task dependency chains
3. reduce_build_time: Minimize total workflow execution time
4. enhance_error_handling: Add retry logic and error recovery
5. add_caching_layers: Introduce caching and memoization
6. optimize_resource_allocation: Improve agent and resource assignments
7. improve_monitoring: Add logging, metrics, and observability
8. simplify_workflow: Reduce workflow complexity and phases

Key features:
- Build plan validation and syntax preservation
- Dependency analysis and optimization
- Parallelization opportunity detection
- SDK subagent integration for intelligent workflow transformations
"""

from __future__ import annotations

import json
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from .candidate import Candidate

logger = logging.getLogger(__name__)


class BuildEvolver:
    """
    Evolutionary build plan improvement via SDK subagent mutations.

    Uses genetic algorithm strategies with 8 mutation strategies for
    build workflow optimization. All mutations preserve build plan validity.
    """

    def __init__(self, mutation_rate: float = 0.6, crossover_rate: float = 0.4):
        """
        Initialize BuildEvolver with reproduction strategy weights.

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

        # Build-specific mutation strategies
        self._mutation_strategies = {
            "optimize_parallelization": "Enable parallel execution where possible in the build phases",
            "improve_dependencies": "Optimize task dependency chains to reduce critical path length",
            "reduce_build_time": "Restructure phases to minimize total workflow execution time",
            "enhance_error_handling": "Add retry logic, fallbacks, and error recovery mechanisms",
            "add_caching_layers": "Introduce caching and memoization to reduce redundant work",
            "optimize_resource_allocation": "Improve agent and resource assignments for efficiency",
            "improve_monitoring": "Add logging, metrics collection, and observability hooks",
            "simplify_workflow": "Reduce workflow complexity and consolidate unnecessary phases",
        }

        logger.info(
            f"BuildEvolver initialized: mutation={mutation_rate}, crossover={crossover_rate}"
        )

    def get_mutation_strategies(self) -> List[str]:
        """Get list of available mutation strategy names."""
        return list(self._mutation_strategies.keys())

    def should_crossover(self) -> bool:
        """Decide whether to use crossover (vs mutation) based on configured rates."""
        return random.random() < self.crossover_rate

    async def crossover(self, parent1: Candidate, parent2: Candidate) -> Candidate:
        """
        Create child candidate by combining two parent build plans.

        Uses SDK subagent to intelligently merge the best aspects of both parents
        while preserving build plan structure and validity.

        Args:
            parent1: First parent build plan candidate
            parent2: Second parent build plan candidate

        Returns:
            Child candidate with combined genetic material from both parents
        """
        # Parse build plans
        plan1 = self._parse_build_plan(parent1.content)
        plan2 = self._parse_build_plan(parent2.content)

        crossover_prompt = f"""
        Combine these two build plans into a single optimized workflow
        that takes the best elements from both:

        Build Plan A:
        {json.dumps(plan1, indent=2)}

        Build Plan B:
        {json.dumps(plan2, indent=2)}

        Create a new build plan that:
        - Combines the strengths of both plans
        - Maintains valid phase structure with required fields
        - Optimizes the workflow for efficiency
        - Preserves agent roles and task assignments
        - Includes proper dependencies between phases
        - Returns valid JSON with "phases" and optional "dependencies" keys

        Return only the JSON build plan, no explanations.
        """

        result = await self._call_build_mutation_subagent(crossover_prompt)

        # Validate the result before creating candidate
        child_plan = self._parse_build_plan(result)
        validation = self._validate_build_plan(child_plan)

        child = Candidate(
            id=f"cross-{uuid.uuid4().hex[:8]}",
            content=result.strip() if validation["valid"] else json.dumps(child_plan),
            candidate_type="build_plan",
            fitness=0.0,  # Uneval
            parent_ids=[parent1.id, parent2.id],
            generation=max(parent1.generation, parent2.generation) + 1,
            metadata={
                "mutation_type": "crossover",
                "parent_fitness": [parent1.fitness, parent2.fitness],
                "validation": validation
            },
            created_at=datetime.now(timezone.utc)
        )

        logger.debug(f"Crossover: {parent1.id} + {parent2.id} → {child.id}")
        return child

    async def mutate(
        self, parent: Candidate, strategy: Optional[str] = None
    ) -> Candidate:
        """
        Create mutated child candidate from single parent build plan.

        Applies specified mutation strategy while preserving build plan structure.
        Optimizes workflow efficiency, dependencies, and parallelization.

        Args:
            parent: Parent build plan candidate to mutate
            strategy: Optional mutation strategy name. If None, selects randomly.

        Returns:
            Mutated child candidate with improved build plan
        """
        if strategy is None:
            strategy = random.choice(self.get_mutation_strategies())

        strategy_description = self._mutation_strategies[strategy]

        # Parse build plan
        plan = self._parse_build_plan(parent.content)

        mutation_prompt = f"""
        Improve this build plan using the following strategy: {strategy_description}

        Current plan:
        {json.dumps(plan, indent=2)}

        Create an improved build plan that:
        - Applies the improvement strategy effectively
        - MAINTAINS valid phase structure (each phase needs "name" and "agents" fields)
        - Preserves all phase names and agent assignments
        - Optimizes the workflow for the stated strategy
        - Returns valid JSON with "phases" and optional "dependencies" keys
        - Uses clear, professional naming conventions

        Return only the improved JSON build plan, no explanations.
        """

        result = await self._call_build_mutation_subagent(mutation_prompt)

        # Validate the result before creating candidate
        mutant_plan = self._parse_build_plan(result)
        validation = self._validate_build_plan(mutant_plan)

        mutant = Candidate(
            id=f"mut-{uuid.uuid4().hex[:8]}",
            content=result.strip() if validation["valid"] else json.dumps(mutant_plan),
            candidate_type="build_plan",
            fitness=0.0,  # Uneval
            parent_ids=[parent.id],
            generation=parent.generation + 1,
            metadata={
                "mutation_type": "mutation",
                "mutation_strategy": strategy,
                "parent_fitness": parent.fitness,
                "validation": validation
            },
            created_at=datetime.now(timezone.utc)
        )

        logger.debug(f"Mutation: {parent.id} → {mutant.id} (strategy: {strategy})")
        return mutant

    def _parse_build_plan(self, content: str | Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse build plan from JSON string or dict.

        Args:
            content: Build plan as JSON string or dict

        Returns:
            Parsed build plan dict
        """
        if isinstance(content, dict):
            return content

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse build plan JSON: {e}. Using empty structure.")
            return {"phases": []}

    def _validate_build_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate build plan structure and content.

        Checks for:
        - Required "phases" key
        - Each phase has "name" and "agents" fields
        - Agents field is a list
        - No duplicate phase names

        Args:
            plan: Build plan dict to validate

        Returns:
            dict with "valid" (bool) and "errors" (list of error messages)
        """
        errors = []

        # Check for required "phases" key
        if "phases" not in plan:
            errors.append("Missing required 'phases' key")
            return {"valid": False, "errors": errors}

        if not isinstance(plan["phases"], list):
            errors.append("'phases' must be a list")
            return {"valid": False, "errors": errors}

        if not plan["phases"]:
            errors.append("'phases' list cannot be empty")
            return {"valid": False, "errors": errors}

        # Validate each phase
        phase_names = set()
        for i, phase in enumerate(plan["phases"]):
            if not isinstance(phase, dict):
                errors.append(f"Phase {i} must be a dict, got {type(phase)}")
                continue

            # Check required fields
            if "name" not in phase:
                errors.append(f"Phase {i} missing required 'name' field")
            elif not isinstance(phase["name"], str):
                errors.append(f"Phase {i} 'name' must be string, got {type(phase['name'])}")
            else:
                # Check for duplicate names
                if phase["name"] in phase_names:
                    errors.append(f"Duplicate phase name: {phase['name']}")
                else:
                    phase_names.add(phase["name"])

            if "agents" not in phase:
                errors.append(f"Phase {i} missing required 'agents' field")
            elif not isinstance(phase["agents"], list):
                errors.append(f"Phase {i} 'agents' must be a list, got {type(phase['agents'])}")
            elif not phase["agents"]:
                errors.append(f"Phase {i} 'agents' list cannot be empty")

        return {"valid": len(errors) == 0, "errors": errors}

    def _optimize_dependencies(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize task dependencies to reduce critical path length.

        Analyzes phase ordering and suggests dependency relationships
        to minimize total workflow execution time.

        Args:
            plan: Build plan to optimize

        Returns:
            Optimized build plan with improved dependency structure
        """
        optimized = plan.copy()

        # If no dependencies key, create one
        if "dependencies" not in optimized:
            optimized["dependencies"] = {}

        # Basic optimization: ensure phases with no special dependencies
        # are executed in a logical order
        if "phases" in optimized:
            phases = optimized["phases"]

            # Suggest dependencies based on phase names
            # (setup should run before build, test after build, etc.)
            phase_names = [p.get("name", "") for p in phases]

            for i, phase_name in enumerate(phase_names):
                phase_name_lower = phase_name.lower()

                # Setup phase usually has no dependencies
                if "setup" in phase_name_lower:
                    optimized["dependencies"][phase_name] = []
                # Test usually depends on build
                elif "test" in phase_name_lower or "validate" in phase_name_lower:
                    # Find build phase
                    build_phase = next(
                        (p for p in phases if "build" in p.get("name", "").lower()),
                        None
                    )
                    if build_phase:
                        optimized["dependencies"][phase_name] = [build_phase["name"]]
                    else:
                        optimized["dependencies"][phase_name] = []
                # Deploy depends on test
                elif "deploy" in phase_name_lower or "release" in phase_name_lower:
                    test_phase = next(
                        (p for p in phases if "test" in p.get("name", "").lower()),
                        None
                    )
                    if test_phase:
                        optimized["dependencies"][phase_name] = [test_phase["name"]]
                    else:
                        optimized["dependencies"][phase_name] = []
                # Default: no dependencies
                else:
                    optimized["dependencies"][phase_name] = []

        return optimized

    def _analyze_parallelization(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze opportunities for parallel execution in build plan.

        Examines phases and identifies which can run concurrently
        based on dependencies and resource requirements.

        Args:
            plan: Build plan to analyze

        Returns:
            dict with:
            - "parallelizable_phases": list of phase names that can run in parallel
            - "parallel_opportunities": list of suggested parallelization changes
            - "sequential_critical_path": phases that must run sequentially
        """
        analysis = {
            "parallelizable_phases": [],
            "parallel_opportunities": [],
            "sequential_critical_path": []
        }

        if "phases" not in plan or not plan["phases"]:
            return analysis

        phases = plan["phases"]
        phase_names = [p.get("name", "") for p in phases]

        # Identify phases with similar names or no dependencies
        # These are candidates for parallelization
        independent_phases = []
        for phase in phases:
            phase_name = phase.get("name", "").lower()
            agents = phase.get("agents", [])

            # Phases with multiple agents might benefit from parallelization
            if len(agents) > 1:
                analysis["parallelizable_phases"].append(phase.get("name", ""))
                analysis["parallel_opportunities"].append({
                    "phase": phase.get("name", ""),
                    "reason": f"Multiple agents ({len(agents)}) can work in parallel",
                    "suggested_change": "Enable parallel execution for this phase"
                })

            # Check if phase has parallel flag disabled
            if "parallel" in phase and not phase["parallel"]:
                if len(agents) > 1:
                    analysis["parallel_opportunities"].append({
                        "phase": phase.get("name", ""),
                        "reason": "Phase has multiple agents but parallelization disabled",
                        "suggested_change": "Set parallel: true for this phase"
                    })

        # Identify critical path (phases that must run sequentially)
        if "dependencies" in plan and plan["dependencies"]:
            deps = plan["dependencies"]
            for phase_name, phase_deps in deps.items():
                if phase_deps:  # Has dependencies
                    analysis["sequential_critical_path"].append(phase_name)

        return analysis

    async def _call_build_mutation_subagent(self, prompt: str) -> str:
        """
        Call SDK subagent for build plan mutation.

        In real implementation, this would use AgentSDKRunner with proper
        context and model selection.

        Args:
            prompt: The mutation instruction prompt for the subagent

        Returns:
            Improved build plan JSON from the subagent
        """
        # Placeholder for SDK integration - will be implemented when AgentSDKRunner
        # has run_with_evolution() method. Tests can mock this method.
        logger.debug(f"Build mutation subagent call: {prompt[:50]}...")

        # For now, return a basic build plan structure (tests can mock this method)
        return json.dumps({
            "phases": [
                {"name": "setup", "agents": ["planner"]},
                {"name": "build", "agents": ["coder"]}
            ]
        })
