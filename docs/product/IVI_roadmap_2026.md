# IVI System — Release Roadmap 2026–2027

```
Q1 2026         Q2 2026         Q3 2026         Q4 2026         Q2 2027
|               |               |               |               |
[PROGRAM KICKOFF]
  SoC selection locked
  OEM HAL docs received
  Licensing negotiations
  (Spotify/Apple/YouTube)
                |
                [M1: FOUNDATION — Jun 30]
                  AAOS 13 platform stable
                  Boot < 4 s KPI hit × 1,000 cycles
                  VHAL CAN integration 100% pass
                  OTA security infrastructure
                  GMS pre-audit submitted
                                |
                                [M2: CONNECTED — Sep 30]
                                  Voice assistant (12 languages, P95 < 800 ms)
                                  Offline+online navigation (route < 3 s)
                                  Spotify + YouTube Music + Apple Music (DRM L1)
                                  GMS certification received
                                  OTA A/B partition tested
                                                |
                                                [M3: PRODUCTION — Dec 15]
                                                  Fleet OTA ≥ 99.5% (10k vehicles)
                                                  UN R155/R156 type approval submitted
                                                  ISO 26262 ASIL-B safety case signed
                                                  NHTSA MEAL compliance 100%
                                                  OEM homologation package complete
                                                                |
                                                                [M4: ENHANCEMENT — Jun 2027]
                                                                  AR overlay navigation
                                                                  Rear seat entertainment
                                                                  Custom wake-word enrollment
                                                                  Fleet telemetry-driven tuning
```

## Milestone Summary Table

| Milestone | Date | Gate Owner | P0/P1 Defects | Key Exit Criterion |
|---|---|---|---|---|
| M1: Foundation | 2026-06-30 | Engineering Lead | Zero | Boot < 4 s × 1,000 cycles; VHAL 100% pass |
| M2: Connected | 2026-09-30 | Product + Safety | Zero | Voice P95 < 800 ms; GMS cert; DRM audit pass |
| M3: Production | 2026-12-15 | Safety + Legal + QA | Zero | OTA ≥ 99.5% fleet; UN R155/R156 submitted; safety case signed |
| M4: Enhancement | 2027-06-30 | Product | < 5 P2 | AR nav pilot; NPS ≥ 45 from fleet telemetry |

## Requirements per Milestone

| Milestone | Must Have Count | Should Have Count | Total |
|---|---|---|---|
| M1 | 10 (AAOS core) | 0 | 10 |
| M2 | 24 (Voice + Nav + Media) | 1 (GMS cert) | 25 |
| M3 | 13 (Full OTA pipeline) | 5 (EV, multi-zone, podcast, delta, scheduled) | 18 |
| M4 | 0 | 3 | 2 Could Have |

## KPI Targets per Milestone

| KPI | M1 Target | M2 Target | M3 Target |
|---|---|---|---|
| Boot time (cold) | **< 4.0 s** | Maintained | Maintained |
| Voice P95 latency | — | **< 800 ms** | Maintained |
| OTA success rate | Infra ready | A/B tested | **≥ 99.5%** fleet |
| Navigation offline | — | **< 3 s** route calc | Maintained |
| Media resume | — | **< 2 s** | Maintained |
| GMS certification | Pre-audit | **Received** | Maintained |
| UN R155/R156 | Security infra | Pen test | **Submitted** |
