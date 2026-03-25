# IP67 Sealing Strategy — Wearable Fall-Detection Unit

**Revision:** 1.0  **Date:** 2026-03-21
**Standard:** IEC 60529 — IP67 (dust-tight, immersion to 1m / 30 min)
**Applicable standards:** IPC-CC-830C (conformal coating), IPC-2221B (PCB design)

---

## 1. IP67 Requirements Recap

| Code | Protection level | Test |
|------|-----------------|------|
| IP6x — Dust | Dust-tight, no ingress | 8 h at 2 Pa negative pressure, <150 µm dust |
| IPx7 — Water | Immersion 1 m depth for 30 min | 125 mbar external pressure |

---

## 2. Enclosure Design Strategy

### 2.1 Housing Construction

```
┌──────────────────────────────────────┐
│  Top shell (PC/ABS, 1.2mm wall)      │
│  ┌────────────────────────────────┐  │
│  │  PCB assembly (38x38mm)       │  │
│  │  [conformal coated]           │  │
│  └────────────────────────────────┘  │
│  Silicone O-ring gasket ─────────┐   │
│  Bottom shell (PC/ABS, 1.2mm)    │   │
└──────────────────────────────────┘   │
         ↑ compression gasket groove
         groove width: 2.5mm
         O-ring cross-section: 1.5mm
         compression: 15-20%
```

**Material:** Polycarbonate + 10% ABS blend (PC/ABS), UV-stabilized
**Surface finish:** Matte texture, Ra 0.8–1.2 µm at seal groove
**Fastening:** 4× M2 stainless screws (H1–H4 PCB mounting holes) + snap-lock retention

### 2.2 O-Ring Specification

| Parameter | Value |
|-----------|-------|
| Material | Silicone VMQ 70 Shore A |
| Cross-section | 1.5 mm |
| Perimeter path | Follows 38×38mm board outline |
| Groove depth | 1.2 mm (80% fill, 15% compression) |
| Groove width | 2.0 mm |
| Temperature range | -40°C to +120°C |
| Part reference | Parker VMQ70 custom profile or equivalent |
| Surface roughness at groove | Ra ≤ 0.8 µm |

### 2.3 USB-C Port Sealing

- GCT USB4125-GF-A has integral IP67 flange seal at PCB level
- Silicone plug/cap provided for USB-C opening when not in use
- **Production option:** Replace USB-C with 5-pin magnetic pogo charging connector (IPX8) — pads already routed to PCB edge

### 2.4 SOS Button Sealing

SW1 (PTS526SM15) rated IP67 standalone. Additional housing seal:
- 0.4mm TPE membrane over actuator (Shore 45A), co-molded with housing
- Membrane provides tactile feedback through enclosure wall
- Tested: 1M actuation cycles with seal intact

### 2.5 Strap Interface

- External lug design — no through-holes penetrate the sealed cavity
- Strap mounts on external bosses; water path has no entry point

---

## 3. PCB Conformal Coating

### 3.1 Material

| Property | Value |
|----------|-------|
| Type | Acrylic AR — MG Chemicals 419D |
| Thickness target | 50 µm (2 passes) |
| Accept range | 30–75 µm |
| Dielectric strength | 2800 V/mil |
| IPC compliance | IPC-CC-830C Type AR |
| UV fluorescence | Yes (365nm inspection) |

### 3.2 Masking (must mask before spray)

| Area | Ref | Method |
|------|-----|--------|
| USB-C contacts | J1 | Peelable latex plug |
| LiPo connector | J3 | Peelable latex plug |
| SWD header | J2 | Peelable latex plug |
| GPS module window | ANT2 | Pre-applied Kapton tape |
| LTE antenna feed trace | ANT1 | Kapton strip |
| BQ25895 thermal pad | U5 | Kapton tape |
| Test points TP1–TP8 | — | Precision sticker dot |

### 3.3 Application Process

```
1. Ultrasonic clean (MPC-400 flux removal) → DI rinse → 60°C oven 30 min
2. Apply all masking
3. Spray pass 1: 30 cm distance, 45° angle, cross-hatch → 25 µm
4. 15 min ambient cure
5. Rotate 180°, spray pass 2 → total 50 µm
6. 60°C oven cure 30 min
7. UV lamp inspection (365 nm) — verify full coverage, no bridges on connectors
8. Peel all masking
9. Electrical functional test
```

---

## 4. IP67 Qualification Tests

### Dust (IP6x)
8 h, silica <150 µm, 2 Pa negative pressure, 5-unit sample.
Pass: no ingress; all electrical functions nominal post-test.

### Immersion (IPx7)
1.0 m fresh water, 23°C, 30 min. Remove, dry externally, functional test within 30 min.
Pass: no water ingress; full MCU/GPS/LTE/IMU/LED/haptic functionality confirmed.

### Thermal Cycling (complementary)
-20°C ↔ +60°C, 30 min dwell, 50 cycles. IP67 retest must pass afterwards.

---

## 5. Production Assembly Sequence

```
1.  PCB SMT + reflow
2.  Conformal coat (Section 3.3)
3.  PCB functional test
4.  Install LRA motor (flex cable to J_HAPTIC)
5.  Place PCB in bottom shell on thermal standoffs
6.  Route LiPo cable; connect J3
7.  Dry-fit O-ring into groove (no grease needed: silicone-on-silicone)
8.  Close top shell; torque M2 screws 0.35 N·m (diagonal sequence 1-3-2-4)
9.  Visual confirm O-ring seated fully around perimeter
10. Attach wristband straps
11. IP67 immersion sample test (1-per-50 production)
12. LTE/GPS power-on registration test
13. Label, pack
```

---

## 6. Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| USB-C cap lost by user | High | Secondary magnetic charging option in BOM |
| O-ring compression set (>3 yr) | Medium | VMQ silicone rated 10-yr automotive; annual inspection recommended |
| Conformal coat crack at -40°C | Low | Acrylic AR type remains flexible; tested to -40°C per IPC-CC-830C |
| SOS button membrane fatigue | Medium | TPE Shore 45A, 0.4mm, 1M-cycle rated |
| GPS antenna de-tuned by housing dielectric | Low | Antenna tuned inside assembled housing; keep-out maintained in PCB layout |
