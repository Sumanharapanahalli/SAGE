"""
Reflect — Knowledge Seeder
===========================
Seeds the vector memory with platform context so SAGE agents have
institutional knowledge on every request — no cold start.

Run once after first setup, and again after major architecture decisions.

Usage:
    SAGE_PROJECT=reflect python solutions/reflect/scripts/seed_knowledge.py
"""

import os
import sys

SAGE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, SAGE_ROOT)

os.environ.setdefault("SAGE_PROJECT", "reflect")

from src.memory.vector_store import vector_memory

KNOWLEDGE = [
    # ── Platform vision ────────────────────────────────────────────────────
    {
        "text": (
            "Reflect is a general-purpose human movement analysis platform with a "
            "white-label tenant model. It is NOT a yoga app — yoga is the first module. "
            "The same platform teaches gym, PT, pilates, tai chi, qigong, barre, dance, sports. "
            "The Extract → Teach pipeline turns expert video demonstrations into portable "
            "skill packs that guide users with real-time camera feedback on-device. "
            "No biometric data is ever uploaded to cloud — fully on-device."
        ),
        "metadata": {"type": "platform_vision", "domain": "all"},
    },
    # ── Extract → Teach pipeline ───────────────────────────────────────────
    {
        "text": (
            "Reflect Extract stage: MediaPipe BlazePose extracts 33 landmarks × N frames "
            "from video (file, webcam, URL). Normalizer centers on hips and scales to unit. "
            "Segmenter detects hold vs transition phases using landmark velocity "
            "(low velocity = hold, high = transition). GoldStandard computes mean ± σ "
            "joint angles per hold phase. Output: skill pack with definition.json, "
            "signature.sig (RSA-2048), thumbnail.png. "
            "Teach stage: Flutter app runs C++ pose engine via Dart FFI for real-time "
            "joint scoring at 30 FPS. CustomPainter skeleton overlay. TTS feedback."
        ),
        "metadata": {"type": "pipeline_architecture", "domain": "extract"},
    },
    # ── C++ Pose Engine ────────────────────────────────────────────────────
    {
        "text": (
            "Reflect C++ Pose Engine: scores user pose against skill pack thresholds in real time. "
            "Confidence-weighted scoring: low-confidence joints (occluded/off-frame) have "
            "reduced weight in overall score. Per-joint severity: OK (within target range), "
            "warning (within warning zone ±3σ), correction (outside warning zone). "
            "FFI boundary: C API with versioned structs, null-safe, Pointer<> in Dart. "
            "Build: CMake (Debug/Release/RelWithDebInfo). "
            "Tests: 6 suites, 80 tests (scoring, confidence, FFI, performance, ...). "
            "Target: < 5ms p95 frame scoring on mid-range Android 2020+."
        ),
        "metadata": {"type": "pose_engine", "domain": "cpp"},
    },
    # ── Skill pack format ──────────────────────────────────────────────────
    {
        "text": (
            "Reflect skill pack definition.json (schema v4): contains phases (hold/transition), "
            "per-phase joint angle definitions with target_min, target_max (mean ± 2σ), "
            "warning_min, warning_max (mean ± 3σ), and confidence weights. "
            "RSA-2048 signing required before distribution to any tenant device. "
            "Clinical review sign-off required for PT/therapy movements — must be logged. "
            "Quality gate: skill pack must achieve ≥ 85% pass rate on test recordings before signing. "
            "Tenant schema version: v3. Skill pack schema version: v4."
        ),
        "metadata": {"type": "skill_pack_format", "domain": "data"},
    },
    # ── Flutter app architecture ───────────────────────────────────────────
    {
        "text": (
            "Reflect Flutter app: cross-platform (Android, iOS, Linux, macOS, Windows). "
            "Camera pipeline: CameraX (Android), AVFoundation (iOS). "
            "Dart isolate for off-main-thread C++ inference via FFI — never call FFI from UI thread. "
            "CustomPainter draws skeleton overlay on camera preview — keep paint() < 2ms. "
            "TTS feedback: voice_packs/ system, one correction at a time, positive framing. "
            "Session tracking: hold time, rep count, score history per movement. "
            "Offline first: skill packs downloaded to device, no cloud biometric upload. "
            "Flutter SDK must be pinned in pubspec.yaml — breaking changes are frequent."
        ),
        "metadata": {"type": "flutter_architecture", "domain": "mobile"},
    },
    # ── Activity modules ───────────────────────────────────────────────────
    {
        "text": (
            "Reflect activity modules (7 active): "
            "yoga (20 movements — most complete, includes Warrior I/II, Downward Dog, Tree Pose), "
            "gym (2 movements — needs expansion to 10+ for ironform_gym), "
            "physical_therapy (2 movements — needs clinical expansion for movewell_clinic), "
            "pilates (5), tai_chi (5 — flow sequences need sequence movement support), "
            "qigong (5), barre (5). "
            "Each module: activity_modules/<name>/ with module.json and skill pack subfolders. "
            "New module scaffold: SCAFFOLD_MODULE task creates catalog + movement templates."
        ),
        "metadata": {"type": "activity_modules", "domain": "content"},
    },
    # ── Tenant white-label system ──────────────────────────────────────────
    {
        "text": (
            "Reflect tenant system (5 active tenants): "
            "zen_yoga (yoga, pilates), ironform_gym (gym — blocked on expansion), "
            "namaste_studio (yoga, barre), harmony_wellness (PT, pilates, qigong), "
            "movewell_clinic (physical_therapy — blocked on clinical expansion). "
            "Per-tenant: RSA license (offline validation), custom branding, "
            "selected activity modules, feature flags. Tenant schema v3. "
            "CRITICAL: tenant isolation is hard — one tenant must never see another's data. "
            "New tenant: CREATE_TENANT task → validate modules → issue license → VALIDATE_TENANT."
        ),
        "metadata": {"type": "tenant_system", "domain": "platform"},
    },
    # ── SAGE agents ────────────────────────────────────────────────────────
    {
        "text": (
            "Reflect has 10 SAGE agents with escalation chain: "
            "Core (20 tools): skill packs, evaluation, tenants, system status. "
            "Infra (16 tools): CRM, orders, communications, task management. "
            "ML Manager (8): threshold tuning, evaluation methodology, confidence scoring. "
            "Dev (8): build, code metrics, architecture, git. "
            "Tester (8): test execution, coverage, quality gates — 550+ tests total. "
            "Video Analysis (8): activity catalogs, skill pack review, reference videos. "
            "Pose Engine (8): C++ build, test, FFI, performance. "
            "Customer Support (8): tickets, FAQ, escalation. "
            "Marketing (8): campaigns, content, leads. "
            "Finance (8): invoices, subscriptions, revenue. "
            "All agent interactions logged to interactions.jsonl."
        ),
        "metadata": {"type": "agent_inventory", "domain": "all"},
    },
    # ── Test coverage ──────────────────────────────────────────────────────
    {
        "text": (
            "Reflect test coverage (as of March 2026): "
            "C++ Pose Engine: 80 tests (6 suites: scoring, confidence, FFI, performance, ...). "
            "Extract Engine (Python): 108 tests. "
            "Python Tools: 130 tests. "
            "Platform SDK: 53 tests. "
            "SAGE Agents: 88+ tests (10 agents). "
            "Flutter: 55 tests (requires Flutter SDK — currently skipped in CI). "
            "Total: ~550+. "
            "Quality gates: no PR merges if non-Flutter suites regress. "
            "New features require tests before merge. "
            "Run: pytest /home/shetty/sandbox/Reflect (Python), ctest (C++ engine)."
        ),
        "metadata": {"type": "test_coverage", "domain": "quality"},
    },
    # ── Current implementation gaps ────────────────────────────────────────
    {
        "text": (
            "Reflect known gaps as of March 2026 (Phase 2): "
            "1. Flutter CI requires Flutter SDK — tests skipped in CI. "
            "2. Multi-angle evaluation not implemented — only single-angle. "
            "3. Sequence/flow movement support missing — blocks tai chi, sun salutation. "
            "4. Voice pack (voice_packs/) exists but NOT wired to Flutter — no TTS in app. "
            "5. Gym module only 2 movements — ironform_gym unusable. "
            "6. PT module only 2 movements — movewell_clinic needs clinical expansion. "
            "7. Admin web panel does not exist — extract stage CLI only. "
            "8. SAGE Monitor not polling Reflect metrics — manual status checks only. "
            "9. Tenant onboarding is manual — not automated."
        ),
        "metadata": {"type": "implementation_gaps", "domain": "all"},
    },
    # ── Architecture decisions ─────────────────────────────────────────────
    {
        "text": (
            "Reflect architecture decisions: "
            "MediaPipe BlazePose chosen over OpenPose/HRNet for extract stage — "
            "runs on CPU without GPU, lighter dependency, 33 landmarks (vs COCO 17) "
            "gives better finger/toe coverage for yoga and PT. "
            "C++ engine chosen over Python for teach stage — "
            "< 5ms scoring requirement cannot be met in Python at 30 FPS on mobile. "
            "Dart FFI (not platform channels) for engine integration — "
            "lower latency, direct memory sharing, no serialization overhead. "
            "RSA-2048 for signing — offline verification, no network required for license check."
        ),
        "metadata": {"type": "architecture_decisions", "domain": "all"},
    },
]


def seed():
    print(f"\nSeeding Reflect vector memory with {len(KNOWLEDGE)} knowledge entries...\n")
    for i, item in enumerate(KNOWLEDGE, 1):
        vector_memory.add_feedback(item["text"], metadata=item["metadata"])
        print(f"  [{i:02d}/{len(KNOWLEDGE)}] {item['metadata']['type']} ({item['metadata']['domain']})")
    print(f"\nDone. Vector memory mode: {vector_memory.mode}")
    print("Run 'make run PROJECT=reflect' to start the backend with seeded knowledge.\n")


if __name__ == "__main__":
    seed()
