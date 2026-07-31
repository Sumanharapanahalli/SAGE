# Desktop Parity Progress

Tracking file for the `/loop` closing web→desktop feature-parity gaps in `sage-desktop`
(Tauri/Rust shell + Python sidecar + React).

**This file is the single source of truth for what is done.** Do not re-derive progress by
re-auditing the code. One item per iteration; first non-DONE item wins.

Verification bar for every item: `make test-desktop` green (sidecar pytest + cargo test +
React vitest), then commit, push branch, `gh pr create --draft`.

## Backlog

| # | Item | Status |
|---|------|--------|
| 0 | Fix broken `.venv` so `make test-desktop` works | **DONE** |
| 1 | Wire dead handler `sidecar/handlers/safety.py` + `/safety` page | **DONE** |
| 2 | Wire dead handler `sidecar/handlers/agentrun.py` (HITL for `agent_hire`) | **DONE** |
| 3 | Surface agentrun in the UI (Run + Hire tabs on `/agents`) | **DONE** |
| 4a | Onboarding: scan-folder import of existing codebase | **DONE** |
| 4b | Onboarding: org-template chooser | **DONE** |
| 4c | Onboarding: conversational refine loop | **DONE** |
| 4d | Onboarding: pre-write ReviewPanel | **DONE** |
| 5 | Extend `org.*`: channels CRUD, cross-team routes (writable), solutions CRUD | **DONE** |
| 6 | Fix `/organization` ignoring `SAGE_SOLUTIONS_DIR` | **DONE** (with item 5) |
| 7 | Add `/chat` (conversational agent + history) | **DONE** |
| 8 | Add `/code` (plan / execute / approve) | **DONE** |
| 9 | Add `/orchestrator` (9 orchestrator-intelligence modules) | TODO |
| 10 | Add remaining `/mr/*` ops (create, review, comment, open, pipeline) | TODO |

Deliberately **out of scope** (deferred with reasons, do not port): Integrations/connectors
(OAuth redirect flows), Auth/access-control (single-operator app), Distillation (niche),
streaming (`/agent/stream`, `/analyze/stream`).

## Rules

- Work in a git worktree; never push to `main`/`master`, never force-push, never merge.
- TDD — tests first.
- Framework stays domain-blind: no solution names in `src/`.
- No `print()` — use `self.logger` / `logging.getLogger()`.
- Smallest correct change; do not refactor while implementing.

## Working location

All loop work happens in the worktree `.claude/worktrees/desktop-parity` on branch
`worktree-desktop-parity`. This file lives there too — the session's working directory was
switched into the worktree, so later iterations find it at the same relative path.

**Run tests from the worktree, not the main checkout** — otherwise you verify unmodified code.
A fresh worktree has neither `node_modules` nor `.venv`, and the Makefile resolves
`VENV_DIR := .venv` relative to CWD, so both are symlinked to the main checkout's copies:

    ln -sfn <repo>/sage-desktop/node_modules <worktree>/sage-desktop/node_modules
    ln -sfn <repo>/.venv                     <worktree>/.venv

Re-create them if a later iteration finds `make test-desktop` failing with "vite not found"
or a missing pytest. If `package.json` ever changes, re-run `npm install` in the main
checkout instead of symlinking.

**Careful: only `.venv` is gitignored.** `sage-desktop/.gitignore` ignores `node_modules/`
*with a trailing slash*, which matches directories only — a **symlink is not a directory**, so
`git add -A` happily stages it. It was caught here before pushing; the path is now in
`.git/info/exclude` (local, deliberately not a repo `.gitignore` change — the trailing-slash
rule is correct for a real `npm install`, and this symlink is loop tooling, not a repo
concern). Verify with `git status --short` before every commit that no symlink is staged.

`npm run test` (vitest) does **not** typecheck. Run `npm run typecheck` (`tsc --noEmit`)
as well before committing — a type error still ships a green vitest run but breaks
`make desktop-dev`.

## Notes

### Item 0 — DONE (2026-07-31)

The prescribed fix (`make venv`) would **not** have worked, and was not run. Diagnosis:

- The venv was created at `/home/shetty/sandbox/SAGE/.venv` and later moved to the current
  path, leaving **82 of 92** scripts in `.venv/bin` with stale absolute shebangs.
- `pip` was itself one of the 82 broken scripts, so `make venv`'s `$(PIP) install -r
  requirements.txt` step would have failed immediately. `make venv` also runs `python -m venv`
  *without* `--clear`, which does not rewrite third-party console-script shebangs anyway.
- `site-packages` contained **zero** stale path references — the 8.4 GB of installed packages
  were intact. This was a venv *relocation* problem, not a corruption problem.

Applied the minimal correct fix instead of an 8.4 GB reinstall:

1. Rewrote the stale shebang line in all 82 affected `.venv/bin` scripts.
2. Fixed the stale `VIRTUAL_ENV` path in `activate`, `activate.csh`, `activate.fish` — these
   matter because CLAUDE.md tells users to `source .venv/bin/activate`.
3. Updated the cosmetic `command =` line in `pyvenv.cfg`.

Verified: zero remaining references to the old path anywhere under `.venv`; `pip --version`
and `pytest --version` both work; `make test-desktop` exits 0 with **611 pytest + 27 cargo +
416 vitest** all passing.

**No code changes** — `.venv/` is gitignored, so item 0 produced nothing committable beyond
this tracking file, and therefore no PR was opened for it.

**Carry-forward for future iterations:** the workaround in the loop prompt (`make test-desktop`
fails, invoke `.venv/bin/python3 -m pytest` directly) is now **obsolete**. Use
`make test-desktop` normally.

**Known fragility:** any future move of the repo directory reintroduces this exact problem.

### Item 1 — DONE (2026-07-31)

Wired `handlers/safety.py` (`fmea`, `fta`, `asil`, `sil`, `iec62304`) and added the `/safety`
page. The handler was fully written and unit-tested but never imported in `app.py`, so it was
absent from `_build_dispatcher` and every call returned -32601. `test_safety.py` could not
catch that — it imports the handler module directly and never crosses the dispatcher.

New `tests/test_registration_safety.py` closes that blind spot by driving the REAL NDJSON
event loop, the same approach `test_registration_activity_regulatory.py` already used for the
identical bug class. It failed with -32601 on all five methods before the fix.

**Two web-UI bugs deliberately NOT copied** (both pinned by tests so they can't creep in):

1. **FTA tree shape.** `web/src/pages/SafetyAnalysis.tsx:46` posts a FLAT `gates` list.
   `calculate_fta()` walks a NESTED tree (`{top_event, gate, children:[...]}`) and cannot read
   a flat list — it silently returns probability `0.0` and no cut sets. Desktop sends the
   nested tree. Every leaf carries BOTH `event` and `probability`, because the engine keys the
   probability roll-up off one and the cut sets off the other.
2. **Result field names.** The engine returns `asil`, `sil`, `safety_class`,
   `required_processes`. The web page reads `asil_level ?? classification` (line 311) and
   `sil_level ?? classification` (line 347) — *none* of which the engine ever emits, so the
   web ASIL and SIL tabs render blank. Desktop reads the real names.

Layers touched: `sidecar/app.py` (import + 5 registrations), new
`src-tauri/src/commands/safety.rs` + `mod.rs` + `lib.rs` invoke_handler, `api/types.ts`,
`api/client.ts`, new `hooks/useSafety.ts`, new `pages/Safety.tsx`, `App.tsx`, `Sidebar.tsx`,
`Header.tsx`.

Verified: `make test-desktop` exits 0 from the worktree — **618 pytest (+7), 27 cargo,
424 vitest (+8)** — plus `tsc --noEmit` clean.

**Still dead after this item:** `handlers/agentrun.py` is the other unimported module. That is
item 2, and unlike safety it is NOT a pure computation engine — `hire` is a HITL proposal kind
under SOUL.md Law 1 and must create a real ProposalStore proposal rather than execute.

### Item 2 — DONE (2026-07-31)

Wired `handlers/agentrun.py` (`run`, `hire`, `analyze_jd`, `get_project`). Unlike `safety`, this
needed real startup injection as well as registration: `_store`, `_project`, and
`_solution_name` in `_wire_handlers`.

**`agentrun` was dead in TWO layers, not one:**

1. The Python handler was never imported in `app.py` (same as `safety`).
2. `src-tauri/src/commands/agentrun.rs` **also already existed** but was missing from
   `commands/mod.rs`, so it never compiled — which is precisely why its RPC names had been
   allowed to drift to methods that exist nowhere: `agents.run`, `agents.hire`,
   `agents.analyze_jd`, `config.get_project`. Corrected to the `agentrun.*` names the
   dispatcher registers. (Keeping `agents.*` would have split one RPC namespace across two
   handler modules, and `config.get_project` would have opened a `config.*` namespace for a
   single method.)

**Wiring placement, deliberate:** `agentrun._solution_name` is set unconditionally next to
`yaml_edit._solution_name`, *not* inside the `ProjectConfig` try-block, so an `agent_hire`
proposal still names the right solution even if `ProjectConfig` fails to import —
`proposal_executor._execute_agent_hire` resolves which `prompts.yaml`/`tasks.yaml` to write
from that value.

**Law 1 coverage.** `test_registration_agentrun.py` drives the real NDJSON loop and asserts a
`hire` proposal appears in `approvals.list_pending` — i.e. `agentrun._store` is the *same*
store the inbox reads. A proposal created in some other store would pass all 21 existing unit
tests while being invisible to the human: an un-approvable HITL gate. Also pinned: `hire`
leaves `prompts.yaml` byte-identical (hash compared before/after), and `run` persists a real
proposal where the web API's `POST /agent/run` returns `status:"pending_review"` and stores
nothing.

**Test-fixture gotcha worth knowing.** `test_registration_activity_regulatory.py` passes a bare
`tmp_path` as `--solution-path`. That only works for handlers that never read solution YAML:
`_bootstrap_env` exports `SAGE_SOLUTIONS_DIR` as the solution path's **parent**, so a bare
tmp_path makes `ProjectConfig` resolve `<tmp>/<solution>/prompts.yaml`, which does not exist —
yielding zero roles *silently*, with no error. `agentrun` reads `prompts.yaml`, so its fixture
`shutil.copytree`s the real solution into tmp instead; YAML reads and `.sage/` writes both stay
inside tmp.

**Impedance mismatch, pinned by a test:** `agent_factory.jd_to_role_config` returns `role_key`,
but the hire payload takes `role_id`. Item 3's UI must map between them.

Frontend surface added for item 3 (no page yet): `AgentRunResponse` / `AgentRoleDraft` /
`HireAgentParams` / `ProjectConfigResult` types, four client functions, and `useAgentRun.ts`
(`useProjectConfig`, `useRunAgent`, `useHireAgent`, `useAnalyzeJobDescription`). `useHireAgent`
invalidates the approvals inbox but deliberately **not** the roster — the role is not live
until a human approves, and refreshing the roster would imply it already was.

Verified: `make test-desktop` exits 0 from the worktree — **625 pytest (+7), 27 cargo,
430 vitest (+6)** — plus `tsc --noEmit` clean.

### Item 3 — DONE (2026-07-31), scope corrected

**The backlog's two named references were both wrong**, verified before building:

- `web/src/pages/Analyst.tsx` (52 lines) is a log-analysis form → proposal card → approve
  buttons. It uses **no** agentrun endpoint. Desktop's existing `/analyze` page already does
  exactly this, and does it better (a real ProposalStore proposal vs the web `/analyze`
  endpoint's disconnected in-memory pending dict). A `/analyst` page would have been a pure
  duplicate, so none was built.
- `web/src/pages/Developer.tsx` (34 lines) is `MRCreateForm` + `MRReviewPanel` +
  `OpenMRsList` — i.e. the `/mr/*` operations, which are **backlog item 10**. It uses no
  agentrun endpoint either. Building it here would have pre-empted item 10.

All three agentrun consumers actually live in **`web/src/pages/Agents.tsx`** (`hireAgent`:227,
`analyzeJd`:258, `runAgent`:522). So item 3's *intent* — put a UI on the newly-wired RPCs — was
met by adding **Run** and **Hire** tabs to the existing `/agents` page, matching where the web
app puts them. No new route, no new nav entry.

**A real contract bug found and fixed.** `agent_factory` prompts the LLM for `task_types` as
OBJECTS (`{name, description}` — agent_factory.py:31), but `agentrun.hire` validates
`all(isinstance(t, str))` and rejects the entire payload otherwise. So an analyze→hire pipe
fails unless the UI maps between them. Item 2's `AgentRoleDraft.task_types: string[]` was
therefore wrong; it is now `Array<AgentTaskTypeDraft | string>` (widened because this is
unvalidated LLM output — the prompt asks for objects, nothing enforces it). New
`lib/taskTypes.ts::normalizeTaskTypes` handles both shapes and drops unusable entries rather
than emitting `undefined`; web's bare `t.name` (Agents.tsx:262) would yield `[undefined]` on a
string array and poison the whole hire.

Other deliberate choices:

- The Run tab's role list comes from `useProjectConfig` (prompts.yaml `roles:`), **not**
  `useAgents`. The latter is audit-annotated and also includes the four core roles, which
  `UniversalAgent.run` cannot dispatch to — offering one guarantees an "unknown role" error.
- Tabs render always; the roster's loading/error/empty states moved *inside* the Roster tab.
  Previously the page early-returned on an empty roster, which would have hidden the Hire tab
  in exactly the situation an operator most needs it (a solution with no agents yet).
- Both success banners say **"Awaiting human approval"** and the hire one states explicitly
  that nothing was written to prompts.yaml. Under Law 1 the role does not exist until approved,
  so any "created" copy would be false. Pinned by a test asserting `/role created/i` is absent.
- No `<Link>` to `/approvals`: the page currently renders without a Router in its tests, and
  adding one would have meant editing the four pre-existing roster tests. The sidebar's
  Approvals badge already increments (both mutations invalidate `approvalsKey`).

Verified: `make test-desktop` exits 0 — **625 pytest, 27 cargo, 443 vitest (+13)** — plus
`tsc --noEmit` clean.

**Carry-forward:** item 10 (`/mr/*`) is where `web/Developer.tsx`'s real content belongs. There
is no remaining reason to add a `/analyst` page.

### Item 4a — DONE (2026-07-31)

Import an EXISTING codebase as a solution. Added `onboarding.scan_folder` and
`onboarding.save_solution`, the Rust commands, typed client + `useScanFolder`/`useSaveSolution`,
and a new `ImportFlow` component behind an "Import a folder" tab on `/onboarding`
("Describe it" stays the default — it is the documented path, and importing only makes sense
when a codebase already exists).

Two RPCs, not one, deliberately: `scan_folder` drafts the YAML triad and **writes nothing**;
`save_solution` is the separate write. A test pins that scanning leaves the solutions dir empty,
so the operator always sees the drafts before anything hits disk. (`save_solution` is also what
4c/4d will need.)

**A THIRD web bug found — and this one is fatal.** `LLMGateway.generate` is
`generate(prompt, system_prompt=..., ...)` with **no `user_prompt` parameter and no
`**kwargs`**. But `api.py:4081` (`/onboarding/scan-folder`) and `api.py:4125`
(`/onboarding/refine`) both call `llm.generate(system_prompt=..., user_prompt=...)`. That raises
`TypeError` on **every** call, is swallowed by a bare `except Exception`, and is reported to the
user as HTTP 503 *"Could not reach the LLM."* Both web endpoints are dead on arrival — they have
never once succeeded, and the error message points at the wrong thing entirely. `api.py:811`
uses `prompt=` correctly, so it is isolated to these two call sites.

The sidecar calls `prompt=`, and `test_scan_folder_calls_generate_with_prompt` pins it: `FakeLLM`
mirrors the real signature exactly (no `**kwargs`), so a regression to `user_prompt=` raises
TypeError in the test instead of silently degrading.

**NOT fixed here:** `src/interface/api.py` is the web interface, outside this loop's desktop
scope, and touching it would pull in `tests/test_api.py` — a much larger verification surface
than this iteration's bar. It is a two-word fix (`user_prompt=` → `prompt=`) on both lines.
**Flagged for the operator as a follow-up.** Item 4c (refine) will hit the same bug at
api.py:4125 and should likewise implement it correctly rather than port it.

Other notes:

- `_solutions_dir()` reads `src.core.onboarding._SOLUTIONS_DIR` rather than re-deriving the
  path, so there is exactly one place that decides where solutions live. That module resolves
  `SAGE_SOLUTIONS_DIR` at import time, and `_bootstrap_env` sets it before any `src.` import.
- `save_solution` whitelists the three triad filenames (the LLM chooses those keys, so they are
  untrusted input) and re-checks the realpath against the solutions root — defence in depth
  against a symlinked solutions dir, on top of the name regex.
- `tsc --noEmit` earned its place in the bar again: vitest was fully green while
  `Onboarding.tsx` passed `{name}` to `useSwitchSolution`, which requires `{name, path}`.
  `save_solution` returns the path, so `onSaved` now threads both through.

Verified: `make test-desktop` exits 0 — **644 pytest (+19), 27 cargo, 450 vitest (+7)** — plus
`tsc --noEmit` clean.

### Item 4b — DONE (2026-07-31)

Org-template chooser. Added `onboarding.org_templates` (reads
`config/org_templates.yaml`, cached, degrades to `[]` if the file is missing), an `org_context`
passthrough on `onboarding.generate`, the Rust commands, typed client + `useOrgTemplates`, and
a new `OrgTemplateChooser` component in the Describe flow.

**The web chooser is dead code too.** `web/src/components/onboarding/OrgStructureChooser.tsx`
is 263 lines and **nothing imports it** — the `/onboarding/org-templates` endpoint exists and
the component exists, but they were never wired into the web wizard. So there was no reference
for how a chosen template should reach generation; that had to be designed here.

**How the choice actually takes effect:** `generate_solution` already has an `org_context`
parameter documented as *"prepended to description before LLM generation"* — exactly the right
hook. The chooser turns the enabled roles into a brief (`- <key> (<name>): <description>`) and
passes it as `org_context`, so the drafted prompts.yaml is steered by the template. **No
framework change was needed.** The template's `compliance_standards` are merged as a *union*
with whatever the operator typed — a template must not silently drop their entries.

Clicking the selected template again clears it: starting from no template is a valid choice and
there was otherwise no way back to it.

**A real page-crash bug found and fixed in `ErrorBanner`.** Its `describe()` switch had no
default branch, so any error whose `kind` is not in the `DesktopError` union returned
`undefined`, and destructuring `{title, detail}` threw — taking the **whole page** to a white
screen instead of rendering the error. This is reachable in production, not just in tests:
React Query raises its own errors (e.g. *"Query data cannot be undefined"* when a queryFn
resolves undefined, which happens if an RPC returns null) and those never pass through
`toDesktopError`. Added a guard plus two regression tests. Surfaced because the new chooser is
the first component on that page to own a `useQuery`.

Note for future iterations: `vi.resetAllMocks()` in a `beforeEach` **clears values configured in
the `vi.mock` factory**. A query mock must be re-established inside `beforeEach`, or its queryFn
resolves `undefined` and React Query errors.

Verified: `make test-desktop` exits 0 — **652 pytest (+8), 27 cargo, 459 vitest (+9)** — plus
`tsc --noEmit` clean.

### Item 4c — DONE (2026-07-31)

Conversational refine loop. Added `onboarding.refine`, the Rust command, `refineSolution` +
`useRefineSolution`, and a new `ReviewPanel` component that hosts the feedback→refine loop.
`ImportFlow` now renders it in place of its read-only preview, so refining is reachable from
the scan flow.

**Which flow "the refine loop" actually is.** Web has two candidates, and only one is real:

- `/onboarding/session`, `/session/{id}/message`, `/session/{id}/generate` — client functions
  exist, **zero component consumers**. Dead, like the org chooser.
- `/onboarding/refine` — consumed by `components/onboarding/ReviewPanel.tsx`, which
  `ImportFlow.tsx:74` renders. This is the live one, so it is what got ported.

**4c and 4d are the same component in web.** `ReviewPanel.tsx` hosts the refine loop *and* the
pre-write review. Split here as: 4c = the refine RPC + the loop inside a new `ReviewPanel`
(files still read-only); 4d = make the files editable and add Accept/Start-over, and wire the
panel into the Describe flow as well. Building the component boundary now avoids doing it twice.

**Same fatal `user_prompt=` bug as 4a**, at api.py:4125 this time — so
`/onboarding/refine` has never succeeded either, and web's ReviewPanel refine button has always
returned a misleading 503. The handler calls `prompt=`; `FakeLLM` mirrors the real signature so
a regression fails loudly. **Two web endpoints now confirmed dead from this one two-word
mistake** (4081 scan-folder, 4125 refine) — still flagged as an unfixed follow-up in `api.py`.

Deliberate behaviours, each pinned by a test:

- The loop genuinely loops: refine returns the same shape it takes, and the panel feeds the
  **refined** files into the next call, not the originals.
- Feedback clears on success only. Clearing on failure would force the operator to retype it;
  keeping it after success invites re-sending stale feedback against revised drafts.
- Accept hands back the **current** drafts, refinements included.
- A failed refine keeps the existing drafts rather than blanking them.

Test note: "old description" appears in both the summary and the rendered YAML, so
`getByText` throws on multiple matches — `getAllByText(...).length` is the right assertion.
That duplication is correct UI, not a bug.

Verified: `make test-desktop` exits 0 — **664 pytest (+12), 27 cargo, 468 vitest (+9)** — plus
`tsc --noEmit` clean.

### Item 4d — DONE (2026-07-31)

Pre-write review. The drafted YAML triad is now **editable** in `ReviewPanel` — the LLM's output
is a draft, and the operator is the last line of defence before it becomes a real solution.
Hand edits flow into both Accept and Refine, so feedback always applies to what is on screen.
Added an optional `onStartOver` (rendered only when the caller passes it) wired in `ImportFlow`
to discard the drafts and reset the save state.

**A genuine pre-write review is only possible in the Import flow.** `generate_solution`
(src/core/onboarding.py:318) creates `<solutions_dir>/<name>/` as part of generating, so by the
time the Describe flow could show a review, the solution is already on disk. The Import flow is
the one with a real gap between draft and write (`scan_folder` → review → `save_solution`), and
that is where the panel sits. Wiring it into Describe would require a draft-only generate — a
framework change, out of scope here. **Recorded as a known limitation, not silently skipped.**

**Editable files made a missing validation reachable, so it was added.** `save_solution` wrote
whatever it was handed; a hand-edited syntax error would produce a solution the framework cannot
load, failing much later and far from the cause. It now `yaml.safe_load`s **every** file before
writing **any** — all-or-nothing, because a half-written solution is worse than none — and names
the offending file in the error, since the operator has three open at once. Web's
`/onboarding/save-solution` has no such check.

Test note: the file name appears in both the `<summary>` and the field label, which made
`getByText` ambiguous. Fixed with `aria-label` on the textarea rather than a second visible
node — same accessibility, one match per query.

Verified: `make test-desktop` exits 0 — **667 pytest (+3), 27 cargo, 473 vitest (+5)** — plus
`tsc --noEmit` clean.

**Item 4 (onboarding) is now complete**: 4a import, 4b org templates, 4c refine loop, 4d
editable pre-write review.

### Items 5 + 6 — DONE (2026-07-31)

Six new RPCs — `org.{channel_create,channel_delete,route_add,route_delete,solution_set_parent,
solution_clear_parent}` — plus Rust commands, typed client, hooks, and an editable
routes/channels UI on `/organization`. The page previously showed cross-team routes read-only.

**Item 6 was a prerequisite, not a separate change.** Channels live in `org.yaml`, but routes
and parents live in each solution's **own** `project.yaml`. Writing those requires resolving the
solutions directory — so implementing item 5 against the old hardcoded `<sage_root>/solutions`
would have deliberately written to the wrong path for any solution mounted elsewhere. The new
`_solutions_dir()` honours `SAGE_SOLUTIONS_DIR` (either/or with the `<sage_root>/solutions`
default, matching the framework's own semantics) and is used by `org.yaml` resolution, the
`OrgLoader` route enrichment, and all six new handlers. The handler docstring, which previously
documented the gap as accepted, was updated. Two tests cover it directly.

Safety: `solution` arrives from the UI and becomes a path segment, so `_project_yaml_path()`
resolves and rejects anything escaping the solutions root (`../../etc`). `route_add` is
idempotent — re-adding an existing target is a no-op, not a duplicate entry.

**A real test-pollution bug found and fixed.** `test_org.py` passed alone but failed six tests in
a full run. Cause: `app._bootstrap_env` performs a genuine `os.environ[...] = ...` for
`SAGE_PROJECT` / `SAGE_SOLUTIONS_DIR` / `SAGE_SOLUTION_PATH` every time a test drives
`app.run()`, and **nothing restores it**. Any later test whose handler honours those vars then
resolves against a previous test's tmp dir. It was invisible until this change made the org
handler env-sensitive.

Fixed at the root with an autouse fixture in `tests/conftest.py` that clears those three vars
before each test and drops anything set during it. This removes a latent ordering-dependent
failure for every future env-sensitive handler, not just org — worth knowing for items 7-10.

Verified: `make test-desktop` exits 0 — **690 pytest (+23), 27 cargo, 478 vitest (+5)** — plus
`tsc --noEmit` clean.

### Item 7 — DONE (2026-07-31)

`/chat` — conversational agent plus history. New `handlers/chat.py` over
`src.core.chat_router` and a solution-scoped `ChatStore`
(`<solution>/.sage/chat_conversations.db`; the web API keeps one framework-global chat DB beside
the audit log). Five RPCs (`chat.{send,list_conversations,get_conversation,delete_conversation,
clear_history}`), Rust commands, typed client, `useChat.ts`, and a `/chat` page with a
conversation sidebar.

**`POST /chat/execute` is deliberately NOT ported, and this is the important divergence.** The
web API executes a chat-proposed action directly, gated only by a confirm button in the chat UI.
Here, when the router returns `type: "action"`, the handler persists a **real ProposalStore
proposal** (`action_type: "chat_action"`, `RiskClass.STATEFUL`) and the operator decides in the
Approvals inbox — same store, queue and audit trail as every other agent proposal (Law 1; the
pattern already used by `analyze.run` and `agentrun.run`).

That is both safer and *smaller*: `/chat/execute` reimplements ~150 lines of action dispatch that
`proposal_executor` already owns, so porting it would have put execution logic in a second place.
The UI banner says "Action queued for approval… nothing has run", pinned by a test — claiming it
ran would be false.

Only actions create proposals; a plain answer must not spam the inbox (also tested). `chat.send`
invalidates the approvals cache only when a proposal came back, so the sidebar badge moves the
moment chat queues something.

Streaming stays deferred as agreed — `POST /chat` is explicitly the non-streaming path, which is
what this mirrors.

Note: `chat_router.route` calls `llm_gateway.generate(prompt, system_prompt=...)` **positionally**,
so it does *not* carry the `user_prompt=` bug that kills `/onboarding/scan-folder` and
`/onboarding/refine`.

Verified: `make test-desktop` exits 0 — **707 pytest (+17), 27 cargo, 486 vitest (+8)** — plus
`tsc --noEmit` clean.

### Item 8 — DONE (2026-07-31)

`/code` — plan → approve → execute over `src.integrations.autogen_runner`. New
`handlers/code.py`, five RPCs, Rust commands, typed client, `useCode.ts`, and a `/code` page.

**Not a Law 1a conflict, checked before building.** Law 1a (Merge-Gate) governs *merging*
agent-written code to `main` — agents own the branch, the human approves the MR, and
`code_diff`/`implementation_plan` are internal branch steps rather than standalone gates. This
endpoint governs something different: *executing a generated script right now*. Its approval gate
is legitimate and, importantly, enforced inside `autogen_runner.execute()` itself — an unapproved
run is refused by the runner, not merely hidden by the UI. A test pins that.

**One addition with no web equivalent: `code.sandbox_status`.** `autogen_runner` runs code in
`docker run --rm --network none`, but falls back to a **local subprocess with no isolation** when
Docker is unavailable (autogen_runner.py:200-201). The web API only reveals that in the *execute
result* — i.e. after the generated code has already run on the operator's machine. The desktop
page queries isolation on mount and shows a red `role="alert"` banner *above* the approve button,
so the operator knows what they are authorising while deciding. Pinned by a test asserting the
warning appears before any Approve button exists.

`autogen_runner` signals failure by returning `{"error": ...}` rather than raising, so `_unwrap()`
checks every call — otherwise a refused execution would look like success.

Known limitation, matching the web API: the runner keeps runs in memory, so a sidecar restart
loses pending plans. Acceptable — an un-executed plan is cheap to regenerate.

Test note: `/hi/` matched both the stdout and the drafted `print('hi')`, and the plan text
overlapped the typed task. Assertions now key off unambiguous anchors (the Approve button, the
`exit 0` line).

Verified: `make test-desktop` exits 0 — **724 pytest (+17), 27 cargo, 494 vitest (+8)** — plus
`tsc --noEmit` clean.
