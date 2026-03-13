# SOUL.md — reflect solution

## What This Solution Is

Reflect is a **general-purpose human movement analysis platform** with a white-label
tenant model. It is not a yoga app. Yoga is the first module. The same platform teaches
gym, PT, pilates, martial arts, dance, sports — any activity where a body needs to
match a reference movement.

```
EXTRACT STAGE (admin tool)
  ├── Video source (webcam, file, URL)
  ├── MediaPipe BlazePose → 33 landmarks × N frames
  ├── Normalizer → hip-center, unit scale, noise filter
  ├── Segmenter → hold / transition phase detection
  ├── GoldStandard → mean ± σ joint angles per phase
  ├── Clinical review + RSA-2048 signing
  └── Output: skill pack (definition.json + signature.sig + thumbnail.png)

TEACH STAGE (end user app)
  ├── Flutter app — camera pipeline (CameraX / AVFoundation)
  ├── C++ Pose Engine — real-time joint scoring vs skill pack thresholds
  ├── Confidence-weighted scoring per joint
  ├── Dart FFI — Flutter ↔ C++ boundary
  ├── TTS feedback via voice_packs
  └── CustomPainter skeleton overlay at 30 FPS
```

## Platform Components

| Component | Language | Tests | Status |
|---|---|---|---|
| Extract Engine | Python (MediaPipe) | 108 | ✅ Functional |
| Pose Engine | C++ (CMake) | 80 | ✅ Functional |
| Python Tools | Python | 130 | ✅ Functional |
| Platform SDK | Python | 53 | ✅ Functional |
| SAGE Agents | Python | 88+ | ✅ 10 agents |
| Flutter App | Dart | 55 | ⚠️ Needs Flutter SDK in CI |
| **Total** | | **~550+** | |

## Activity Modules

| Module | Movements | Notes |
|---|---|---|
| Yoga | 20 | Most complete module |
| Gym | 2 | Needs expansion |
| Physical Therapy | 2 | Clinical review required |
| Pilates | 5 | |
| Tai Chi | 5 | Flow sequences — needs sequence support |
| Qigong | 5 | |
| Barre | 5 | |

## Tenants

zen_yoga, ironform_gym, namaste_studio, harmony_wellness, movewell_clinic

Each tenant: RSA license, custom branding, chosen activity modules, feature flags.

## SAGE Agent Roles for This Solution

| Role | Purpose |
|---|---|
| `tech_lead` | Proposes what to build next, plans waves, surfaces gaps |
| `core_agent` | Skill packs, evaluation, tenant management, platform status |
| `ml_manager` | Threshold tuning, evaluation methodology, confidence scoring |
| `dev_agent` | Build system, architecture, git workflow, code quality |
| `tester_agent` | Test execution, coverage, quality gates |
| `pose_engine_agent` | C++ engine build, test, FFI, performance |
| `video_analysis_agent` | Activity catalogs, skill pack review, reference videos |
| `sequence_analyst` | Movement sequence validation, threshold quality analysis |
| `infra_agent` | Business ops, CRM, tenant onboarding, communications |
| `support_agent` | Tickets, FAQ, escalation routing |

## Known Gaps (as of March 2026)

- Admin web panel for extract stage (CLI only)
- Multi-angle evaluation (not implemented)
- Sequence/flow movement support (sun salutation, rep-based)
- Voice pack integration (voice_packs/ exists, not wired to Flutter)
- CI Flutter tests require Flutter SDK (currently skipped in CI)
- Tenant onboarding is manual, no automated flow
- SAGE Monitor not polling Reflect metrics

## Critical Constraints

- **RSA signing is mandatory** before any skill pack reaches a tenant device
- **Clinical review** required for PT/therapy movements before signing
- **FFI struct layout** must exactly match C structs — silent data corruption otherwise
- **Tenant isolation** — one tenant must never see another tenant's data or license

## Quick Start

```bash
# Start SAGE with reflect solution
make run PROJECT=reflect
make ui

# Seed vector memory with platform knowledge (run once)
SAGE_PROJECT=reflect python solutions/reflect/scripts/seed_knowledge.py

# Check current gaps
python solutions/reflect/mcp_servers/codebase_server.py gaps
```

## Specification Files

```
solutions/reflect/specs/
  PROJECT.md        ← What the platform is and who it is for
  REQUIREMENTS.md   ← Functional and non-functional requirements
  ROADMAP.md        ← Phases, milestones, success criteria
  STATE.md          ← Current implementation state (update after each phase)
```
