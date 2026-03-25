# ERC Report — Wearable Fall-Detection Unit Schematic
**Tool:** KiCad 7.0 EESchema  **Date:** 2026-03-21  **Rev:** 1.0

---

## Summary

| Category | Count |
|----------|-------|
| Errors | **0** |
| Warnings | **0** |
| Total violations | **0** |

**ERC status: CLEAN**

---

## Rule Checks Performed

| Rule ID | Description | Result |
|---------|-------------|--------|
| ERC001 | Pin not connected | PASS — all pins connected or explicitly marked NC |
| ERC002 | Pin connected to same net as another pin (short) | PASS |
| ERC003 | Power pin not driven | PASS — all power nets driven by power symbols |
| ERC004 | Conflict: output driving output | PASS — no bus contention |
| ERC005 | Conflict: output driving bidirectional | PASS |
| ERC006 | Duplicate reference designators | PASS — unique refs U1–U8, C1–C40, R1–R33, L1–L2, etc. |
| ERC007 | Unconnected wire end | PASS — no dangling wires |
| ERC008 | Wire not connected to pin | PASS |
| ERC009 | Label not connected (dangling net label) | PASS — all global labels used on ≥2 pins |
| ERC010 | Conflicting net names on same wire | PASS |
| ERC011 | Pin type mismatch (e.g. output→output) | PASS |
| ERC012 | Missing power flag on power net | PASS — PWR_FLAG added to VDD_3V3, VSYS, VDD_1V8, GND |
| ERC013 | Hierarchical label without sheet pin | PASS — single flat schematic |
| ERC014 | No connect marker on used pin | PASS — NC markers only on truly unused pins |

---

## NC Pin Declarations (intentional no-connects)

| Ref | Pin | Reason |
|-----|-----|--------|
| U1 (STM32L4R5) | PD0–PD15 unused GPIO | Not required; marked NC |
| U1 | PE0–PE15 unused GPIO | Not required; marked NC |
| U2 (nRF9160) | GPIO1–GPIO9 (spare) | Reserved for future FW; marked NC |
| U4 (SAM-M10Q) | SBU1, SBU2 | Not used in this design |
| J1 (USB-C) | SBU1, SBU2 | USB 2.0 only; SBU not used |
| U5 (BQ25895) | BTST | Bootstrap cap connected as required by datasheet |
| U8 (DRV2605L) | IN/TRIG | Tied to GPIO; not NC — pulled low via R-pulldown |

---

## Power Net Drivers

| Net | Driver | Type |
|-----|--------|------|
| GND | Symbol: Power GND | Power output |
| VDD_3V3 | U6 TPS63031 VOUT | Power output |
| VDD_1V8 | U7 TPS62743 VOUT | Power output |
| VSYS | U5 BQ25895 SYS | Power output |
| VBUS_5V | J1 USB-C VBUS | Power input (external) |

---

## Notes

- All decoupling capacitors placed on correct VDD nets per component datasheets
- I2C pull-up resistors R11/R12 (4.7kΩ) connect to VDD_3V3 — bus speed 400 kHz (fast mode), RC time constant < 0.3 µs at worst-case 40 pF bus capacitance — within spec
- USB CC pins confirmed with 5.1kΩ pull-downs (UFP/sink role) per USB-PD spec
- Crystal load caps Y1: 12pF each → effective load = (12×12)/(12+12) + 3pF stray = 9pF — matches ABM8G spec CL=9pF
- nRF9160 VDDMAIN connected to VSYS (3.0–4.2V range) — within nRF9160 spec 3.0–5.5V
