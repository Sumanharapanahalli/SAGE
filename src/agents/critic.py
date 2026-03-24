"""
SAGE[ai] - Critic Agent
========================
Adversarial reviewer that stress-tests plans and code before they reach
human approval. Implements an actor-critic pattern: Builder produces →
Critic reviews → Builder revises → until score meets threshold or max
iterations reached.

The Critic asks:
  - What failure modes exist? (security, scalability, edge cases, compliance)
  - What's missing? (error handling, tests, monitoring, rollback)
  - What assumptions are wrong? (tech stack mismatch, infra requirements)
  - Confidence score: 0-100 that this will work in production

Critic feedback is stored in vector memory so future plans start better.
"""

import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CriticAgent:
    """
    Adversarial reviewer for build orchestrator artifacts.

    Uses a separate LLM call with a critic-specific system prompt.
    Follows the existing agent pattern: lazy LLM gateway import,
    audit logging, severity parsing.
    """

    def __init__(self):
        self.logger = logging.getLogger("CriticAgent")
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

    # ------------------------------------------------------------------
    # System prompts
    # ------------------------------------------------------------------

    PLAN_REVIEW_PROMPT = (
        "You are a ruthless technical critic. Your job is to find flaws, gaps, "
        "and unrealistic assumptions in implementation plans BEFORE they reach "
        "production. You are not here to be encouraging — you are here to prevent "
        "failures.\n\n"
        "Review the plan and respond with a JSON object:\n"
        "{\n"
        '  "score": <0-100 confidence this plan will work in production>,\n'
        '  "flaws": ["<flaw 1>", "<flaw 2>", ...],\n'
        '  "suggestions": ["<suggestion 1>", ...],\n'
        '  "missing": ["<missing element 1>", ...],\n'
        '  "security_risks": ["<risk 1>", ...],\n'
        '  "summary": "<one paragraph overall assessment>"\n'
        "}\n\n"
        "Be specific. Name concrete failure modes, not vague concerns. "
        "A score above 80 means you'd bet your reputation on this shipping. "
        "A score below 50 means fundamental rework is needed.\n\n"
        "Calibrate your scoring to the scope:\n"
        "- For MVP/prototype builds: 60-70 is acceptable if core functionality is solid\n"
        "- For production systems: require 80+\n"
        "- For regulated domains (medical, automotive, avionics): require 85+ with all compliance artifacts\n"
        "Do NOT penalize an MVP for missing monitoring, CI/CD, or advanced features unless they are in the acceptance criteria."
    )

    CODE_REVIEW_PROMPT = (
        "You are a senior code reviewer focused on production readiness. "
        "Review the code diff against the task description and respond with JSON:\n"
        "{\n"
        '  "score": <0-100 production readiness>,\n'
        '  "issues": ["<issue 1>", ...],\n'
        '  "security_risks": ["<risk 1>", ...],\n'
        '  "suggestions": ["<improvement 1>", ...],\n'
        '  "missing_tests": ["<test case 1>", ...],\n'
        '  "summary": "<one paragraph assessment>"\n'
        "}\n\n"
        "Focus on: correctness, error handling, security vulnerabilities, "
        "missing edge cases, and test coverage gaps. Be specific — cite lines "
        "or patterns, not vague advice.\n\n"
        "Calibrate your scoring to the scope:\n"
        "- For MVP/prototype builds: 60-70 is acceptable if core functionality is solid\n"
        "- For production systems: require 80+\n"
        "- For regulated domains (medical, automotive, avionics): require 85+ with all compliance artifacts\n"
        "Do NOT penalize an MVP for missing monitoring, CI/CD, or advanced features unless they are in the acceptance criteria."
    )

    INTEGRATION_REVIEW_PROMPT = (
        "You are an integration test reviewer. Given test results and a diff, "
        "assess whether the integrated system is production-ready. Respond with JSON:\n"
        "{\n"
        '  "score": <0-100 integration confidence>,\n'
        '  "gaps": ["<gap 1>", ...],\n'
        '  "risks": ["<risk 1>", ...],\n'
        '  "summary": "<one paragraph assessment>"\n'
        "}\n\n"
        "Focus on: test coverage completeness, integration seams, failure modes "
        "under load, data consistency, and deployment risks.\n\n"
        "Calibrate your scoring to the scope:\n"
        "- For MVP/prototype builds: 60-70 is acceptable if core functionality is solid\n"
        "- For production systems: require 80+\n"
        "- For regulated domains (medical, automotive, avionics): require 85+ with all compliance artifacts\n"
        "Do NOT penalize an MVP for missing monitoring, CI/CD, or advanced features unless they are in the acceptance criteria."
    )

    # ------------------------------------------------------------------
    # Review methods
    # ------------------------------------------------------------------

    def review_plan(
        self,
        plan: Any,
        product_description: str,
        context: str = "",
    ) -> Dict[str, Any]:
        """
        Review an implementation plan. Returns score + flaws + suggestions.

        Args:
            plan: The plan to review (list of tasks or dict).
            product_description: What the product is supposed to do.
            context: Optional additional context (prior critic feedback, etc).
        """
        self.logger.info("Reviewing plan for: %s", product_description[:80])

        user_prompt = (
            f"## Product Description\n{product_description}\n\n"
            f"## Plan\n{json.dumps(plan, indent=2, default=str)}\n"
        )
        if context:
            user_prompt += f"\n## Additional Context\n{context}\n"

        result = self._call_llm(user_prompt, self.PLAN_REVIEW_PROMPT, "PLAN_REVIEW")
        return result

    def review_code(
        self,
        code_diff: str,
        task_description: str,
        context: str = "",
    ) -> Dict[str, Any]:
        """
        Review code output from an agent task.

        Args:
            code_diff: The code changes to review.
            task_description: What the task was supposed to accomplish.
            context: Optional additional context.
        """
        self.logger.info("Reviewing code for: %s", task_description[:80])

        user_prompt = (
            f"## Task Description\n{task_description}\n\n"
            f"## Code Diff\n```\n{code_diff[:8000]}\n```\n"
        )
        if context:
            user_prompt += f"\n## Additional Context\n{context}\n"

        return self._call_llm(user_prompt, self.CODE_REVIEW_PROMPT, "CODE_REVIEW")

    def review_integration(
        self,
        test_results: str,
        diff: str,
        context: str = "",
    ) -> Dict[str, Any]:
        """
        Review integration test results and the combined diff.

        Args:
            test_results: Test output (stdout/stderr).
            diff: The combined code diff.
            context: Optional additional context.
        """
        self.logger.info("Reviewing integration results")

        user_prompt = (
            f"## Test Results\n```\n{test_results[:4000]}\n```\n\n"
            f"## Combined Diff\n```\n{diff[:8000]}\n```\n"
        )
        if context:
            user_prompt += f"\n## Additional Context\n{context}\n"

        return self._call_llm(
            user_prompt, self.INTEGRATION_REVIEW_PROMPT, "INTEGRATION_REVIEW"
        )

    # ------------------------------------------------------------------
    # Builder↔Critic loop
    # ------------------------------------------------------------------

    def review_with_loop(
        self,
        review_fn: str,
        artifact: Any,
        description: str,
        revise_fn=None,
        threshold: int = 70,
        max_iterations: int = 3,
    ) -> Dict[str, Any]:
        """
        Run a Builder↔Critic loop: review → revise → re-review until
        score >= threshold or max_iterations reached.

        Args:
            review_fn: Which review method to call ("plan", "code", "integration").
            artifact: The artifact to review (plan, code diff, etc).
            description: Description of what the artifact should do.
            revise_fn: Optional callable(artifact, critic_feedback) → revised_artifact.
                       If None, loop returns after first review.
            threshold: Minimum score to pass (default 70).
            max_iterations: Maximum revision rounds (default 3).

        Returns:
            Dict with final review, revision history, and pass/fail status.
        """
        reviewer = {
            "plan": self.review_plan,
            "code": self.review_code,
            "integration": self.review_integration,
        }.get(review_fn)

        if reviewer is None:
            return {"error": f"Unknown review type: {review_fn}", "score": 0}

        history = []
        current_artifact = artifact

        for iteration in range(1, max_iterations + 1):
            # Build context from prior iterations
            context = ""
            if history:
                context = "Prior critic feedback (address these):\n" + json.dumps(
                    [{"iteration": h["iteration"], "score": h["score"],
                      "flaws": h.get("flaws", []), "issues": h.get("issues", [])}
                     for h in history],
                    indent=2,
                )

            # Review
            if review_fn == "plan":
                review = reviewer(current_artifact, description, context=context)
            elif review_fn == "code":
                review = reviewer(current_artifact, description, context=context)
            else:
                review = reviewer(current_artifact, "", context=context)

            review["iteration"] = iteration
            history.append(review)

            # Fail fast on LLM parse errors — no point iterating
            if review.get("llm_parse_error"):
                self.logger.warning(
                    "Critic loop aborting: LLM parse error on iteration %d", iteration
                )
                break

            score = review.get("score", 0)
            self.logger.info(
                "Critic loop iteration %d/%d — score: %d (threshold: %d)",
                iteration, max_iterations, score, threshold,
            )

            # Pass?
            if score >= threshold:
                break

            # Revise if we have a revision function and more iterations left
            if revise_fn and iteration < max_iterations:
                try:
                    current_artifact = revise_fn(current_artifact, review)
                except Exception as exc:
                    self.logger.warning("Revision function failed: %s", exc)
                    break
            elif not revise_fn:
                break  # No revision function — single review only

        final = history[-1]
        if final.get("llm_parse_error"):
            passed = False
        else:
            passed = final.get("score", 0) >= threshold

        # Store critic patterns in vector memory for compounding
        self._store_feedback(review_fn, description, history, passed)

        return {
            "passed": passed,
            "final_score": final.get("score", 0),
            "final_review": final,
            "history": history,
            "iterations": len(history),
            "threshold": threshold,
        }

    # ------------------------------------------------------------------
    # Multi-LLM review (provider pool voting)
    # ------------------------------------------------------------------

    def review_plan_multi(
        self,
        plan: Any,
        product_description: str,
        context: str = "",
        strategy: str = "voting",
        provider_names: list | None = None,
    ) -> Dict[str, Any]:
        """Review a plan using multiple LLM providers in parallel.

        Falls back to single-provider review_plan when no pool providers
        are registered.
        """
        pool = self.llm.provider_pool
        if not pool.list_providers():
            return self.review_plan(plan, product_description, context)

        user_prompt = (
            f"## Product Description\n{product_description}\n\n"
            f"## Plan\n{json.dumps(plan, indent=2, default=str)}\n"
        )
        if context:
            user_prompt += f"\n## Additional Context\n{context}\n"

        from src.core.llm_gateway import generate_parallel
        result = generate_parallel(
            pool, user_prompt, self.PLAN_REVIEW_PROMPT,
            strategy=strategy, provider_names=provider_names,
        )
        if "error" in result:
            return {"error": result["error"], "score": 0}

        return self._parse_critic_json(result.get("response", ""), result)

    def _parse_critic_json(
        self, response_text: str, meta: dict
    ) -> Dict[str, Any]:
        """Parse JSON from a critic response, attach multi-LLM metadata."""
        import re
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        obj_match = re.search(r'\{[\s\S]*\}', response_text)
        if obj_match:
            response_text = obj_match.group(0)
        try:
            result = json.loads(response_text)
            if not isinstance(result, dict):
                raise ValueError("Expected JSON object")
            result["score"] = int(result.get("score", 0))
        except (json.JSONDecodeError, ValueError):
            result = {
                "score": 0,
                "summary": "Multi-LLM critic parse error — manual review required",
                "flaws": ["Could not parse LLM output"],
                "llm_parse_error": True,
            }
        result["multi_llm"] = {
            "strategy": meta.get("strategy"),
            "provider": meta.get("provider"),
            "elapsed_ms": meta.get("elapsed_ms"),
        }
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_llm(
        self, user_prompt: str, system_prompt: str, action_type: str
    ) -> Dict[str, Any]:
        """Call LLM and parse JSON response. Returns error dict on failure."""
        try:
            response_text = self.llm.generate(
                user_prompt, system_prompt, trace_name=f"critic.{action_type.lower()}"
            )
            # Clean markdown fences
            response_text = response_text.replace("```json", "").replace("```", "").strip()

            # Extract JSON object
            import re
            obj_match = re.search(r'\{[\s\S]*\}', response_text)
            if obj_match:
                response_text = obj_match.group(0)

            result = json.loads(response_text)
            if not isinstance(result, dict):
                raise ValueError("Expected JSON object")

            # Ensure score is an int
            result["score"] = int(result.get("score", 0))

        except json.JSONDecodeError:
            self.logger.error("Critic LLM failed to produce valid JSON")
            result = {
                "score": 0,
                "summary": "Critic output parsing error — manual review required",
                "raw_output": response_text[:500] if 'response_text' in dir() else "",
                "flaws": ["Critic could not parse LLM output"],
                "llm_parse_error": True,
            }
        except Exception as exc:
            self.logger.error("Critic review failed: %s", exc)
            return {"error": str(exc), "score": 0}

        # Audit
        self.audit.log_event(
            actor="CriticAgent",
            action_type=f"CRITIC_{action_type}",
            input_context=user_prompt[:500],
            output_content=json.dumps(result)[:500],
            metadata={"score": result.get("score", 0)},
        )

        return result

    def _store_feedback(
        self,
        review_type: str,
        description: str,
        history: list,
        passed: bool,
    ) -> None:
        """Store critic patterns in vector memory for future context."""
        try:
            from src.memory.vector_store import vector_memory

            final = history[-1] if history else {}
            feedback_text = (
                f"CRITIC REVIEW ({review_type}): {description[:200]}\n"
                f"SCORE: {final.get('score', 0)}/100 | PASSED: {passed}\n"
                f"FLAWS: {json.dumps(final.get('flaws', final.get('issues', [])))}\n"
                f"ITERATIONS: {len(history)}"
            )
            vector_memory.add_feedback(
                feedback_text,
                metadata={
                    "type": "critic_feedback",
                    "review_type": review_type,
                    "score": final.get("score", 0),
                    "passed": passed,
                    "source": "CriticAgent",
                },
            )
        except Exception as exc:
            self.logger.warning("Critic vector store feedback failed (non-fatal): %s", exc)


# Module-level singleton
critic_agent = CriticAgent()
