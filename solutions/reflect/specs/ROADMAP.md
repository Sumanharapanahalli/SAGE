# ROADMAP.md — Reflect Movement Analysis Platform

**Last Updated:** 2026-03-13
**Status:** Living Document

---

## Phase 1 — Foundation (COMPLETE)
**Goal:** Functional Extract → Teach pipeline with core test coverage

| Deliverable | Status | Tests |
|---|---|---|
| Extract engine (MediaPipe → skill pack) | ✅ Done | 108 tests |
| C++ pose engine (scoring, confidence) | ✅ Done | 80 tests |
| Python tools layer | ✅ Done | 130 tests |
| Platform SDK | ✅ Done | 53 tests |
| 10 SAGE agents | ✅ Done | 88+ tests |
| 7 activity modules (44 movements) | ✅ Done | — |
| 5 tenants | ✅ Done | — |
| Flutter app (Android, iOS) | ✅ Done | 55 tests |
| RSA-2048 signing pipeline | ✅ Done | — |

---

## Phase 2 — Quality & Completeness (CURRENT)
**Goal:** Production-quality skill packs across all modules; CI reliable; Flutter CI working

| Deliverable | Status | Notes |
|---|---|---|
| Flutter CI with Flutter SDK | ❌ Todo | Skip in CI currently |
| Multi-angle evaluation | ❌ Todo | Single-angle only |
| Sequence/flow movement support | ❌ Todo | Sun salutation, rep flows |
| Gym module expansion (2 → 10 movements) | ❌ Todo | ironform_gym priority |
| PT module clinical expansion (2 → 8) | ❌ Todo | movewell_clinic priority |
| Voice pack wired to Flutter | ❌ Todo | voice_packs/ exists, not connected |
| SAGE Monitor polling Reflect metrics | ❌ Todo | Manual status checks only |
| Automated tenant onboarding flow | ❌ Todo | Manual currently |

**Success criteria:**
- All 550+ tests pass in CI including Flutter
- Each tenant has ≥ 5 movements per enabled module
- Multi-angle evaluation available for all signed skill packs

---

## Phase 3 — Admin Web Panel
**Goal:** Non-technical tenant admins can extract and manage skill packs via browser UI

| Deliverable | Status | Notes |
|---|---|---|
| Web extract tool (upload video → skill pack) | ❌ Todo | CLI only today |
| Admin review UI (skeleton overlay, phase adjust) | ❌ Todo | |
| Skill pack management dashboard | ❌ Todo | |
| Tenant self-service onboarding | ❌ Todo | |
| Clinical review workflow (sign-off, audit trail) | ❌ Todo | |

**Success criteria:**
- A yoga teacher with no coding background can extract a new movement in < 30 minutes
- Clinical sign-off creates an immutable audit record

---

## Phase 4 — Scale & Revenue
**Goal:** Multiple paying tenants, automated billing, marketplace

| Deliverable | Status | Notes |
|---|---|---|
| Subscription management | ❌ Todo | |
| Skill pack marketplace (tenant sharing) | ❌ Todo | |
| AR pose review (side-by-side comparison) | ❌ Todo | |
| WandB / ML metrics dashboard in SAGE | ❌ Todo | |
| White-label app store submission pipeline | ❌ Todo | |

---

## Milestone Definitions

| Milestone | Definition |
|---|---|
| MVP | Phase 1 complete — pipeline functional, all tests passing |
| Beta Ready | Phase 2 complete — production-quality skill packs, CI reliable |
| Tenant Launch | Phase 3 complete — tenant admin can self-serve |
| Revenue | Phase 4 complete — paying tenants, automated billing |
