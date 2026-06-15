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
        # provider builder is injectable so tests can pass mocks; defaults to SAGE's.
        self._build = build_provider or self._default_build_provider
        # Allow direct provider injection (tests) via optimizer_provider/evaluator_provider.
        self.optimizer = self.config.get("optimizer_provider") or self._build(self.config.get("optimizer", {}))
        self.evaluator = self.config.get("evaluator_provider") or self._build(self.config.get("evaluator", {}))

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
                return GeminiCLIProvider({"gemini_model": model or "gemini-3.5-flash", "timeout": 180})
            if name == "claude-code":
                from src.core.llm_gateway import ClaudeCodeCLIProvider
                return ClaudeCodeCLIProvider({"claude_model": model or "claude-sonnet-4-6", "timeout": 180})
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
            f"TASK:\n{task}\n\nCRITERIA:\n{self.criteria}\n\n"
            f"CANDIDATE SOLUTION:\n{candidate}\n\n"
            "Score 0-10, decide pass/fail against the criteria, and give specific actionable "
            "feedback. Respond with JSON only."
        )

    # -- the loop -----------------------------------------------------------
    def run(self, task: str, context: str = "") -> dict:
        if self.optimizer is None or self.evaluator is None:
            return {"error": "optimizer and evaluator providers must both be available",
                    "converged": False, "iterations": 0, "history": []}

        history = []
        candidate = None
        feedback = ""
        score = 0.0

        for i in range(1, self.max_iterations + 1):
            # OPTIMIZE (Claude)
            opt_prompt = self._optimizer_prompt(task, context, candidate, feedback, score)
            candidate = (self.optimizer.generate(opt_prompt, OPTIMIZER_SYSTEM) or "").strip()

            # EVALUATE (Gemini)
            eval_raw = self.evaluator.generate(self._evaluator_prompt(task, candidate), EVALUATOR_SYSTEM)
            parsed = _extract_json(eval_raw) or {}
            try:
                score = float(parsed.get("score", 0))
            except (ValueError, TypeError):
                score = 0.0
            passed = bool(parsed.get("pass", False)) or score >= self.score_threshold
            feedback = str(parsed.get("feedback", "") or ("(no parseable feedback)" if not parsed else ""))

            history.append({"iteration": i, "candidate": candidate, "score": score,
                            "passed": passed, "feedback": feedback})
            logger.info("iter %d/%d: score=%.1f passed=%s", i, self.max_iterations, score, passed)

            if passed:
                return {"converged": True, "iterations": i, "final": candidate,
                        "score": score, "history": history,
                        "note": "Evaluator passed the solution. Submit `final` to the HITL approval gate."}

        # no convergence — return the best-scoring candidate
        best = max(history, key=lambda h: h["score"]) if history else {"candidate": candidate, "score": score}
        return {"converged": False, "iterations": len(history), "final": best["candidate"],
                "score": best["score"], "history": history,
                "note": "Hit max_iterations without a pass; returning the best-scoring candidate. "
                        "Submit `final` to the HITL approval gate (a human decides)."}


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
