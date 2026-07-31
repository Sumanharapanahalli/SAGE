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
| 1 | Wire dead handler `sidecar/handlers/safety.py` + `/safety` page | TODO |
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
