export const meta = {
  name: 'sage-queue-review',
  description: 'Adversarially review + verify the 5 Evaluator-Optimizer proposals, then synthesize an apply plan',
  phases: [
    { title: 'Review', detail: 'one reviewer per proposal vs its target files' },
    { title: 'Verify', detail: 'adversarial verifier tries to refute each apply verdict' },
    { title: 'Synthesize', detail: 'rank, flag conflicts, recommend apply order' },
  ],
}

const ROOT = 'C:/sandbox/SAGE'
const LOOP = 'C:/tmp/sage_loop'

const ITEMS = [
  {
    id: 1, title: 'Unblock concurrency: kill the thread-locked LLM gateway singleton',
    dimension: 'agent-framework',
    targets: [`${ROOT}/src/core/llm_gateway.py`],
    goal: 'Remove the global thread-lock that serializes all inferences; gate only local GPU models with a semaphore; let API/CLI providers run concurrently; make the gateway injectable, not a hard singleton; stay backward compatible.',
  },
  {
    id: 2, title: 'Establish UI primitives + collapse to tokens-via-Tailwind',
    dimension: 'web-reuse',
    targets: [`${ROOT}/web/src/components/ui/Button.tsx`, `${ROOT}/web/src/index.css`, `${ROOT}/web/tailwind.config.ts`],
    goal: 'Add Card/Modal/Select primitives that consume --sage CSS tokens (no hex / no raw tailwind colors), matching the Button.tsx conventions; map sage tokens into tailwind.config.ts.',
  },
  {
    id: 3, title: 'Single-source-of-truth components + extract shared logic',
    dimension: 'web-reuse',
    targets: [`${ROOT}/web/src/pages/Dashboard.tsx`, `${ROOT}/web/src/pages/Approvals.tsx`, `${ROOT}/web/src/components/proposals/ProposalCard.tsx`],
    goal: 'Delete the inline ProposalCard/ToastContainer duplicates; add a useProposals hook + lib/date.ts formatRelativeTime; both pages consume the canonical shared component + hook with identical behavior.',
  },
  {
    id: 4, title: 'Fix header status/color/label consistency',
    dimension: 'visual-ui',
    targets: [`${ROOT}/web/src/components/layout/Header.tsx`, `${ROOT}/web/src/index.css`],
    goal: 'One labelled status dot (Online/Offline) at >=4.5:1 contrast via tokens; consistent color strategy (accent vs status vs selection); remove redundant tags; preserve props/handlers.',
  },
  {
    id: 5, title: 'Decouple providers behind an ABC + always-on pluggable tracing + retry',
    dimension: 'agent-framework',
    targets: [`${ROOT}/src/core/llm_gateway.py`],
    goal: 'Common provider ABC with an injectable mock; always-on tracing with a default console tracer + propagated trace_id; configurable retry (backoff+jitter) on 429/500/503; backward compatible.',
  },
]

const REVIEW_SCHEMA = {
  type: 'object',
  required: ['implements_goal', 'is_real_code', 'apply_readiness', 'summary', 'regressions', 'overreach', 'key_risks'],
  properties: {
    implements_goal: { type: 'boolean', description: 'does the candidate actually implement the stated goal?' },
    is_real_code: { type: 'boolean', description: 'is the candidate concrete code/diff (not prose, not a stub)?' },
    correctness: { type: 'string', description: 'correctness assessment of the candidate' },
    regressions: { type: 'array', items: { type: 'string' }, description: 'behavior/API regressions vs the current file(s)' },
    hitl_safe: { type: 'boolean', description: 'safe to stage for human review (no destructive/unscoped actions baked in)?' },
    overreach: { type: 'array', items: { type: 'string' }, description: 'changes beyond the stated scope' },
    apply_readiness: { type: 'string', enum: ['apply', 'revise', 'reject'] },
    summary: { type: 'string' },
    key_risks: { type: 'array', items: { type: 'string' } },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['agrees', 'final_readiness', 'confidence', 'reasoning'],
  properties: {
    agrees: { type: 'boolean', description: 'does the verifier agree with the reviewer apply_readiness?' },
    refutation: { type: 'string', description: 'strongest case that the readiness is wrong (empty if none)' },
    final_readiness: { type: 'string', enum: ['apply', 'revise', 'reject'] },
    confidence: { type: 'number', description: '0-1 confidence in final_readiness' },
    reasoning: { type: 'string' },
  },
}

const SYNTH_SCHEMA = {
  type: 'object',
  required: ['ranking', 'apply_order', 'conflicts', 'overall'],
  properties: {
    ranking: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'title', 'readiness', 'one_line'],
        properties: {
          id: { type: 'number' }, title: { type: 'string' },
          readiness: { type: 'string', enum: ['apply', 'revise', 'reject'] },
          one_line: { type: 'string' },
        },
      },
    },
    apply_order: { type: 'array', items: { type: 'number' }, description: 'recommended order of human review/apply' },
    conflicts: { type: 'array', items: { type: 'string' }, description: 'proposals that touch the same files / would conflict' },
    overall: { type: 'string' },
  },
}

function reviewPrompt(item) {
  return `You are reviewing a code PROPOSAL generated by an Evaluator-Optimizer loop (Claude optimized, Gemini graded). It is NOT yet applied — a human will decide.

PROPOSAL #${item.id}: ${item.title} (${item.dimension})
GOAL the proposal must achieve:
${item.goal}

STEPS:
1. Read the candidate proposal: ${LOOP}/fix_${item.id}.txt
2. Read the loop log (per-iteration Gemini score + feedback): ${LOOP}/log_${item.id}.txt
3. Read the CURRENT target file(s) to compare against:
${item.targets.map(t => '   - ' + t).join('\n')}

Judge rigorously and concretely:
- Does the candidate actually implement the goal, or only gesture at it?
- Is it real, concrete code/diff — or prose, pseudo-code, or a stub?
- Would applying it cause regressions (changed/broken behavior, API, props, imports)?
- Is it HITL-safe (no destructive or out-of-scope actions baked in)?
- Does it overreach beyond the stated scope?
- Verdict: apply (ready to stage for a human to apply largely as-is), revise (right idea, needs concrete fixes — name them), or reject (wrong/unsafe/not real code).

Be specific. Cite what you saw in the candidate. Return the structured verdict.`
}

function verifyPrompt(item, review) {
  return `You are an ADVERSARIAL verifier. A reviewer judged proposal #${item.id} ("${item.title}") as apply_readiness="${review?.apply_readiness}".

Their summary: ${review?.summary}
Regressions they noted: ${JSON.stringify(review?.regressions || [])}
Overreach they noted: ${JSON.stringify(review?.overreach || [])}

Try hard to REFUTE that readiness. Re-read what you need:
- candidate: ${LOOP}/fix_${item.id}.txt
- current target(s): ${item.targets.join(', ')}

Especially attack an "apply" verdict: look for a hidden regression, a missing import, a broken signature, an unscoped deletion, or claims of "real code" that are actually incomplete. If after a genuine attempt you cannot refute it, agree. Default to a MORE conservative readiness when genuinely uncertain. Return the structured verdict.`
}

// Phase 1 (Review) -> Phase 2 (Verify), pipelined per item (no barrier)
const reviewed = await pipeline(
  ITEMS,
  (item) => agent(reviewPrompt(item), { label: `review:#${item.id}`, phase: 'Review', schema: REVIEW_SCHEMA }).then(r => ({ item, review: r })),
  ({ item, review }) => agent(verifyPrompt(item, review), { label: `verify:#${item.id}`, phase: 'Verify', schema: VERDICT_SCHEMA }).then(v => ({ item, review, verdict: v })),
)

const ok = reviewed.filter(Boolean)

// Phase 3 (Synthesize) — single agent ranks + flags conflicts
phase('Synthesize')
const rows = ok.map(r => ({
  id: r.item.id, title: r.item.title, dimension: r.item.dimension, targets: r.item.targets,
  reviewer_readiness: r.review?.apply_readiness, implements_goal: r.review?.implements_goal,
  is_real_code: r.review?.is_real_code, regressions: r.review?.regressions, overreach: r.review?.overreach,
  verifier_final: r.verdict?.final_readiness, verifier_agrees: r.verdict?.agrees, verifier_conf: r.verdict?.confidence,
}))
const synthesis = await agent(
  `Synthesize an apply plan for these 5 reviewed-and-verified SAGE proposals. Use the verifier's final_readiness as the authoritative verdict per item.

DATA:
${JSON.stringify(rows, null, 2)}

Produce: a ranking (best-prepared first), a recommended apply_order (ids), explicit conflicts (e.g. #1 and #5 both rewrite src/core/llm_gateway.py and cannot both be applied blindly), and an overall read. Be concise and decision-useful for a human reviewer.`,
  { label: 'synthesize', schema: SYNTH_SCHEMA },
)

return { reviewed: rows.map((row, i) => ({ ...row, verdict: ok[i].verdict, review: ok[i].review })), synthesis }
