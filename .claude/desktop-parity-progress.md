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
| 2 | Wire dead handler `sidecar/handlers/agentrun.py` (HITL for `agent_hire`) | TODO |
| 3 | Add `/analyst` and `/developer` pages over agentrun RPCs | TODO |
| 4a | Onboarding: scan-folder import of existing codebase | TODO |
| 4b | Onboarding: org-template chooser | TODO |
| 4c | Onboarding: conversational refine loop | TODO |
| 4d | Onboarding: pre-write ReviewPanel | TODO |
| 5 | Extend `org.*`: channels CRUD, cross-team routes (writable), solutions CRUD | TODO |
| 6 | Fix `/organization` ignoring `SAGE_SOLUTIONS_DIR` | TODO |
| 7 | Add `/chat` (conversational agent + history) | TODO |
| 8 | Add `/code` (plan / execute / approve) | TODO |
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
