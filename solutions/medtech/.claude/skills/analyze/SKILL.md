---
name: analyze
description: >
  Analyze a medtech firmware log, error report, or production alert using
  domain context. Use when the user pastes a crash dump, UART log, flash
  error, or CI failure and wants a structured diagnosis. $ARGUMENTS is the
  raw log/error text to analyze.
user-invocable: true
allowed-tools: Bash
---

Analyze the following medtech / embedded firmware log using domain context:

```
$ARGUMENTS
```

## Analysis framework

Apply this reasoning sequence:

1. **Identify the subsystem** — UART/serial, NAND flash, BLE stack, FreeRTOS scheduler,
   bootloader, J-Link/SWD, or CI pipeline.

2. **Classify severity:**
   - **RED** — production line stopped, device bricked, patient risk, data loss
   - **AMBER** — degraded function, intermittent failure, known workaround exists
   - **GREEN** — cosmetic, logging noise, non-blocking

3. **Root cause hypothesis** — cite the specific register, memory address, task name,
   assertion, or stack frame if present. Reference IEC 62304 fault categories where
   applicable (software unit failure, integration failure, requirements gap).

4. **Recommended action** — be specific: which file, which function, which test to add.
   If a GitLab issue exists, say "create issue referencing this trace."

5. **Spira traceability** — if the fault maps to a known requirement, note the Spira ID
   format: `REQ-xxx` or `TC-xxx`.

## Output format

Respond with a structured report:

```
SEVERITY: RED | AMBER | GREEN
SUBSYSTEM: <name>
ROOT CAUSE: <hypothesis>
EVIDENCE: <specific lines from the log>
RECOMMENDED ACTION: <concrete next step>
SPIRA LINK: <REQ/TC ID if applicable, else N/A>
```

If the log is too short or ambiguous to diagnose, ask one specific clarifying question.
