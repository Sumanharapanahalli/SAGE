# PROJECT.md — Reflect Movement Analysis Platform

**Last Updated:** 2026-03-13
**Status:** Active Development
**Version:** 1.0.0

---

## What Is Reflect?

Reflect is a **general-purpose human movement analysis platform** with a white-label
tenant model. Organizations (yoga studios, gyms, PT clinics, sports academies) license
a fully branded app with their chosen activity modules.

This is **not** a yoga app. Yoga is the first module. The same platform teaches any
human movement — gym, physical therapy, pilates, martial arts, dance, sports form,
ergonomics.

---

## Core Value Proposition

**For tenants (B2B):** A white-label movement coaching app in weeks, not years.
Bring your own expert videos. We extract the skill packs, you deliver the app.

**For end users:** Real-time, on-device movement coaching with camera feedback.
No cloud upload. No subscription. The coach is on the device.

---

## The Extract → Teach Pipeline

```
Expert demonstrates movement (video/webcam)
        ↓
Extract Engine (Python + MediaPipe)
    - 33 BlazePose landmarks × N frames
    - Normalize to hip-center, unit scale
    - Segment into hold / transition phases
    - Compute gold standard (mean ± σ angles)
    - Clinical review + RSA-2048 signing
        ↓
Skill Pack (definition.json + signature.sig)
        ↓
Teach Stage (Flutter app + C++ Pose Engine)
    - Real-time camera feed
    - Confidence-weighted joint scoring
    - TTS feedback + skeleton overlay
    - Session progress tracking
```

---

## Target Users

| User Type | Description | Entry Point |
|---|---|---|
| Tenant Admin | Yoga studio, gym, PT clinic owner | Web admin panel (Phase 3) |
| Movement Expert | Yoga teacher, physiotherapist | Extract tool (admin) |
| End User | App user learning movements | Flutter app |
| Developer (you) | Building and extending the platform | SAGE (this) |

---

## Technology Stack

| Component | Technology | Location |
|---|---|---|
| Extract Engine | Python, MediaPipe BlazePose | `/extract_engine/` |
| Pose Engine | C++17, CMake, GoogleTest | `/pose_engine/` |
| Platform SDK | Python | `/platform_sdk/` |
| Tools | Python | `/tools/` |
| Flutter App | Dart, Flutter 3.x | `/flutter_app/` |
| SAGE Agents | Python, FastAPI | `/agents/` + `/sage_platform/` |

---

## Activity Modules (Current)

| Module | Movements | Priority |
|---|---|---|
| Yoga | 20 | ✅ Primary module |
| Pilates | 5 | Active |
| Tai Chi | 5 | Active |
| Qigong | 5 | Active |
| Barre | 5 | Active |
| Gym | 2 | Needs expansion |
| Physical Therapy | 2 | Needs clinical expansion |

---

## Active Tenants

| Tenant ID | Name | Focus |
|---|---|---|
| zen_yoga | Zen Yoga | Yoga, Pilates |
| ironform_gym | IronForm Gym | Gym, Sports |
| namaste_studio | Namaste Studio | Yoga, Barre |
| harmony_wellness | Harmony Wellness | PT, Pilates, Qigong |
| movewell_clinic | MoveWell Clinic | Physical Therapy |

---

## Creator

shetty@yogaapp.dev
