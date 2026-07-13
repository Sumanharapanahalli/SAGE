# SAGE Agent Gym — Benchmark

**What this is:** the gym is SAGE's only source of GROUND TRUTH about agent quality.
An agent plays a real exercise; the output is mechanically graded (did it execute?
did it produce artifacts?); a cross-vendor critic panel scores it; the agent reflects;
a Glicko rating moves. These are measurements, not model opinions.

**Sessions:** 5 (5 completed, 0 errored)  
**Critic panel:** gemini, ollama, primary  
**Mean graded score:** 55.7/100

| Role | Exercise | Skill | Graded | Passed | Critic scores | Elo |
|---|---|---|---|---|---|---|
| marketing_strategist | `ope-b01` | product_strategy | 59.6 | yes | gemini:60, primary:62, ollama:65 | 1000.0→1414.8 |
| product_manager | `ope-b01` | product_strategy | 61.4 | yes | gemini:61, primary:62, ollama:61 | 1000.0→1403.4 |
| ux_designer | `ope-b01` | ux_design | 42.6 | no | gemini:42, primary:42, ollama:42 | 1000.0→971.9 |
| technical_writer | `ope-b01` | technical_writing | 53.6 | yes | gemini:53, primary:42, ollama:50 | 1000.0→1451.0 |
| developer | `ope-b05` | brainstorming | 61.2 | yes | gemini:0, primary:35, ollama:61 | 1479.6→1538.0 |

## What the agents said they got wrong

These are the agents' own reflections after seeing the critics — the compounding
signal (Law 3). They are the highest-value input to the optimizer.

**marketing_strategist / `ope-b01`**  
The core personas and JTBD structure were solid — differentiated, grounded in real signals, all four JTBD dimensions covered. But the output failed on execution rigor: market sizing rows were unlabeled tiers with no funnel methodology, WTP figures were asserted rather than anchored to comparables, a  
  - Always label market sizing rows explicitly as TAM / SAM / SOM and add a one-sentence methodology note per persona explaining the funnel logic (e.g., 'Top-down: BLS headcount → bottom-up reachability filter → 5% early-adopter SOM')
  - Never assert a WTP figure without a single analogous SaaS benchmark anchor — even one comparable (Sentry $156/mo, Linear $8/seat/mo, Retool $10/mo) makes the number credible rather than a guess
  - Add a 'By When / Success Metric' column to every action item table — a what without a when and a measurable outcome has near-zero PM utility

**product_manager / `ope-b01`**  
The 61/100 score reflects three compounding failures, not one. First, the document was physically truncated — Persona 3 never appeared in the output, which is a basic delivery failure that alone should have failed the exercise. I either hit a token limit without noticing or didn't verify the artifac  
  - Verify completeness before submitting: after generating any structured document, explicitly count the required sections (e.g., 'Persona 1 ✓, Persona 2 ✓, Persona 3 ✓') and confirm no sentence is mid-truncated before treating the artifact as done.
  - Name the sizing framework explicitly in a header row: label columns TAM / SAM / SOM and define each boundary in one sentence (e.g., 'SAM = English-speaking, regulated-industry teams with ≥5 engineers and existing CI/CD'). Never leave the hierarchy implicit.
  - Anchor every sizing row to a citable primary source: for engineers use BLS OES code 15-1252 + EU EUROSTAT equivalent with survey year; for mobile developers use the Apple press release developer count; for compliance roles use LinkedIn title-search methodology. Inline the citation, not just the number.

**ux_designer / `ope-b01`**  
The most damaging failure was entirely self-inflicted and avoidable: I truncated the JSON output mid-value, making the entire artifact unparseable. This single mistake blocked all downstream automated checks and was the primary cause of the 0/1 experimental score. Beyond that, I treated the exercise  
  - Before submitting any JSON artifact, validate it with json.loads() mentally or write it to a temp string and parse it — never truncate output mid-token; if output is long, split across multiple files rather than cutting off.
  - Read every acceptance criterion literally before generating content — treat each bullet as a checklist item and confirm it is present in the artifact before finishing.
  - Add a 'Skip for now' TextLink explicitly on screens 1, 2, and 3 in the wireframe spec, and include a navigation-flow.md file that traces Skip → destination screen for each.

**technical_writer / `ope-b01`**  
The submission had a fundamental completeness failure: the output was truncated on disk or in submission, meaning the curl example and 400/401/500 response schemas were either missing or cut off before delivery. This is the single biggest gap — scoring 20/100 on experimental checks because the curl   
  - Always verify the complete file on disk before submission — read it end-to-end and confirm all acceptance criteria are visibly present: curl block, all four response codes, all schema shapes.
  - Write the curl example first, immediately after the request body, before anything else — it is the highest-weight acceptance criterion and the easiest to forget when writing top-down.
  - Enumerate all four required response codes (200, 400, 401, 500) as a checklist before starting to write; check each off explicitly rather than assuming coverage from top-down flow.

**developer / `ope-b05`**  
The core failure was confusing narrative with deliverable. I described a well-structured solution — frozen dataclass, bulk error reporting, whitespace validation, .env.example — but never actually emitted any of those artifacts. The files list was empty, no code blocks were produced, and reviewers h  
  - Emit actual files first, reflection second. For any coding exercise, the first output should be the code blocks themselves — config.py, .env.example, test file — not a description of what they will contain.
  - Use a self-check before returning: verify that the files list is non-empty and that every file mentioned in the narrative has a corresponding code block in the output. If files is empty and status is completed, that is a bug to fix before finishing.
  - Write the test file as part of the exercise, not as an afterthought. Cover the four required cases explicitly: missing required var raises at startup, whitespace-only var is rejected, all defaults resolve correctly, and the happy path loads without error.

