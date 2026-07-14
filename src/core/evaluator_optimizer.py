"""Evaluator-Optimizer loop — an agentic self-improvement workflow.

The Evaluator-Optimizer pattern (Anthropic, "Building Effective Agents"): one LLM
produces a solution (the OPTIMIZER), a second LLM scores it and returns specific,
actionable feedback (the EVALUATOR); the optimizer revises against that feedback,
and the loop repeats until the evaluator passes the solution (or a max-iteration
cap is hit). Two different models keep each other honest — the optimizer can't
grade its own work.

Roles, per the SAGE house setup:
    OPTIMIZER = Claude  (claude-code / claude)   — generates and revises
    EVALUATOR = Gemini  (gemini CLI)             — scores + gives feedback

This is a sibling of DualLLMRunner (teacher-student); it reuses the same provider
builder. Like everything in SAGE, the loop PRODUCES a result — it does not apply
it. The final solution is returned for the human-in-the-loop approval gate (submit
it to the ProposalStore); nothing is committed automatically.

Hardening (so the loop can't quietly break the HITL guarantee):
  * SANDBOXED OPTIMIZER — the optimizer is usually the agentic claude-code CLI,
    which will WRITE files in its cwd if allowed. When SAGE builds it, we pass
    `--disallowedTools "Write Edit MultiEdit NotebookEdit Bash"` and a throwaway
    cwd, so it can only emit text. The proposal reaches a human before it touches
    any repo. (`sandbox=False` opts out — for trusted, non-agentic optimizers.)
  * SHARPENED RUBRIC — before the loop, the evaluator expands the terse criteria
    into a concrete, checkable rubric, then judges every iteration against it. A
    fixed bar keeps scoring consistent and stops evaluator drift. (`generate_rubric=False` opts out.)
  * ROBUST OPTIMIZE STEP — a wrapping ```code fence``` is stripped from each
    candidate, and an empty/errored optimizer response is retried once.

Use it to make SAGE better: point the optimizer at a SAGE artifact (a prompt, a
config, a code change) with a task + criteria, and let Gemini hold the bar.

    runner = EvaluatorOptimizerRunner({
        "optimizer": {"provider": "claude-code", "model": "claude-sonnet-4-6"},
        "evaluator": {"provider": "gemini",      "model": "gemini-2.5-flash"},
        "max_iterations": 4, "score_threshold": 8.0,
        "criteria": "correctness, clarity, no security gaps, follows SAGE conventions",
    })
    result = runner.run(task="Improve this approval-inbox component ...", context=src)
    # result["final"] -> submit to HITL approval; result["history"] -> audit trail
"""
from __future__ import annotations

import json
import logging
import re
import tempfile
import time
from typing import Callable, Optional

logger = logging.getLogger("EvaluatorOptimizer")

OPTIMIZER_SYSTEM = (
    "You are the OPTIMIZER in an evaluator-optimizer loop. Produce the best possible "
    "solution to the task. When given evaluator feedback, REVISE to address every point "
    "raised — do not restate the task or explain yourself. Output ONLY the solution "
    "(code, config, or text), with no preamble or commentary."
)
EVALUATOR_SYSTEM = (
    "You are the EVALUATOR in an evaluator-optimizer loop. Rigorously judge a candidate "
    "solution against the stated criteria. You do NOT rewrite it — you score and critique. "
    "Be specific and actionable: name exactly what to change. Respond with ONLY a JSON "
    'object: {"score": <number 0-10>, "pass": <true|false>, "feedback": "<specific, '
    'actionable feedback; empty if pass>"}. Pass only when the solution fully meets the criteria.'
)


def _extract_json(text: str) -> Optional[dict]:
    """Pull the first JSON object out of an LLM response (tolerates fences/prose)."""
    if not text:
        return None
    # strip markdown fences
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    blob = fenced.group(1) if fenced else None
    if blob is None:
        # first balanced-looking object
        m = re.search(r"\{.*\}", text, re.DOTALL)
        blob = m.group(0) if m else None
    if not blob:
        return None
    try:
        return json.loads(blob)
    except (ValueError, TypeError):
        return None


class EvaluatorOptimizerRunner:
    """Run an optimizer LLM against an evaluator LLM until the bar is met."""

    def __init__(self, config: dict, build_provider: Optional[Callable[[dict], object]] = None):
        self.config = config or {}
        self.max_iterations = int(self.config.get("max_iterations", 4))
        self.score_threshold = float(self.config.get("score_threshold", 8.0))
        self.criteria = self.config.get("criteria", "correctness, clarity, completeness")
        self.rubric = self.criteria  # may be sharpened in run()
        self.generate_rubric = self.config.get("generate_rubric", True)
        self.sandbox = self.config.get("sandbox", True)
        self.evaluator_retries = int(self.config.get("evaluator_retries", 2))
        self.evaluator_retry_backoff = float(self.config.get("evaluator_retry_backoff", 5.0))
        self._build = build_provider or self._default_build_provider

        # HARDENING — keep the human-in-the-loop guarantee. The optimizer is the
        # agentic claude-code CLI; left alone it WRITES files in its cwd (it created
        # Button.tsx directly). So when we build it ourselves, run it (a) tool-
        # restricted (no Write/Edit/Bash -> a pure text proposal, never touching the
        # repo) and (b) in a throwaway sandbox cwd as defence in depth. The final
        # candidate is returned for the human to apply; nothing auto-applies.
        opt_cfg = dict(self.config.get("optimizer", {}))
        if self.sandbox and "optimizer_provider" not in self.config:
            opt_cfg.setdefault("disallowed_tools", "Write Edit MultiEdit NotebookEdit Bash")
            opt_cfg.setdefault("cwd", tempfile.mkdtemp(prefix="eo_sandbox_"))

        # Allow direct provider injection (tests) via optimizer_provider/evaluator_provider.
        self.optimizer = self.config.get("optimizer_provider") or self._build(opt_cfg)
        self.evaluator = self.config.get("evaluator_provider") or self._build(self.config.get("evaluator", {}))

        # Evaluator pool (game-theory proposal, Step 0(c)): route scoring through
        # an N-provider panel + robust median instead of one judge, so a single
        # overloaded/hallucinating evaluator can't singlehandedly tank or inflate
        # a candidate's score. Defaults to the single `evaluator` above (pool of
        # one) — existing single-evaluator callers are unaffected.
        pool_providers = self.config.get("evaluator_pool_providers")
        if pool_providers:
            self.evaluators = list(pool_providers)
        elif self.config.get("evaluator_pool"):
            self.evaluators = [e for e in
                                (self._build(cfg) for cfg in self.config["evaluator_pool"])
                                if e is not None]
        elif self.evaluator is not None:
            self.evaluators = [self.evaluator]
        else:
            self.evaluators = []

    # -- provider building (mirrors DualLLMRunner._build_provider) ----------
    @staticmethod
    def _default_build_provider(cfg: dict):
        if not cfg:
            return None
        name = cfg.get("provider", "claude-code")
        model = cfg.get("model", "")
        try:
            if name == "gemini":
                from src.core.llm_gateway import GeminiCLIProvider
                return GeminiCLIProvider({"gemini_model": model or "gemini-3.5-flash",
                                          "timeout": cfg.get("timeout", 180)})
            if name == "claude-code":
                from src.core.llm_gateway import ClaudeCodeCLIProvider
                # Default the optimizer timeout high: it is the agentic claude-code
                # CLI generating whole files/large diffs, which legitimately takes
                # minutes (a trivial ask returns in ~10s, a full-file rewrite far more).
                return ClaudeCodeCLIProvider({
                    "claude_model": model or "claude-sonnet-4-6", "timeout": cfg.get("timeout", 600),
                    # forwarded by the hardened __init__ so the optimizer can't write to disk
                    "disallowed_tools": cfg.get("disallowed_tools", ""),
                    "cwd": cfg.get("cwd"),
                })
            if name == "claude":
                from src.core.llm_gateway import ClaudeAPIProvider
                return ClaudeAPIProvider({"claude_model": model or "claude-sonnet-4-6", "timeout": 180})
            if name == "ollama":
                from src.core.llm_gateway import OllamaProvider
                return OllamaProvider({"ollama_model": model or "llama3", "timeout": 120})
        except Exception as e:  # noqa: BLE001
            logger.warning("could not build provider %s: %s", name, e)
        return None

    # -- prompts ------------------------------------------------------------
    def _optimizer_prompt(self, task, context, prev_candidate, feedback, score):
        if prev_candidate is None:
            base = f"TASK:\n{task}\n"
            if context:
                base += f"\nCONTEXT / CURRENT ARTIFACT:\n{context}\n"
            return base + "\nProduce the best solution."
        return (
            f"TASK:\n{task}\n\nYOUR PREVIOUS SOLUTION:\n{prev_candidate}\n\n"
            f"THE EVALUATOR SCORED IT {score}/10 AND SAID:\n{feedback}\n\n"
            "Revise the solution to address every point above. Output only the improved solution."
        )

    def _evaluator_prompt(self, task, candidate):
        return (
            f"TASK:\n{task}\n\nCRITERIA:\n{self.rubric}\n\n"
            f"CANDIDATE SOLUTION:\n{candidate}\n\n"
            "Score 0-10, decide pass/fail against the criteria, and give specific actionable "
            "feedback. Respond with JSON only."
        )

    # -- rubric sharpening (Gemini finding #6: self-sharpening loop) ---------
    def _generate_rubric(self, task: str) -> str:
        """Ask the evaluator to expand the terse criteria into a concrete, checkable
        rubric BEFORE judging. A sharper bar yields more consistent scoring across
        iterations and stops the evaluator from drifting. Falls back to the raw
        criteria if anything goes wrong — never blocks the loop."""
        try:
            prompt = (
                f"TASK THE SOLUTION MUST SATISFY:\n{task}\n\n"
                f"HIGH-LEVEL CRITERIA:\n{self.criteria}\n\n"
                "Expand these into a concrete scoring rubric: a short numbered list of "
                "specific, checkable requirements a solution must meet, each phrased so it "
                "can be objectively verified. Output ONLY the rubric as plain text."
            )
            lead_evaluator = self.evaluators[0] if self.evaluators else self.evaluator
            rubric = (lead_evaluator.generate(prompt, "You are a meticulous test-rubric author. "
                                              "Output only the rubric, no preamble.") or "").strip()
            rubric = self._strip_fences(rubric)
            if rubric and len(rubric) > 20:
                logger.info("rubric sharpened: %d chars", len(rubric))
                return f"{self.criteria}\n\nDETAILED RUBRIC:\n{rubric}"
        except Exception as e:  # noqa: BLE001
            logger.warning("rubric generation failed, using raw criteria: %s", e)
        return self.criteria

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Drop a single wrapping ```lang ... ``` fence so the candidate is raw code,
        not a Markdown block (the evaluator and any downstream apply step want the
        bare artifact)."""
        if not text:
            return text
        m = re.match(r"^\s*```[a-zA-Z0-9_-]*\n(.*)\n```\s*$", text, re.DOTALL)
        return m.group(1) if m else text

    @staticmethod
    def _parse_evaluation(raw: str) -> dict:
        """Parse an evaluator JSON response into {parse_ok, score, passed, feedback}.

        Crucially distinguishes a GENUINE low score (valid JSON with a numeric score,
        even 0) from an UNPARSEABLE response (prose, empty, or a swallowed CLI error). The
        latter must never masquerade as a real 0.0 — that misread is what produced this
        session's flat-0.0 runs (the evaluator was overloaded/unavailable, not harsh)."""
        parsed = _extract_json(raw)
        if not isinstance(parsed, dict) or "score" not in parsed:
            return {"parse_ok": False, "score": 0.0, "passed": False,
                    "feedback": "(evaluator output unparseable — no JSON score)"}
        try:
            score = float(parsed.get("score", 0))
        except (ValueError, TypeError):
            return {"parse_ok": False, "score": 0.0, "passed": False,
                    "feedback": "(evaluator score was non-numeric)"}
        return {"parse_ok": True, "score": score,
                "passed": bool(parsed.get("pass", False)),
                "feedback": str(parsed.get("feedback", "") or "")}

    @staticmethod
    def _weighted_median(values: list) -> float:
        """Weighted median of equally-weighted floats — same robustness property
        as CriticAgent._robust_aggregate (breakdown point ~50%, unlike a mean's
        0), reimplemented locally to preserve this loop's 0-10 float precision
        (that method rounds to int, tuned for multi_critic_review's 0-100 scale)."""
        s = sorted(values)
        n = len(s)
        mid = n // 2
        if n % 2 == 1:
            return s[mid]
        return (s[mid - 1] + s[mid]) / 2.0

    def _oversize_guard(self, prompt: str) -> Optional[dict]:
        """Refuse an evaluator prompt that is too large to be judged, instead of hanging.

        CLI evaluator latency is super-linear in prompt size (measured for Gemini on this
        repo: 5KB->7s, 20KB->17s, 50KB->142s). A task scoped as "add response models to
        EVERY endpoint" of a 232KB file produced 34KB candidates, whose evaluator prompt
        blew a 900s timeout on every attempt AND every retry — the run burned five hours and
        returned nothing.

        Timing out is not just slow, it is *dishonest*: it lands as a phantom 0.0 that reads
        as "the optimizer produced garbage" when in truth the judge never ran. Fail fast and
        say WHY, so the answer is "re-scope the task", not "the model is bad".
        """
        limit = int(self.config.get("max_evaluator_prompt_chars", 40_000))
        if limit <= 0 or len(prompt) <= limit:
            return None
        msg = (
            f"candidate is too large to evaluate: the evaluator prompt is "
            f"{len(prompt) // 1024}KB (limit {limit // 1024}KB). CLI evaluators scale "
            f"super-linearly with prompt size and will time out rather than answer. "
            f"Scope the task to a smaller unit of work, or raise "
            f"max_evaluator_prompt_chars if your evaluator can genuinely take it."
        )
        logger.error("%s", msg)
        return {"parse_ok": False, "score": 0.0, "passed": False,
                "oversize": True, "feedback": f"(NOT SCORED — {msg})"}

    def _evaluate_candidate(self, task: str, candidate: str) -> dict:
        """Evaluate a candidate against self.evaluators. With one evaluator
        (the default), behavior is identical to a single-judge call. With a
        pool of several, every provider is queried independently and scores
        are aggregated via robust median — Step 0(c) of the game-theory
        proposal: one hallucinating/overloaded evaluator can no longer
        singlehandedly tank or inflate a candidate's score."""
        prompt = self._evaluator_prompt(task, candidate)

        # Check BEFORE calling anyone, and before the retry loop: retrying a prompt that is
        # too big to answer just multiplies the wasted wall-clock (3 iterations x 3 attempts
        # x a 900s timeout = the five hours this run threw away).
        oversize = self._oversize_guard(prompt)
        if oversize is not None:
            return oversize

        if len(self.evaluators) <= 1:
            evaluator = self.evaluators[0] if self.evaluators else None
            if evaluator is None:
                return self._parse_evaluation("")
            ev = self._parse_evaluation(evaluator.generate(prompt, EVALUATOR_SYSTEM))
            # A CLI evaluator times out or returns prose under transient overload; that
            # is indistinguishable at this layer from a genuinely bad candidate unless we
            # retry. Without this, one overloaded-provider window sinks a whole run to a
            # phantom 0.0 (observed: 3/3 iterations of a task lost to 300s timeouts) —
            # the failure that motivated dropping the cross-vendor judge entirely.
            for attempt in range(self.evaluator_retries):
                if ev["parse_ok"]:
                    break
                logger.warning("evaluator unparseable/timed out — retry %d/%d",
                               attempt + 1, self.evaluator_retries)
                time.sleep(self.evaluator_retry_backoff * (2 ** attempt))
                ev = self._parse_evaluation(evaluator.generate(prompt, EVALUATOR_SYSTEM))
            return ev

        scores = []
        feedbacks = []
        for provider in self.evaluators:
            raw = provider.generate(prompt, EVALUATOR_SYSTEM)
            ev = self._parse_evaluation(raw)
            if ev["parse_ok"]:
                scores.append(ev["score"])
                if ev["feedback"]:
                    feedbacks.append(ev["feedback"])

        if not scores:
            return {"parse_ok": False, "score": 0.0, "passed": False,
                    "feedback": "(every evaluator-pool provider returned unparseable output)"}

        median_score = self._weighted_median(scores)
        return {
            "parse_ok": True,
            "score": median_score,
            "passed": median_score >= self.score_threshold,
            "feedback": " | ".join(feedbacks),
        }

    # -- the loop -----------------------------------------------------------
    def run(self, task: str, context: str = "") -> dict:
        if self.optimizer is None or not self.evaluators:
            return {"error": "optimizer and at least one evaluator provider must be available",
                    "converged": False, "iterations": 0, "history": []}

        # sharpen the bar once, up front, so every iteration is judged the same way
        self.rubric = self._generate_rubric(task) if self.generate_rubric else self.criteria

        history = []
        candidate = None
        feedback = ""
        score = 0.0

        for i in range(1, self.max_iterations + 1):
            # OPTIMIZE (Claude) — strip any wrapping fence; retry once if empty/errored
            opt_prompt = self._optimizer_prompt(task, context, candidate, feedback, score)
            candidate = self._strip_fences((self.optimizer.generate(opt_prompt, OPTIMIZER_SYSTEM) or "").strip())
            if not candidate or candidate.lower().startswith("error"):
                logger.warning("iter %d: optimizer returned empty/error, retrying once", i)
                candidate = self._strip_fences((self.optimizer.generate(opt_prompt, OPTIMIZER_SYSTEM) or "").strip())

            # EVALUATE — parse robustly: an unparseable response is FLAGGED, not a silent 0.0.
            # With a pool, scores are aggregated via robust median (Step 0(c)).
            ev = self._evaluate_candidate(task, candidate)

            # An oversize candidate will not get smaller by iterating — the optimizer is
            # doing exactly what the task asked. Stop now and tell the human to re-scope,
            # rather than grinding through every iteration to arrive at a phantom 0.0.
            if ev.get("oversize"):
                history.append({"iteration": i, "candidate": candidate, "score": 0.0,
                                "passed": False, "feedback": ev["feedback"], "parse_ok": False})
                return {"converged": False, "iterations": i, "final": candidate,
                        "score": 0.0, "oversize": True, "history": history,
                        "error": ev["feedback"],
                        "note": "The candidate is too large for the evaluator to judge. This "
                                "is NOT a quality score — the judge never ran. Re-scope the "
                                "task to a smaller unit of work."}

            score = ev["score"]
            passed = ev["parse_ok"] and (ev["passed"] or score >= self.score_threshold)
            feedback = ev["feedback"]

            history.append({"iteration": i, "candidate": candidate, "score": score,
                            "passed": passed, "feedback": feedback, "parse_ok": ev["parse_ok"]})
            logger.info("iter %d/%d: score=%.1f passed=%s", i, self.max_iterations, score, passed)

            if passed:
                return {"converged": True, "iterations": i, "final": candidate,
                        "score": score, "history": history,
                        "note": "Evaluator passed the solution. Submit `final` to the HITL approval gate."}

        # no convergence — return the best-scoring candidate among PARSEABLE evaluations.
        # A parse-failure iteration carries a swallowed 0.0; it must not be mistaken for a
        # genuine low score nor win the best-candidate selection.
        parsed_iters = [h for h in history if h.get("parse_ok")]
        if parsed_iters:
            best = max(parsed_iters, key=lambda h: h["score"])
            return {"converged": False, "iterations": len(history), "final": best["candidate"],
                    "score": best["score"], "history": history,
                    "note": "Hit max_iterations without a pass; returning the best-scoring candidate. "
                            "Submit `final` to the HITL approval gate (a human decides)."}
        # Every iteration's evaluation was unparseable — surface that; do NOT report a genuine 0.0.
        return {"converged": False, "iterations": len(history),
                "final": (history[-1]["candidate"] if history else candidate),
                "score": 0.0, "evaluator_unparseable": True, "history": history,
                "note": "Evaluator output was unparseable on every iteration — the score is NOT a "
                        "genuine 0.0. Check the evaluator model/provider before trusting this result."}


def run_loop(task: str, context: str = "", **config) -> dict:
    """One-call convenience: run an evaluator-optimizer loop with config kwargs."""
    return EvaluatorOptimizerRunner(config).run(task, context)


def _main(argv=None):
    """CLI: python -m src.core.evaluator_optimizer --task "..." [--context-file f]"""
    import argparse
    ap = argparse.ArgumentParser(description="Evaluator-Optimizer loop (Claude optimizes, Gemini evaluates)")
    ap.add_argument("--task", required=True, help="what to optimize")
    ap.add_argument("--context-file", help="file whose contents are the current artifact/context")
    ap.add_argument("--criteria", default="correctness, clarity, completeness, follows SAGE conventions")
    ap.add_argument("--optimizer", default="claude-code", help="optimizer provider (claude-code|claude|ollama)")
    ap.add_argument("--evaluator", default="gemini", help="evaluator provider (gemini|...)")
    ap.add_argument("--max-iterations", type=int, default=4)
    ap.add_argument("--threshold", type=float, default=8.0)
    ap.add_argument("--out", help="write the final solution to this file")
    ap.add_argument("--no-rubric", action="store_true",
                    help="skip the up-front evaluator rubric-sharpening pass")
    ap.add_argument("--no-sandbox", action="store_true",
                    help="DANGER: let the optimizer use file-writing tools in the cwd "
                         "(default: tool-restricted, throwaway cwd — pure text proposer)")
    args = ap.parse_args(argv)

    context = ""
    if args.context_file:
        with open(args.context_file, encoding="utf-8") as f:
            context = f.read()

    runner = EvaluatorOptimizerRunner({
        "optimizer": {"provider": args.optimizer},
        "evaluator": {"provider": args.evaluator},
        "criteria": args.criteria,
        "max_iterations": args.max_iterations,
        "score_threshold": args.threshold,
        "generate_rubric": not args.no_rubric,
        "sandbox": not args.no_sandbox,
    })
    result = runner.run(args.task, context)

    print(f"\n=== Evaluator-Optimizer: converged={result.get('converged')} "
          f"iterations={result.get('iterations')} score={result.get('score')} ===")
    for h in result.get("history", []):
        print(f"  iter {h['iteration']}: score={h['score']} passed={h['passed']}  {h['feedback'][:90]}")
    print(f"\n{result.get('note', '')}")
    if "error" in result:
        print("ERROR:", result["error"])
        return 1
    if args.out and result.get("final"):
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(result["final"])
        print(f"final solution -> {args.out}  (submit to the HITL approval gate; nothing was applied)")
    else:
        print("\n--- FINAL SOLUTION ---\n" + (result.get("final") or ""))
    return 0


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(_main())
