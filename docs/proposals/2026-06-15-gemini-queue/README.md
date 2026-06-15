# Proposals — Gemini improvement queue (2026-06-15)

Machine-generated **proposals** from running the hardened Evaluator-Optimizer loop on
Gemini's platform findings, then verifying each with an adversarial review workflow.

**These are NOT applied.** They are staged here for the human-in-the-loop approval gate.
Read **[`SYNTHESIS.md`](./SYNTHESIS.md)** first — it has the verdicts, the regressions each
one must fix, the conflicts, and the recommended apply order.

## Files

| File | What |
|------|------|
| `SYNTHESIS.md` | Verdicts, per-item fix lists, conflicts, apply order, meta-findings — **start here** |
| `01-gateway-concurrency.proposal.txt` | Candidate code for #1 (REVISE) — full `llm_gateway.py` rewrite |
| `02-ui-primitives-tokens.proposal.txt` | Candidate for #2 (REVISE) — Card/Modal/Select + `tailwind.config.ts` + `index.css` |
| `03-single-source-useproposals.proposal.txt` | Candidate for #3 (REJECT) — `useProposals` hook + page rewrites |
| `04-header-consistency.proposal.txt` | Candidate for #4 (REVISE, cleanest) — `Header.tsx` rewrite |
| `05-providers-abc-tracing.proposal.txt` | Candidate for #5 (REVISE) — provider ABC + tracing + retry |
| `NN-*.loop.log` | The loop's own per-iteration Gemini score + feedback for that item |

## To act on one (human)

1. Read `SYNTHESIS.md` for that item's verdict and the concrete fixes it still needs.
2. Open the matching `*.proposal.txt`, apply the fixes, and stage it as a real change /
   submit it through the SAGE approval inbox.
3. Mind the conflicts: `#1`/`#5` both rewrite `llm_gateway.py`; `#2`/`#4` both touch `index.css`.

Do **not** trust the in-loop `converged 10/10` score alone — see the meta-finding in
`SYNTHESIS.md` (#2 and #3 scored 10/10 yet are build-breaking / reject; the loop's
evaluator grades the rubric without repo access).
