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
import os
import threading
import time
import uuid
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Path for persisted critic prompts (editable by founder)
_CRITIC_PROMPTS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "critic_prompts.json",
)


class CriticAgent:
    """
    Adversarial reviewer for build orchestrator artifacts.

    Uses a separate LLM call with a critic-specific system prompt.
    Follows the existing agent pattern: lazy LLM gateway import,
    audit logging, severity parsing.

    Supports:
      - N LLM providers reviewing in parallel
      - Optional human expert critic (async, queued for review)
      - Editable system prompts (founder can tune what critics look for)
    """

    def __init__(self):
        self.logger = logging.getLogger("CriticAgent")
        self._llm_gateway = None
        self._audit_logger = None
        self._custom_prompts: Dict[str, str] = {}
        self._pending_human_reviews: Dict[str, dict] = {}
        self._completed_human_reviews: Dict[str, dict] = {}
        self._human_review_lock = threading.Lock()
        self._load_custom_prompts()

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
    # Custom prompt loading (editable by founder)
    # ------------------------------------------------------------------

    def _load_custom_prompts(self):
        """Load founder-customized critic prompts from config/critic_prompts.json."""
        try:
            if os.path.isfile(_CRITIC_PROMPTS_PATH):
                with open(_CRITIC_PROMPTS_PATH) as f:
                    self._custom_prompts = json.load(f)
                self.logger.info("Loaded custom critic prompts from %s", _CRITIC_PROMPTS_PATH)
        except Exception as exc:
            self.logger.debug("No custom critic prompts: %s", exc)

    def _get_prompt(self, key: str) -> str:
        """Get a system prompt — custom override takes priority over default."""
        if key in self._custom_prompts:
            return self._custom_prompts[key]
        return getattr(self, key, "")

    def get_all_prompts(self) -> Dict[str, str]:
        """Return all critic prompts (defaults + any custom overrides)."""
        defaults = {
            "PLAN_REVIEW_PROMPT": self.PLAN_REVIEW_PROMPT,
            "CODE_REVIEW_PROMPT": self.CODE_REVIEW_PROMPT,
            "INTEGRATION_REVIEW_PROMPT": self.INTEGRATION_REVIEW_PROMPT,
        }
        # Layer custom overrides on top
        merged = {**defaults, **self._custom_prompts}
        return merged

    def update_prompt(self, key: str, prompt: str) -> Dict[str, str]:
        """
        Update a critic system prompt. Persists to config/critic_prompts.json.

        Args:
            key: Prompt name (e.g., "PLAN_REVIEW_PROMPT", "CODE_REVIEW_PROMPT",
                 or any custom key like "MEDICAL_REVIEW_PROMPT").
            prompt: The new system prompt text.

        Returns:
            Updated prompts dict.
        """
        self._custom_prompts[key] = prompt
        # Persist to disk
        try:
            os.makedirs(os.path.dirname(_CRITIC_PROMPTS_PATH), exist_ok=True)
            with open(_CRITIC_PROMPTS_PATH, "w") as f:
                json.dump(self._custom_prompts, f, indent=2)
            self.logger.info("Saved custom critic prompt: %s (%d chars)", key, len(prompt))
        except Exception as exc:
            self.logger.error("Failed to persist critic prompt: %s", exc)

        self.audit.log_event(
            actor="Founder",
            action_type="CRITIC_PROMPT_UPDATE",
            input_context=key,
            output_content=prompt[:200],
            metadata={"prompt_key": key, "length": len(prompt)},
        )
        return self.get_all_prompts()

    def delete_prompt(self, key: str) -> Dict[str, str]:
        """Remove a custom prompt override (reverts to default)."""
        self._custom_prompts.pop(key, None)
        try:
            with open(_CRITIC_PROMPTS_PATH, "w") as f:
                json.dump(self._custom_prompts, f, indent=2)
        except Exception:
            pass
        return self.get_all_prompts()

    # ------------------------------------------------------------------
    # Human expert critic
    # ------------------------------------------------------------------

    def request_human_review(
        self,
        review_type: str,
        artifact: Any,
        description: str,
        context: str = "",
    ) -> Dict[str, Any]:
        """
        Queue an artifact for human expert review.

        Returns a review_id that can be used to submit the review later.
        The human expert sees the same artifact and context as LLM critics.
        """
        review_id = str(uuid.uuid4())
        with self._human_review_lock:
            self._pending_human_reviews[review_id] = {
                "review_id": review_id,
                "review_type": review_type,
                "artifact": str(artifact)[:10000],
                "description": description,
                "context": context,
                "requested_at": time.time(),
                "status": "pending",
            }
        self.logger.info("Human review requested: %s (%s)", review_id[:8], review_type)
        return {"review_id": review_id, "status": "pending"}

    def submit_human_review(
        self,
        review_id: str,
        score: int,
        feedback: str,
        flaws: list[str] | None = None,
        suggestions: list[str] | None = None,
    ) -> Dict[str, Any]:
        """
        Submit a human expert review for a pending review request.

        Args:
            review_id: The ID from request_human_review.
            score: 0-100 expert assessment.
            feedback: Free-form expert feedback.
            flaws: List of identified flaws.
            suggestions: List of improvement suggestions.
        """
        with self._human_review_lock:
            pending = self._pending_human_reviews.pop(review_id, None)
            if not pending:
                return {"error": f"Review '{review_id}' not found or already submitted"}

            review = {
                "review_id": review_id,
                "review_type": pending["review_type"],
                "score": max(0, min(100, score)),
                "feedback": feedback,
                "flaws": flaws or [],
                "suggestions": suggestions or [],
                "submitted_at": time.time(),
                "requested_at": pending["requested_at"],
                "turnaround_s": round(time.time() - pending["requested_at"], 1),
            }
            self._completed_human_reviews[review_id] = review

        self.audit.log_event(
            actor="HumanExpert",
            action_type="HUMAN_CRITIC_REVIEW",
            input_context=pending["description"][:300],
            output_content=json.dumps({"score": score, "flaws": flaws or []}),
            metadata={"score": score, "review_type": pending["review_type"]},
        )

        self.logger.info(
            "Human review submitted: %s score=%d turnaround=%.0fs",
            review_id[:8], score, review["turnaround_s"],
        )
        return review

    def get_pending_human_reviews(self) -> list[dict]:
        """List all pending human expert reviews."""
        with self._human_review_lock:
            return list(self._pending_human_reviews.values())

    def get_human_review(self, review_id: str) -> dict | None:
        """Get a completed human review by ID."""
        return self._completed_human_reviews.get(review_id)

    # ------------------------------------------------------------------
    # System prompts (defaults — overridable via update_prompt)
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

        result = self._call_llm(user_prompt, self._get_prompt("PLAN_REVIEW_PROMPT"), "PLAN_REVIEW")
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

        return self._call_llm(user_prompt, self._get_prompt("CODE_REVIEW_PROMPT"), "CODE_REVIEW")

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
            user_prompt, self._get_prompt("INTEGRATION_REVIEW_PROMPT"), "INTEGRATION_REVIEW"
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

    def review_code_multi(
        self,
        code_diff: str,
        task_description: str,
        context: str = "",
        strategy: str = "quality",
        provider_names: list | None = None,
    ) -> Dict[str, Any]:
        """Review code using multiple LLM providers in parallel.

        Falls back to single-provider review_code when no pool providers
        are registered.
        """
        pool = self.llm.provider_pool
        if not pool.list_providers():
            return self.review_code(code_diff, task_description, context)

        user_prompt = (
            f"## Task Description\n{task_description}\n\n"
            f"## Code Diff\n```\n{code_diff[:8000]}\n```\n"
        )
        if context:
            user_prompt += f"\n## Additional Context\n{context}\n"

        from src.core.llm_gateway import generate_parallel
        result = generate_parallel(
            pool, user_prompt, self.CODE_REVIEW_PROMPT,
            strategy=strategy, provider_names=provider_names,
        )
        if "error" in result:
            return {"error": result["error"], "score": 0}
        return self._parse_critic_json(result.get("response", ""), result)

    def review_integration_multi(
        self,
        test_results: str,
        diff: str,
        context: str = "",
        strategy: str = "quality",
        provider_names: list | None = None,
    ) -> Dict[str, Any]:
        """Review integration using multiple LLM providers in parallel.

        Falls back to single-provider review_integration when no pool providers
        are registered.
        """
        pool = self.llm.provider_pool
        if not pool.list_providers():
            return self.review_integration(test_results, diff, context)

        user_prompt = (
            f"## Test Results\n```\n{test_results[:4000]}\n```\n\n"
            f"## Combined Diff\n```\n{diff[:8000]}\n```\n"
        )
        if context:
            user_prompt += f"\n## Additional Context\n{context}\n"

        from src.core.llm_gateway import generate_parallel
        result = generate_parallel(
            pool, user_prompt, self.INTEGRATION_REVIEW_PROMPT,
            strategy=strategy, provider_names=provider_names,
        )
        if "error" in result:
            return {"error": result["error"], "score": 0}
        return self._parse_critic_json(result.get("response", ""), result)

    # ------------------------------------------------------------------
    # N-critic review (any number of providers)
    # ------------------------------------------------------------------

    def multi_critic_review(
        self,
        review_type: str,
        artifact: Any,
        description: str,
        context: str = "",
        provider_names: list | None = None,
    ) -> Dict[str, Any]:
        """
        Run N-provider critic review for diverse quality assessment.

        Uses all registered providers in the ProviderPool (Gemini, OpenAI,
        Ollama, Mistral, etc.) plus the primary provider. Each reviews
        independently, scores are aggregated.

        Aggregation:
          - Final score = weighted mean (primary gets 1.5x weight)
          - All flaws/issues merged and deduplicated
          - Per-provider reviews attached for transparency
          - Disagreements (>20pt gap from mean) flagged for human attention

        Args:
            review_type: "plan", "code", or "integration"
            artifact: The artifact to review.
            description: What the artifact should accomplish.
            context: Additional context for the review.
            provider_names: Optional list of specific providers to use.
                           If None, uses all registered + primary.

        Returns:
            Dict with aggregated score, individual reviews, disagreements.
        """
        import concurrent.futures

        self.logger.info("Multi-critic review (%s) starting", review_type)

        # 1. Always include primary provider
        reviews: dict[str, dict] = {}

        # Build the user prompt once
        system_prompt, user_prompt = self._build_review_prompt(
            review_type, artifact, description, context
        )

        # 2. Gather which providers to call
        pool = self.llm.provider_pool
        pool_names = provider_names or pool.list_providers()

        # Ensure Gemini is auto-discovered if not already registered
        if "gemini" not in pool_names:
            self._ensure_gemini_registered(pool)
            if pool.get("gemini"):
                pool_names = pool.list_providers() if not provider_names else provider_names

        # 3. Call primary + all pool providers in parallel
        def _call_primary():
            return ("primary", self._get_single_review(review_type, artifact, description, context))

        def _call_pool_provider(name):
            provider = pool.get(name)
            if not provider:
                return (name, {"score": 0, "error": f"Provider '{name}' not found"})
            try:
                resp = provider.generate(user_prompt, system_prompt)
                return (name, self._parse_critic_json(resp, {"provider": name}))
            except Exception as exc:
                self.logger.warning("Critic provider '%s' failed: %s", name, exc)
                return (name, {"score": 0, "error": str(exc)})

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(pool_names) + 1) as executor:
            futures = [executor.submit(_call_primary)]
            for name in pool_names:
                futures.append(executor.submit(_call_pool_provider, name))

            for future in concurrent.futures.as_completed(futures):
                name, review = future.result()
                reviews[name] = review

        # 3.5 Include completed human expert reviews if available
        with self._human_review_lock:
            for rid, hr in self._completed_human_reviews.items():
                if hr.get("review_type") == review_type:
                    reviews[f"human_expert_{rid[:8]}"] = {
                        "score": hr["score"],
                        "flaws": hr.get("flaws", []),
                        "suggestions": hr.get("suggestions", []),
                        "summary": hr.get("feedback", ""),
                        "source": "human_expert",
                    }

        # 4. Aggregate scores (primary 1.5x, human_expert 2.0x weight)
        scored = {n: r.get("score", 0) for n, r in reviews.items() if "error" not in r}
        if not scored:
            scored = {"primary": reviews.get("primary", {}).get("score", 0)}

        weight_sum = 0
        weighted_total = 0
        for name, score in scored.items():
            if "human_expert" in name:
                w = 2.0  # Human expert opinion weighted highest
            elif name == "primary":
                w = 1.5
            else:
                w = 1.0
            weighted_total += score * w
            weight_sum += w
        final_score = int(weighted_total / max(weight_sum, 1))

        # 5. Merge all flaws
        all_flaws = []
        seen_flaws = set()
        for r in reviews.values():
            for flaw in r.get("flaws", r.get("issues", r.get("gaps", []))):
                if flaw not in seen_flaws:
                    all_flaws.append(flaw)
                    seen_flaws.add(flaw)

        # 6. Detect disagreements (>20pt from mean)
        mean_score = sum(scored.values()) / max(len(scored), 1)
        disagreements = []
        for name, score in scored.items():
            gap = abs(score - mean_score)
            if gap > 20:
                disagreements.append(
                    f"{name}={score} vs mean={int(mean_score)} (gap={int(gap)})"
                )

        # 7. Merge suggestions, missing, security_risks
        def _merge_key(key):
            merged = []
            seen = set()
            for r in reviews.values():
                for item in r.get(key, []):
                    if item not in seen:
                        merged.append(item)
                        seen.add(item)
            return merged

        provider_scores = {n: r.get("score", 0) for n, r in reviews.items()}
        summary_parts = ", ".join(f"{n}={s}" for n, s in provider_scores.items())

        result = {
            "score": final_score,
            "provider_scores": provider_scores,
            "providers_used": list(reviews.keys()),
            "flaws": all_flaws,
            "suggestions": _merge_key("suggestions"),
            "missing": _merge_key("missing"),
            "security_risks": _merge_key("security_risks"),
            "summary": (
                f"MULTI CRITIC ({review_type}, {len(reviews)} providers): "
                f"{summary_parts} → Final={final_score}/100. "
                f"{len(all_flaws)} flaws, {len(disagreements)} disagreements."
            ),
            "disagreements": disagreements,
            "reviews": reviews,
            "multi_critic": True,
        }

        # Audit
        self.audit.log_event(
            actor="CriticAgent",
            action_type=f"MULTI_CRITIC_{review_type.upper()}",
            input_context=description[:300],
            output_content=json.dumps({
                "final_score": final_score,
                "provider_scores": provider_scores,
                "disagreements": len(disagreements),
            }),
            metadata={"score": final_score, **provider_scores},
        )

        return result

    # Backward compat alias
    dual_critic_review = multi_critic_review

    def _get_single_review(
        self, review_type: str, artifact: Any, description: str, context: str
    ) -> Dict[str, Any]:
        """Get a review from the current (primary) LLM provider."""
        try:
            if review_type == "plan":
                return self.review_plan(artifact, description, context)
            elif review_type == "code":
                return self.review_code(artifact, description, context)
            elif review_type == "integration":
                return self.review_integration(artifact, description, context)
            else:
                return {"error": f"Unknown review type: {review_type}", "score": 0}
        except Exception as exc:
            self.logger.error("Primary critic failed: %s", exc)
            return {"error": str(exc), "score": 0}

    def _build_review_prompt(
        self, review_type: str, artifact: Any, description: str, context: str
    ) -> tuple[str, str]:
        """Build (system_prompt, user_prompt) for a review type."""
        system_prompt = {
            "plan": self.PLAN_REVIEW_PROMPT,
            "code": self.CODE_REVIEW_PROMPT,
            "integration": self.INTEGRATION_REVIEW_PROMPT,
        }.get(review_type, self.PLAN_REVIEW_PROMPT)

        if review_type == "plan":
            user_prompt = (
                f"## Product Description\n{description}\n\n"
                f"## Plan\n{json.dumps(artifact, indent=2, default=str)}\n"
            )
        elif review_type == "code":
            user_prompt = (
                f"## Task Description\n{description}\n\n"
                f"## Code Diff\n```\n{str(artifact)[:8000]}\n```\n"
            )
        else:
            user_prompt = (
                f"## Test Results\n```\n{str(artifact)[:4000]}\n```\n\n"
                f"## Combined Diff\n```\n{description[:8000]}\n```\n"
            )
        if context:
            user_prompt += f"\n## Additional Context\n{context}\n"
        return system_prompt, user_prompt

    def _ensure_gemini_registered(self, pool) -> None:
        """Auto-discover and register Gemini if available."""
        if pool.get("gemini"):
            return
        try:
            from src.core.llm_gateway import GeminiCLIProvider, _load_config
            cfg = _load_config()
            llm_cfg = cfg.get("llm", {})
            gemini_timeout = llm_cfg.get("gemini_timeout", llm_cfg.get("timeout", 30))
            temp = GeminiCLIProvider({"gemini_model": "gemini-2.5-flash", "gemini_timeout": gemini_timeout})
            if temp.gemini_path:
                pool.register("gemini", temp)
                self.logger.info("Auto-registered Gemini as critic provider")
        except Exception as exc:
            self.logger.debug("Gemini auto-register failed: %s", exc)

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
