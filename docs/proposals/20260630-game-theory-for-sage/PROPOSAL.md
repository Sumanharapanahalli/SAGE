# Game Theory for SAGE — A Per-Agent, Per-Capability Application Map (v2)

**Status:** Analysis / proposal (menu of options). Nothing here is approved for build.
**Author:** generated with Claude (Opus 4.8), grounded in the live SAGE codebase.
**Date:** 2026-06-30
**Revision:** v2 — revised after a 5-lens adversarial review (54 findings raised, 42 survived
independent verification). See `REVIEW-findings-v1.md` for the full record. The most important
change: the motivating "unreliable referee" failure was **re-anchored to its real cause** (a
self-grading misconfiguration + a parse bug), and the recommended first slice was re-pointed at
the code path that actually broke.

> **How to read this.** This is the *landscape*, not a single design. It maps concrete
> game-theory mechanisms onto every SAGE agent and capability, with scope and the specific
> improvement each delivers. Picking any one item to actually build then goes through the
> normal design → plan → implement flow with HITL approval — a game's output is always a
> *proposal*, never an auto-decision (Law 1).

---

## 1. Thesis (corrected)

SAGE is already a multi-agent system with an adversarial core (optimizer vs. evaluator), a
rating system (`agent_gym`, Glicko-2-inspired self-play), and ensemble reviewing
(`critic.multi_critic_review`). Game theory is the *formalization and hardening* of mechanisms
SAGE already gestures at.

**But be honest about what actually went wrong this session, because it changes the
recommendation.** The flat 0.0s / inflated 9.5s / capped 4–7.5 scores we saw were **largely a
misconfiguration plus a parse bug, not a missing mechanism**:

1. The self-improvement run used **one model (Opus 4.8) as BOTH optimizer and evaluator** —
   i.e. self-grading. The documented house default is `OPTIMIZER=claude-code / EVALUATOR=gemini`
   (`evaluator_optimizer.py:10-12`); the run overrode both to Opus.
2. Many "0.0" verdicts were **JSON-parse failures**: when the evaluator's JSON can't be
   extracted, the score *silently defaults to 0.0* (`evaluator_optimizer.py:227-231`). A 0.0
   from a parse failure is not a low-quality judgement — it is a swallowed error.
3. The bulk of the late-run failures were the **Opus capacity outage** ("Unknown error"), not
   the evaluator being a poor referee at all.

So the cleanest wins are not exotic game theory — they are *Step 0 wiring fixes*. Game theory
then earns its place hardening the referee **after** the misconfiguration is removed, and
several mappings below are genuinely valuable. The honest framing: **fix the wiring first,
formalize second, and don't sell incentive-compatibility the cooperative-LLM setting can't
deliver.**

**Caveat up front (expanded in §7):** LLM "agents" have no stable utility functions and no
currency, so formal equilibrium and incentive-compatibility *guarantees* do not transfer.
Several classical mechanisms (VCG, quadratic voting, peer prediction) are included for their
*structure*, with their impossibility results stated inline — not as proofs of optimality.

---

## 2. What SAGE already does game-theoretically (the baseline)

| Existing feature | Game-theoretic content | File |
|---|---|---|
| Evaluator-Optimizer loop | 2-player iterated game (proposer vs. **single** judge) | `src/core/evaluator_optimizer.py` |
| Agent Gym | Self-play + **Glicko-2-inspired** ratings (simplified, non-iterative volatility per `agent_gym.py:1249`) | `src/core/agent_gym.py` |
| `critic.multi_critic_review` / `review_*_multi` | N-provider panel, aggregated by a **non-robust weighted mean** (`critic.py:706`) | `src/agents/critic.py` |
| `review_with_loop` | Iterated best-response; **already has** a stopping rule (score≥threshold, max-iters) | `src/agents/critic.py:388` |
| Orchestrator consensus / beam search; `PlanSelector` | Aggregation + N-candidate plan select→score→rank | `src/core/`, `src/core/plan_selector.py` |
| AdaptiveRouter | Online learning of `(task_type, agent_role)` routing from execution success (fixed quality score 0.5/0.0; **no model dim, not human-feedback-driven**) | `src/integrations/build_orchestrator.py:2807` |
| CI/CD pipeline status | **Objective, un-gameable** pass/fail oracle | `developer.get_pipeline_status` |
| Constitution | Priority-ordered principles + decision rules (`check_action`, `can_auto_approve`) | `src/core/constitution.py` |
| Collective memory; audit-integrity hash-chain | Cross-agent knowledge; tamper-evident outcome record | `collective_memory.py`, `audit_integrity.py` |

The work below extends these. Note two referee paths exist and they are **different code**:
the single-judge `evaluator_optimizer` loop (what the failing run used) and the N-provider
`multi_critic_review` panel (what §8 must target — see §6).

---

## 3. The game-theory toolkit (concept catalogue)

1. **Tournaments + Elo/Glicko/Bradley–Terry** — rank rival outputs by pairwise competition. *Glicko-2 fits **persistent** players; for **ephemeral** one-batch candidates use Bradley–Terry / Plackett–Luce or Copeland/round-robin (no time-decay/volatility needed).*
2. **Proper scoring rules** (Brier, log) — elicit a *calibrated probabilistic forecast of a realized event*. In SAGE (an unpaid LLM judge with no payoff) this yields a **calibration / confidence signal** measured against eventual audit-log labels — *not* classical incentive-compatibility.
3. **Robust social choice** — aggregate many *cardinal* judgements with **median / trimmed-mean** (breakdown point ~50% vs. the weighted mean's 0). *Ordinal* methods (Condorcet) need ≥2 ranked candidates and can cycle — they belong with tournaments, not single-artifact scoring.
4. **Multi-agent debate** — two agents argue opposite sides; a judge rules. Surfaces hidden failure modes.
5. **Peer prediction / Bayesian Truth Serum** — elicit honest signals without ground truth by collecting both an answer *and a prediction of others' answers*, rewarding answers that are **surprisingly common** (more frequent than the crowd predicts) plus accurate meta-predictions. *Not strategyproof:* admits uninformative/colluding equilibria (Bayes-Nash, not dominant-strategy); classic BTS truthfulness is asymptotic + common-prior, so it is unreliable for a handful of critics. Prefer multi-task / correlated-agreement variants (Dasgupta–Ghosh 2013; Shnayder et al. 2016) when robustness matters.
6. **Mechanism design / VCG** — *dominant-strategy* truthfulness comes only from the **second-price/Vickrey payment rule** (a plain first-price sealed-bid auction is strategically shaded — bid < value — and is **not** incentive-compatible). VCG further requires private valuations, a payment numeraire, and collected transfers; it is **not budget-balanced** (Green–Laffont) and is collusion/shill-vulnerable. *In SAGE these preconditions are absent — see §7.*
7. **Stackelberg (leader-follower)** — one player commits first (e.g. the critic fixes a rubric), the other best-responds.
8. **Information design / Bayesian persuasion** (Kamenica–Gentzkow 2011) — a committing critic's rubric shapes what the optimizer best-responds to; "what the rubric reveals" is itself a design lever.
9. **Shapley value** — fair credit across a coalition. *Exact is O(2ⁿ) and needs a defined characteristic function v(S); use Monte-Carlo/permutation estimators, offline only.*
10. **No-regret / contextual bandits** — minimize **regret against the best policy in hindsight** (not "converge to the best arm" — routing reward is non-stationary). LinUCB / contextual Thompson for context; discounted/sliding-window UCB (Garivier–Moulines) or EXP3 for non-stationarity.
11. **Principal-agent** — align an agent with a principal (the human / the HITL gate / the Constitution).
12. **Repeated games + reputation** — cooperation sustained by track record; *credible only if history is tamper-evident* (audit-integrity hash-chain).
13. **Inspection / security games** — allocate scarce auditing to deter a **strategic** inspectee; yields **randomized** coverage. (For non-adversarial drift, use change-detection instead — §4.6.)
14. **Coalition / team formation; PSRO / double-oracle** — assemble the agent-set that maximizes joint value; PSRO/double-oracle give population-based self-play with a Nash meta-strategy (anti-farming opponent selection).

---

## 4. Per-agent × per-capability application map (the core)

Legend — **Effort:** S/M/L · **Risk:** Lo/Md/Hi · **Reuse:** existing code to build on.

### 4.1 Universal Agent — `get_roles`, `run`, `execute` (the router)

| Capability | Mechanism | How it improves | Effort/Risk/Reuse |
|---|---|---|---|
| `run`/`execute` route task→agent | **Contextual bandit (LinUCB / Thompson)** with discounted/sliding-window UCB for non-stationarity | Router already learns over `(task_type, role)`; net-new = adding a **model dimension** and an **approval/critic reward** path (today it uses a fixed 0.5/0.0 execution-success score) | M/Lo · extend **AdaptiveRouter** (wiring the HITL reward is the real cost) |
| Model selection (Opus/Sonnet/Gemini) | **Cost-adjusted-reward bandit** | Spends the expensive model only where it earns its keep (directly relevant to the Opus cost this session) | M/Md · `llm_gateway` (net-new dimension) |
| Allocate a task several agents could serve | **Heuristic cost-ranked allocation** (NOT an auction) | Cheap tasks don't go to expensive agents. *No IC claim — see §7; agents have no private valuations/currency* | S/Lo |

### 4.2 Analyst — `analyze_log`, `learn_from_feedback`

| Capability | Mechanism | How it improves | Effort/Risk/Reuse |
|---|---|---|---|
| `analyze_log` (single shot) | **Ensemble + trimmed-mean** over k samples | Variance reduction; fewer flukey analyses | S/Lo |
| `analyze_log` confidence | **Proper scoring rule on P(human approves)** vs. realized audit-log labels (Brier/log) | Calibrated confidence (a "0.9" means 0.9). *Channel = confidence-aware retrieval reweighting (Memento), not retraining or IC* | M/Md+ · audit log = labels; needs a label corpus |
| `learn_from_feedback` → vector memory | **Reputation-weighted retrieval** — weight a memory by whether acting on it led to approval | Memory compounds by *reliability*, not recency. *Credible only atop the tamper-evident audit chain* | M/Md · vector store + `audit_integrity` |
| Corrections without ground truth | **Multi-task peer prediction** (Dasgupta–Ghosh) | Cross-validates corrections; flags low-information feedback. *Not strategyproof — keep human feedback as anchor* | L/Hi · research-grade |

### 4.3 Coder — `implement_step`

| Capability | Mechanism | How it improves | Effort/Risk/Reuse |
|---|---|---|---|
| `implement_step` (single candidate) | [DONE, scoped-down] **Best-of-N, cardinal-scored via `PlanSelector` + `multi_critic_review`** | Higher quality via competition. *Built without Bradley–Terry/Copeland or new tournament plumbing — see Phase 2 note in §6* | S/Md — landed |
| Verification of generated code | [DONE, scoped-down] **Refutation via git-stash-isolated re-run**, not a real execution venue | Builds in atomic verification (Law 5) — *actually run*, not just LLM-scored. *Explicit user tradeoff: no WorktreeManager, no `_ROOT` refactor — see §6* | S/Md — landed |
| Skill growth over time | **Self-play + PSRO / double-oracle** | Coder trains vs. a Nash meta-strategy of opponents; resists farming one weak opponent (Nash averaging on the rating side) | L/Hi · gym extension (re-scope DB to `.sage/` — see §7) |

### 4.4 Critic — `review_*`, `review_with_loop`, `multi_critic_review`, `request/submit_human_review`

*The highest-leverage agent — but target the right path (see §6).*

| Capability | Mechanism | How it improves | Effort/Risk/Reuse |
|---|---|---|---|
| `multi_critic_review` aggregation | **Median / trimmed-mean + diversity-weighted lenses** | One rogue/extreme critic (a 0.0 or 9.5) can no longer drag the verdict — the weighted mean at `critic.py:706` has breakdown point 0; median ~50%. **This carries the scale-inflation remedy.** | **S/Lo · formalize existing method** |
| `review_*` JSON handling | **Robust parsing** (unparseable ≠ silent 0.0) | Fixes the *actual* cause of the flat 0.0s. *This is the named-failure fix, not "proper scoring"* | **S/Lo** · port critic's parse-error flag |
| `review_*` calibration | **Proper scoring rule** on P(approve)/P(tests pass) vs. audit labels | Trustworthy *confidence*; does **not** by itself fix scale inflation (median does) | M/Md+ · deferred (Phase 1b) |
| `review_with_loop` | **Committed (Stackelberg) rubric** — port `evaluator_optimizer._generate_rubric` | Stops rubric drift. *The loop already stops on threshold/max-iters; only the committed rubric is new* | S/Lo |
| Ranking among multiple candidates | **Condorcet / Copeland** | Needs ≥2 candidates to rank — belongs in **Phase 2** with tournaments, not single-artifact scoring | M/Md |
| `request/submit_human_review` | **Value-of-information + principal-agent** escalation | Humans see only the items where their scarce attention changes the outcome — amplifies Law 1 instead of flooding it | M/Md |

### 4.5 Developer — `review_merge_request`, `propose_code_patch`, `create_mr_from_issue`, `add_mr_comment`, `list_open_mrs`, `get_pipeline_status`

| Capability | Mechanism | How it improves | Effort/Risk/Reuse |
|---|---|---|---|
| `review_merge_request` | **Adversarial review game** + **inspection game** (random deep audits) | Higher review quality; random audits deter low-effort MRs without auditing all | M/Md |
| `add_mr_comment` | **Cheap talk / signaling** (Crawford–Sobel) | Models the author↔reviewer channel — when does a comment credibly convey quality vs. cost-free talk | S/Lo |
| `list_open_mrs` | Audit **population** for the inspection game | Allocate random deep audits proportional to risk across the open set | S/Lo |
| `propose_code_patch` | [DONE] **Best-of-N + refutation**, run in a real `WorktreeManager` worktree (`git apply` + full test run) | Patch quality + verification | M/Md · WorktreeManager + CI — landed |
| `get_pipeline_status` | **Objective referee / Goodhart anchor** | CI pass/fail grounds the LLM judge; trust the LLM only on what CI *can't* check (design, security reasoning) | S/Lo — *load-bearing for §6/§8* |

### 4.6 Monitor — `start/stop`, `get_status`, `register_callback`

| Capability | Mechanism | How it improves | Effort/Risk/Reuse |
|---|---|---|---|
| Alert trigger threshold | **Quickest change detection** (CUSUM / Shiryaev–Roberts / SPRT) | Tunes false-alarm rate vs. detection delay — *not* the secretary problem (which is no-recall best-choice) | S/Lo |
| Attention — non-adversarial drift | **Value-of-information / expected-loss sensor allocation** | Watch where failure is most probable; no adversary, no equilibrium | M/Md |
| Attention — strategic threats | **Stackelberg security game = randomized patrol** that equalizes attacker payoff | Coverage an adversary can't exploit (a deterministic "watch the likeliest" is exploitable) | M/Md |

### 4.7 Planner — `create_plan`, `plan_and_execute`, `get_plan_status`

| Capability | Mechanism | How it improves | Effort/Risk/Reuse |
|---|---|---|---|
| `create_plan` (one `llm.generate`) | [DONE] **Judge panel of N divergent plans → score → synthesize**, wired via `PlanSelector` + `multi_critic_review` | Robust plans; best ideas grafted from runners-up. *The N-generate→score→rank→select core already existed — this was wiring, not new mechanism* | S/Lo — landed |
| Planning under uncertainty | **Minimax / robust optimization** | Picks the least-bad plan in the worst case — fits regulated-industry risk | M/Md |
| `plan_and_execute` wave scheduling | **Team formation + Shapley credit (Monte-Carlo, offline)** | Better team assembly; *cheap online default = per-agent EMA success already tracked by AdaptiveRouter* | L/Hi |
| Backlog ordering under budget | **Budgeted knapsack (value-per-cost)** — NOT an "auction" (no bidders/private values/payments) | Orders work by value-per-cost | S/Lo |

*(Removed the v1 "`prioritize` capability" row — no such method exists on the Planner; the real
prioritization is `product_owner.prioritize_stories`, §4.8.)*

### 4.8 Product Owner — `gather_requirements`, `prioritize_stories`, `approve/refine_backlog`

| Capability | Mechanism | How it improves | Effort/Risk/Reuse |
|---|---|---|---|
| `prioritize_stories` (MoSCoW) | **Median rule** (strategyproof under single-peaked prefs, Black/Moulin); **quadratic voting** to reveal *intensity* | Fair aggregation. *QV is valued for intensity revelation, **not** strategyproofness — it is collusion/sybil-vulnerable (splitting n votes across k identities cuts cost n²→n²/k)* | M/Md |
| `gather_requirements` (5W1H) | **Multi-task peer prediction** to elicit true priorities | Discounts strategic exaggeration. *Not strategyproof — see §7* | L/Hi |
| `approve/refine_backlog` | **Stackelberg** — PO commits acceptance criteria first | Stable target for downstream agents | S/Lo |

---

## 5. Cross-cutting / system-level mechanisms

| Surface | Mechanism | Improvement |
|---|---|---|
| **Constitution** (`constitution.py`) | **Stackelberg commitment / principal-agent objective** | The human principal pre-commits weighted, priority-ordered principles (`get_principles_by_priority`, `check_action`, `can_auto_approve`) before agents play — giving every mechanism a stable *principal objective* to be aligned against. *Mitigates, doesn't eliminate, §7's "no stable utilities"; the [0,1] weights are not a literal utility function* |
| **CI/CD pipeline** (`get_pipeline_status`) | **Objective arbiter / Goodhart anchor** | Grounds the LLM critic's calibration loop and the refutation games against real test/job pass-fail; trust the LLM judge only where CI can't reach |
| **HITL approval gate** | **Mechanism design / principal-agent** — reputation that penalizes *overconfident, later-rejected* proposals | The gate sharpens over time; agents incentivized to reveal true confidence/risk |
| **Queue / wave scheduler** (`queue_manager.py`) | **Scheduling + mechanism design** | The per-task `priority` field is cost-free cheap talk over scarce worker slots (`max_workers=4`); charge declared priority against the agent's compute budget to make it incentive-compatible. `LoopDetector` = inspection-game guard against degenerate self-spawning fanout |
| **Agent-hire** (`agent_factory`/`role_generator`) | **Labor-market auction** | Hire the agent that wins its gym "interview" (ratings + exercises) |
| **Per-agent budgets** | **Cost-ranked allocation** (NOT VCG) | Honest framing: agents have no private valuations or currency, so VCG's IC is vacuous and its payments aren't budget-balanced (Green–Laffont). Use a cost-aware ranking; reserve "auction" for genuine bidders |
| **Proposal store + RiskClass** (`proposal_store.py`) | **Inspection game** keyed to `reversible`/blast-radius | Allocate audit scrutiny + VoI escalation by irreversibility. *Precondition: today `risk_class` is a static literal driving only expiry windows — it must be made content-derived and wired into routing before this signal exists* |
| **Collective memory + audit-integrity** | **Reputation game** atop a **tamper-evident hash-chain** (`verify_chain`) | Cross-solution learnings weighted by track record; reputation only deters defection if history can't be rewritten (the chain *detects*, doesn't prevent, tampering) |
| **Agent Gym** | **Nash averaging / PSRO** | Ratings that can't be gamed by farming one weak opponent |

---

## 6. Prioritization & phasing (re-anchored)

- **[DONE] Step 0 — fix the misconfiguration (near-free; this is what actually broke).**
  (a) Set the evaluator to a **different model** than the optimizer (stop self-grading;
  house default Claude/Gemini). (b) Make evaluator/critic JSON parsing **robust** so an
  unparseable response is a flagged retry, **not a silent 0.0** (`evaluator_optimizer.py:227-231`,
  `critic.py`). (c) [DONE] Route self-improvement scoring through an N-provider panel + robust
  median (1 judge → N) — `EvaluatorOptimizerRunner.evaluator_pool_providers`/`evaluator_pool`
  config, aggregated via a local float-preserving weighted-median (not `CriticAgent._robust_aggregate`
  directly — that helper rounds to int, tuned for `multi_critic_review`'s 0-100 scale; this loop
  needs 0-10 float precision). Backward compatible: a pool of one (the default) is byte-identical
  to the prior single-evaluator behavior. No new mechanisms.
- **[DONE] Phase 1a — robust referee (true S/Lo, no new data).**
  Swap `multi_critic_review`'s weighted **mean → median/trimmed-mean** (`critic.py:706`) +
  diversity lenses; commit the Stackelberg rubric in `review_with_loop` (`CriticAgent._generate_review_rubric`,
  mirrors `evaluator_optimizer._generate_rubric` — generated once before the loop, injected into
  every iteration's review context, degrades to no-rubric on any failure rather than blocking).
  Targets **both** referee paths (single-judge loop *and* panel) — done for both.
  **Diversity lenses** (multiple distinct review angles, not just multiple providers on the same
  prompt) remain unbuilt — not part of the S/Lo slice; would need its own scoping.
  **Also fixed while grounding this phase**: the Agent Gym's `GymDB` default `db_path` wrote to
  framework root (`<project_root>/.gym_data.db`) instead of the active solution's `.sage/`
  directory — the exact prerequisite §7 flags as blocking before any rating-reuse mechanism
  (tournaments, PSRO) is safe to build. Now resolves via `ProjectConfig.sage_data_dir`, the same
  single-source-of-truth every other per-solution store uses. `gym.py`'s route handlers are
  unchanged (still use the global `agent_gym` singleton) — only where its data physically lives
  changed.
- **Phase 1b — calibration (deferred, M/Md+).**
  Proper-scoring-rule calibration of critic confidence against accumulated **resolved human
  verdicts + CI pass/fail**. Gated on a sufficient label corpus.
- **[DONE] Phase 2 — competition.**
  All three items landed, but on a materially cheaper mechanism than originally scoped: **cardinal
  scoring via the existing `PlanSelector` (N-generate→score→rank→select, Phase 1's beam-search engine)
  + `CriticAgent.multi_critic_review` (Phase 1a's robust weighted-median panel)** — not a new
  Bradley–Terry/Copeland pairwise-tournament module. Grounding (advisor-reviewed) showed
  `PlanSelector`'s generic `select(generator, critic, beam_width)` contract already covers all three
  agents' needs; building net-new O(N²) pairwise-judge infrastructure alongside it would have been
  exactly the kind of "build ahead of need" this proposal explicitly rejects elsewhere (§6 Phase 1b/4).
  Condorcet/Copeland ranking remains unbuilt — no evidence yet that cardinal (median) scoring is
  failing on code/plan candidates the way it was failing on critic panels pre-Phase-1a.
  - **`Planner.create_plan(beam_width=N)`** — `src/agents/planner.py`. Generates N candidate plans,
    scores each via `multi_critic_review("plan", ...)` (normalized to 0–1), picks the best.
    `beam_width=1` (default) is byte-identical to the original single-shot path.
  - **`Developer.propose_code_patch(beam_width=N)`** — `src/agents/developer.py`. Generates N
    candidate patches (pure text, no filesystem writes), verifies each in a real isolated
    `WorktreeManager` worktree (`git apply -p1`/`-p0`, then a full `pytest tests/` run) — a patch
    that fails to apply is disqualified outright regardless of LLM score; a patch whose tests fail
    is heavily penalized (0.3×) rather than zeroed, since a failing test may be pre-existing/unrelated.
    Worktrees are always cleaned up (`finally`-guarded). This is the one piece built exactly as
    originally scoped ("Best-of-N + refutation, run in a worktree") since `propose_code_patch` never
    writes to the main tree, so worktree isolation was cheap.
  - **`Coder.implement_step(beam_width=N)`** — `src/agents/coder.py` — **scoped down by explicit user
    decision**, not built as originally envisioned. The real cost/risk profile only became clear
    during grounding: unlike the other two (cheap pure-text candidates), `implement_step` runs a full
    ReAct loop per candidate (up to ~12 LLM steps, real file writes via a module-level `_ROOT`
    constant used across 6 tool methods) — true `WorktreeManager` isolation would have required
    refactoring `_ROOT` to an instance attribute across all 6 methods plus N parallel worktree-isolated
    ReAct runs, a materially larger and riskier change to the code-writing agent's core I/O path than
    "wire `PlanSelector` in" as originally scoped. Surfaced back to the user as its own go/no-go
    (not re-litigating the original "build all of Phase 2" approval — correcting the scope estimate
    it was made on); the user chose the scoped-down variant. **What shipped instead**: N *sequential*
    ReAct-loop attempts in the *main* working tree, isolated between attempts via `git stash push -u`
    (candidate) → `git stash apply` (winner only) → `git stash drop` (every candidate, resolved to its
    live `stash@{n}` ref at drop-time since indices shift after each drop). Falls back to single-shot
    if the working tree isn't clean at call time (best-of-N needs a clean baseline to safely isolate
    candidates) — refuses to co-mingle a candidate's stash with pre-existing uncommitted work rather
    than silently risking it. Known tradeoff, accepted by the user: no true per-candidate parallelism,
    and a real (if small) window per candidate where its writes sit in the main tree before being
    stashed. No `_ROOT` refactor was needed or done.
  - No shared "tournament.py" primitive was built. All three reuse `PlanSelector` + `CriticAgent`
    directly; there was no duplicated selection logic to factor out.
- **Phase 3 — spend scarce resources well.** Contextual-bandit router (add model dim + HITL reward);
  VoI escalation for `request_human_review`; budget-charged priority in the scheduler.
- **Phase 4 — research-grade.** Multi-agent debate for high-stakes approvals; Monte-Carlo Shapley;
  multi-task peer prediction; PSRO/Nash-averaged gym ratings.

---

## 7. Honest caveats & anti-patterns

- **No stable utilities → no incentive-compatibility.** LLM agents have no fixed payoff and no
  currency, so VCG/auction/peer-prediction *truthfulness* claims are decorative here. Where this
  document maps such a mechanism, it is for *structure*, framed as a heuristic.
- **Known impossibility results (these bind even with perfectly rational agents — distinct from
  the no-utilities caveat):**
  - *Voting / QV* → **Gibbard–Satterthwaite** (every non-dictatorial ordinal rule over ≥3 options
    is manipulable) + **QV collusion/sybil**; so "manipulation-resistant" only ever means
    "under stated assumptions."
  - *VCG* → **Green–Laffont / Myerson–Satterthwaite** (no efficient, IC, IR, budget-balanced
    mechanism) — a truthful VCG budget auction runs a deficit needing external subsidy — plus
    collusion/shill-bidding.
  - *Peer prediction / BTS* → non-unique equilibria including **uninformative/colluding** ones;
    BTS needs large-n + common prior.
- **Goodhart.** Every mechanism optimizes a *proxy* (the critic's score). Keep **human feedback +
  CI** central as the anchor (Law 3); a green pipeline only verifies what tests cover.
- **Cost.** Tournaments are O(N²) judgements; debate doubles agent calls; exact Shapley is O(2ⁿ).
  Gate the expensive mechanisms behind **risk class** — high-stakes proposals only.
- **Data isolation (hard SOUL.md rule).** All learned runtime state — calibration tables,
  reputation, bandit weights, candidate ratings — must persist **per-solution under
  `.sage/` via `ProjectLoader.sage_data_dir`**, never in `src/`, never committed, never keyed to a
  hardcoded solution name. *The gym's Glicko DB currently writes to framework root
  (`<project_root>/.gym_data.db`) — any rating reuse must be re-scoped to `.sage/` first.*
- **Complexity budget.** Prefer the smallest mechanism that fixes a *named* failure. Step 0 fixes
  the one we actually hit; everything past Phase 1 should clear a real, observed need.

---

## 8. Recommended first slice (re-anchored)

If you build one thing: **Step 0 + Phase 1a**, pointed at the referee path that *actually broke*.

- **Step 0** (different evaluator model + robust parsing + route through `multi_critic_review`)
  is near-free and removes the real cause of the flat 0.0s we lived through.
- **Phase 1a** (mean→median aggregation + committed rubric) is genuinely S/Lo, needs no new data,
  and makes the referee robust to a single rogue score — the property every downstream mechanism
  (tournaments, escalation, hiring) ultimately leans on.
- Ground it on **CI pass/fail** (`get_pipeline_status`) wherever a real test exists; reserve the
  LLM judge for what CI can't check.

Explicitly **not** the v1 recommendation ("harden `multi_critic_review` + proper-scoring
calibration"): calibration can't repair a phantom 0.0, and the failing run never used the panel.
Defer proper-scoring (Phase 1b) until resolved human/CI labels accumulate.

That slice would then go through the normal design → plan → implement cycle with HITL review.
