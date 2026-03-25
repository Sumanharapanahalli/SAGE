# Elder Fall Detection — Wearable Hardware Design Package

Form factor: Wristband, ≤50 mm × 40 mm × 12 mm
IP rating: IP67
Design revision: v1.0
Date: 2026-03-22

## Artifact Index

| File | Description |
|------|-------------|
| `schematic/schematic_description.md` | Full schematic narrative, net list, ERC checklist |
| `schematic/netlist.csv` | Machine-readable net connections |
| `BOM_v1.csv` | Bill of Materials with MPN, distributor, pricing |
| `pcb_layout_constraints.md` | Layer stack, keepouts, placement rules, DFM notes |
| `power_budget_analysis.md` | Per-rail current draw, battery life model |

## Component Summary

| Role | Part | Package |
|------|------|---------|
| MCU | STM32L476RGT6 | LQFP-64 |
| IMU | LSM6DSO | LGA-14L |
| GPS | u-blox CAM-M8C | LCC-18 |
| Cellular | SIM7080G | LCC-88 |
| BLE SoC | nRF52840-QIAA | QFN-73 |
| Battery Mgmt IC | BQ25180YFPR | DSBGA-9 |
| Li-Po cell | 300 mAh / 3.7 V | 402035 |

## Quick-Start Review Checklist

- [ ] ERC: zero errors, zero warnings (see schematic_description.md §ERC)
- [ ] All power rails annotated with voltage + max current
- [ ] BOM pricing confirmed with distributor quotes
- [ ] Power budget confirms ≥72 h typical battery life
- [ ] PCB keepout zones defined for all RF components
- [ ] Signal integrity review signed off
- [ ] EMC pre-compliance checklist completed
