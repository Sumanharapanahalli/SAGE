# Evaluator-Optimizer Loop

An agentic self-improvement workflow for making SAGE (or any artifact) better:

```
OPTIMIZER (Claude) ──produces/revises──▶ candidate
        ▲                                   │
        │ feedback + score                  ▼
        └──────────── EVALUATOR (Gemini) ◀──┘  scores 0-10, says pass/fail + why
                          (loop until pass, or max_iterations)
```

Two different models keep each other honest — the optimizer can't grade its own
work. This is the Anthropic "evaluator-optimizer" pattern; in SAGE the house
roles are **Claude = optimizer**, **Gemini = evaluator** (both keyless via their
CLIs). It's a sibling of the teacher-student `DualLLMRunner` and reuses the same
provider builder.

**Human-in-the-loop is preserved.** The loop *produces* a result; it never applies
it. The final solution is returned for the approval gate — submit it to the
`ProposalStore` so a human signs off. Nothing is committed automatically.

## Hardening

The optimizer is usually the agentic `claude-code` CLI, which will **write files**
if you let it (in an early run it created `Button.tsx` directly in the repo —
bypassing the human gate). The loop is hardened so that can't happen:

- **Sandboxed optimizer** — when SAGE builds the optimizer it passes
  `--disallowedTools "Write Edit MultiEdit NotebookEdit Bash"` and a throwaway
  cwd, so the optimizer can only emit *text*. The proposal always reaches a human
  before it touches any file. Opt out with `sandbox=False` / `--no-sandbox` (only
  for a trusted, non-file-writing optimizer).
- **Sharpened rubric** — before iterating, the evaluator expands the terse
  `criteria` into a concrete, checkable rubric and judges every iteration against
  it. A fixed bar keeps scoring consistent and stops evaluator drift. Opt out with
  `generate_rubric=False` / `--no-rubric`.
- **Robust optimize step** — a wrapping ```` ```code fence ```` is stripped from
  each candidate, and an empty/errored optimizer response is retried once.

## Run it

```bash
# make SAGE better: optimize an artifact against criteria
make optimize TASK="Tighten this approval-inbox component for reuse + a11y" \
              CONTEXT=web/src/pages/Approvals.tsx OUT=/tmp/approvals.improved.tsx

# or directly
python -m src.core.evaluator_optimizer \
  --task "Improve the analyst prompt for fewer false positives" \
  --context-file solutions/medtech/prompts.yaml \
  --optimizer claude-code --evaluator gemini \
  --max-iterations 4 --threshold 8.0
```

Prerequisites: the `gemini` and `claude` CLIs on PATH and authenticated (browser
OAuth / existing auth — no API keys; see GETTING_STARTED.md).

## In code

```python
from src.core.evaluator_optimizer import EvaluatorOptimizerRunner

runner = EvaluatorOptimizerRunner({
    "optimizer": {"provider": "claude-code", "model": "claude-sonnet-4-6"},
    "evaluator": {"provider": "gemini",      "model": "gemini-2.5-flash"},
    "criteria": "correctness, clarity, no security gaps, follows SAGE conventions",
    "max_iterations": 4, "score_threshold": 8.0,
})
result = runner.run(task="...", context="...current artifact...")
# result["final"]   -> submit to HITL approval
# result["history"] -> per-iteration score + feedback (audit trail)
# result["converged"], result["score"]
```

Providers are injectable (`optimizer_provider` / `evaluator_provider`) for testing —
see `tests/test_evaluator_optimizer.py` (mock providers; 10 tests, no live LLMs —
covers convergence, rubric sharpening, fence stripping, retry, and the sandbox).

## How it converges

0. **Sharpen** (once) — Gemini turns `criteria` into a concrete rubric used for
   every later judgement.
1. **Optimize** — Claude produces a candidate (iteration 1) or revises against the
   evaluator's last feedback (later iterations); fences stripped, retried once if empty.
2. **Evaluate** — Gemini returns `{score 0-10, pass, feedback}` (JSON; tolerant of
   fences/prose) against the sharpened rubric.
3. **Stop** when `pass` is true or `score >= threshold`; otherwise loop with the
   feedback fed back to the optimizer, up to `max_iterations`. If it never passes,
   the **best-scoring** candidate is returned (a human still decides).

## Making SAGE better with it

Point the loop at SAGE's own artifacts — a page that needs the reuse refactor, an
agent prompt that's too noisy, a config that drifted — with a task + criteria, and
let Gemini hold the bar while Claude iterates. Wire the result into the approval
inbox and the improvement is auditable end-to-end (the SAGE "Lean Loop", but with
a second model as the critic).
