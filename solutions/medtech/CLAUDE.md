# medtech solution — Claude Code Instructions

@.claude/SOUL.md

## Available Skills

| Skill | Usage |
|---|---|
| `/analyze` | Analyze a firmware log: `/analyze <paste log here>` |
| `/run-solution-tests` | Run medtech IQ/OQ/PQ and e2e tests |

## Key Files

```
project.yaml    Domain metadata, active_modules, compliance standards
prompts.yaml    Agent prompts — analyst triages STM32H7/FreeRTOS/BLE faults
tasks.yaml      Task types: ANALYZE_LOG, ANALYZE_FLASH_ERROR, ANALYZE_BLE_ERROR, ...
tests/          IQ/OQ/PQ validation tests + e2e MR workflow tests
```

## Quick Start

```bash
make run PROJECT=medtech    # backend
make ui                     # frontend
make test-medtech           # tests
```
