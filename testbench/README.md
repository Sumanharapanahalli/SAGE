# SAGE Test Bench — one generic bench for any solution

A config-driven, pluggable test bench. A solution declares **what** to test in a
`testbench.yaml`; the bench runs the declared suites via pluggable **drivers** and
produces one report. Works across project types — **web/API, mobile, or embedded**.

It generalizes the bespoke harnesses built for the Poseengine product (acceptance,
load, browser) into a reusable capability every SAGE solution inherits.

## Run

```bash
# by config file
python testbench/run.py --config testbench/configs/poseengine.yaml --report out.md

# by solution (uses solutions/<name>/testbench.yaml, else testbench/configs/<name>.yaml)
python testbench/run.py --solution poseengine

# a subset of suites
python testbench/run.py --solution poseengine --suite api,load
```

## Drivers

| Driver | What it does | For |
|---|---|---|
| `api` | health + read routes + auth flow + auth-gated routes + optional websocket | any REST/HTTP backend (framework, product, device control-plane) |
| `load` | N concurrent user journeys + a read-throughput burst | any HTTP backend |
| `browser` | headless-Chromium UI smoke — every view renders, no console errors, click+assert interactions | web UIs |
| `mobile` | runs the app's test suite (Flutter today; in Docker so no local SDK) | mobile solutions |
| `embedded` | firmware host unit tests (CMake/CTest…) + a HIL extension point (serial / J-Link via SAGE MCP) | embedded/firmware solutions |

`api`/`load` are **stdlib-only** (urllib + threads) — zero install footprint.
`browser` needs Node + Playwright (point `playwright_dir` at a `node_modules/playwright`).
`mobile`/`embedded` shell out to the project's own test command (optionally in Docker).

## Config shape (`testbench.yaml`)

```yaml
project: my_solution
suites:
  api:      { base_url: "...", health: [...], reads: [...], auth: {...}, protected: [...], ws_chat: {...} }
  load:     { base_url: "...", users: 20, journey: [...], burst: {endpoint: "...", n: 200} }
  browser:  { url: "...", playwright_dir: "...", views: [...], interactions: [...] }
  mobile:   { kind: flutter, test_cmd: "flutter test", docker_image: "..." }
  embedded: { unit_test_cmd: "ctest ...", cwd: "...", hil: {transport: jlink, port: "..."} }
```

A suite is skipped if absent or `enabled: false`. See `configs/poseengine.yaml`
(mobile + web) and `configs/_embedded.example.yaml` (firmware + HIL).

## Adding a driver

Drop `drivers/<name>.py` exposing `run(cfg: dict) -> {passed, failed, skipped, checks:[{name,status,detail}], note}`
and register it in `run.py`'s `DRIVERS`. (Node-based drivers: a thin Python wrapper
shells out, like `browser.py` → `browser.mjs`.)

## How a solution opts in

Add a `testbench.yaml` next to its `project.yaml`. The bench is the same for every
solution — only the config differs. This is the "AI test bench" as a reusable SAGE
capability, not a per-project script.
