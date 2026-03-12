# SOUL.md — medtech solution

## What This Solution Is

This is the **reference implementation** of a SAGE solution for ISO 13485-compliant
medical device manufacturing. It exists for two purposes:
1. As a working production configuration for a real manufacturing environment
2. As the canonical example for anyone building their own SAGE solution

Every prompt, task type, and integration in this solution reflects the actual needs
of a regulated medical device software team — not a demo, not a toy.

---

## Domain Context

Medical device software is governed by:
- **ISO 13485:2016** — quality management system for medical devices
- **IEC 62304:2006+AMD1** — software lifecycle for medical device software
- **ISO 14971:2019** — risk management
- **FDA 21 CFR Part 11** — electronic records and signatures

In practice this means:
- Every AI action must be logged to an immutable audit trail
- AI may only *propose* — a qualified human must *approve*
- Changes to software must be traceable from requirement to test (RTM)
- Any autonomous action that touches the device software must be risk-assessed

When working on this solution, never suggest removing or shortcutting any of these.

---

## Agents in This Domain

**AnalystAgent** — Triages firmware crash logs, UART output, flash error reports.
Must identify severity (RED/AMBER/GREEN), root cause hypothesis, and recommended action.
Context: STM32H7 MCU, FreeRTOS, BLE stack, NAND flash, bootloader.

**DeveloperAgent** — Reviews GitLab MRs against IEC 62304 software change control.
Checks: static analysis findings, unit test coverage, traceability to requirements (Spira).

**MonitorAgent** — Polls Teams channels for production alerts, Metabase for error trends,
GitLab for failed CI pipelines.

**PlannerAgent** — Orchestrates multi-step tasks: e.g. "investigate issue #45" →
fetch issue → search memory → analyze → propose fix → create MR → request review.

---

## What to Be Careful About Here

- **Severity classification is safety-critical.** RED means production line down or
  patient risk. Never downgrade a RED to AMBER without human confirmation.
- **Spira traceability links must be preserved.** Every MR description must reference
  the Spira requirement ID.
- **Flash/bootloader errors are high risk.** A wrong firmware flash recommendation
  can brick a device on the manufacturing line.
- **This solution's prompts.yaml is MIT-licensed** and can be publicly shared.
  Don't put any real device-specific IP in the prompts.

---

## Running This Solution

```bash
make run PROJECT=medtech        # backend on :8000
make ui                         # frontend on :5173
make test-medtech               # 32 solution tests
```
