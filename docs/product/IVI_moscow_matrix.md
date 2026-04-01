# IVI System — MoSCoW Prioritization Matrix

## Must Have (M1–M3 blocking — 39 functional + 15 NFR)

| ID | Feature Area | Summary | ASIL/QM |
|---|---|---|---|
| IVI-REQ-001 | AAOS | Boot < 4 s (cold start) | QM |
| IVI-REQ-002 | AAOS | AAOS 13+ as primary OS | QM |
| IVI-REQ-003 | AAOS | VHAL full CAN pass-through | ASIL-B |
| IVI-REQ-004 | AAOS | Multi-user zone isolation | ASIL-A |
| IVI-REQ-005 | AAOS | Dual-display output | QM |
| IVI-REQ-008 | AAOS | Driving restriction policy enforcement | ASIL-B |
| IVI-REQ-009 | AAOS | VHAL tamper-evident audit log | QM |
| IVI-REQ-011 | Voice | On-device wake-word (no cloud) | QM |
| IVI-REQ-012 | Voice | End-to-end latency P95 < 800 ms | QM |
| IVI-REQ-013 | Voice | False activation < 1/8 h | QM |
| IVI-REQ-014 | Voice | 12 language support | QM |
| IVI-REQ-015 | Voice | NPU on-device NLU inference | QM |
| IVI-REQ-017 | Voice | Voice control of nav/media/climate/calls | ASIL-A |
| IVI-REQ-018 | Voice | Audio + HUD confirm < 200 ms | ASIL-A |
| IVI-REQ-020 | Voice | Offline NLU graceful degradation | QM |
| IVI-REQ-021 | Navigation | Offline full-country maps | QM |
| IVI-REQ-022 | Navigation | 32 GB dedicated map partition | QM |
| IVI-REQ-023 | Navigation | Seamless offline/online transition | QM |
| IVI-REQ-024 | Navigation | Real-time traffic < 60 s freshness | QM |
| IVI-REQ-025 | Navigation | Route calc < 3 s (offline, 1,000 km) | QM |
| IVI-REQ-026 | Navigation | Map SOTA updates | QM |
| IVI-REQ-027 | Navigation | Turn-by-turn to cluster + console | ASIL-A |
| IVI-REQ-029 | Navigation | Map data AES-256 at rest | QM |
| IVI-REQ-031 | Media | Spotify AAOS integration | QM |
| IVI-REQ-032 | Media | YouTube Music AAOS integration | QM |
| IVI-REQ-033 | Media | Apple Music integration | QM |
| IVI-REQ-034 | Media | Media resume < 2 s | QM |
| IVI-REQ-035 | Media | Offline playlist caching | QM |
| IVI-REQ-036 | Media | Multi-modal media controls | ASIL-A |
| IVI-REQ-037 | Media | Widevine L1 DRM | QM |
| IVI-REQ-039 | Media | Session persist across IGN cycles | QM |
| IVI-REQ-041 | Media | No video on driver display at speed | ASIL-B |
| IVI-REQ-042 | Media | Bluetooth audio fallback | QM |
| IVI-REQ-043 | OTA | SOTA application layer | QM |
| IVI-REQ-044 | OTA | FOTA MCU/ECU gateway | ASIL-B |
| IVI-REQ-045 | OTA | ≥ 99.5% OTA success rate | QM |
| IVI-REQ-046 | OTA | A/B atomic partition + auto-rollback | ASIL-B |
| IVI-REQ-047 | OTA | ED25519 signed packages | ASIL-B |
| IVI-REQ-048 | OTA | FOTA blocked during motion | ASIL-B |
| IVI-REQ-049 | OTA | < 5% CPU overhead during SOTA | QM |
| IVI-REQ-050 | OTA | Driver notification + 7-day deferral | QM |
| IVI-REQ-051 | OTA | Staged rollout with auto-halt | QM |
| IVI-REQ-052 | OTA | Tamper-evident OTA audit log | ASIL-A |
| IVI-REQ-055 | OTA | mTLS on OTA endpoints | ASIL-A |

---

## Should Have (M3 or M4 — 9 requirements)

| ID | Feature Area | Summary | ASIL/QM |
|---|---|---|---|
| IVI-REQ-006 | AAOS | Split-screen multitasking | QM |
| IVI-REQ-010 | AAOS | GMS certification (target M2) | QM |
| IVI-REQ-016 | Voice | Custom wake-word enrollment | QM |
| IVI-REQ-019 | Voice | Multi-turn dialogue (3 turns) | QM |
| IVI-REQ-028 | Navigation | EV-specific routing + charging POIs | QM |
| IVI-REQ-038 | Media | Multi-zone audio | QM |
| IVI-REQ-040 | Media | Podcast/audiobook apps | QM |
| IVI-REQ-053 | OTA | Delta package compression (bsdiff) | QM |
| IVI-REQ-054 | OTA | Scheduled OTA (driver-configurable) | QM |

---

## Could Have (M4+ — 2 requirements)

| ID | Feature Area | Summary | ASIL/QM |
|---|---|---|---|
| IVI-REQ-007 | AAOS | Rear seat entertainment (3rd display) | QM |
| IVI-REQ-030 | Navigation | AR overlay navigation | QM |

---

## Won't Have (this program)

| Feature | Reason |
|---|---|
| Augmented HUD | Requires dedicated HUD ECU — out of IVI scope |
| V2X integration | Separate connectivity stack program |
| Biometric driver authentication | Hardware dependency not in BOM baseline |
