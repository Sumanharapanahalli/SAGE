# SAGE Agent Gym — Benchmark

**What this is:** the gym is SAGE's only source of GROUND TRUTH about agent quality.
An agent plays a real exercise; the output is mechanically graded (did it execute?
did it produce artifacts?); a cross-vendor critic panel scores it; the agent reflects;
a Glicko rating moves. These are measurements, not model opinions.

**Sessions:** 6 (3 completed, 3 errored)  
**Critic panel:** gemini, ollama, primary  
**Mean graded score:** 73.2/100

| Role | Exercise | Skill | Graded | Passed | Critic scores | Elo |
|---|---|---|---|---|---|---|
| developer | `ope-b03` | brainstorming | 80.4 | yes | primary:72, ollama:75, gemini:50 | 1400.6→1454.6 |
| developer | `ope-b04` | brainstorming | 91.2 | yes | primary:72, ollama:75, gemini:72 | 1454.6→1479.6 |
| analyst | `ope-b01` | technical_writing | 47.9 | no | gemini:48, primary:62, ollama:40 | 1000.0→965.1 |
| analyst | — | — | ERROR | — | — |  |
| planner | — | — | ERROR | — | — |  |
| planner | — | — | ERROR | — | — |  |

## What the agents said they got wrong

These are the agents' own reflections after seeing the critics — the compounding
signal (Law 3). They are the highest-value input to the optimizer.

**developer / `ope-b03`**  
The 80.4 score masks real gaps. Three stand out as genuine mistakes, not just missed polish: (1) I left slugify() without a None guard while truncate() and sanitize_html() both had one — inconsistency in a single module is a design smell I should have caught in review before submitting. (2) The Test  
  - Before submitting any utility function, scan every sibling function for None guards and ensure consistency — if two of three functions guard None, the third must too, or the asymmetry must be documented explicitly.
  - Run the test file locally (or mentally trace collection) before finalizing — a class body that's cut off is a SyntaxError that silences the entire suite, which is worse than a failing test.
  - Name tests after the actual input, not the intended equivalence: 'test_none_input_raises_type_error' not 'test_none_equivalent_empty_string'. The name forces me to write the correct assertion.

**developer / `ope-b04`**  
I scored 91.2 overall but the critic panel correctly identified real runtime failures that the LLM judge glossed over. Three concrete mistakes: (1) I used exec-form HEALTHCHECK with `${PORT}` — exec-form never invokes a shell, so the variable was passed literally to curl and every health check would  
  - Before submitting any Dockerfile, walk every RUN/CMD/HEALTHCHECK line and ask: does this require a shell? If yes, use shell-form or `sh -c`. Never use `${VAR}` in exec-form — write the port hardcoded or wrap in `sh -c`.
  - For every file referenced in the Dockerfile (COPY targets, CMD entrypoints, npm build scripts), verify the file exists in the diff. Treat a dangling reference as a build failure, not a minor omission.
  - Match runtime OS packages to Python requirements.txt exactly. If libpq5 is installed, psycopg2-binary must be in requirements.txt. If it is not, remove the OS package. No orphaned dependencies.

**analyst / `ope-b01`**  
I failed primarily on structural and format compliance, not content knowledge. The core mistakes were: (1) delivering a YAML schema when the criterion explicitly said 'valid JSON Schema' — I defaulted to YAML because it's OpenAPI's canonical form without checking the literal requirement; (2) the cur  
  - Read acceptance criteria word-for-word before generating output — if the criterion says 'valid JSON Schema', produce JSON, not YAML, even if YAML is technically equivalent in the OpenAPI spec
  - Always render the curl example as a fenced bash code block in the document body, immediately after the endpoint description — never relegate it to a table or summary section
  - Include `operationId` in every OpenAPI path object snippet to make fragments self-contained and machine-parseable

