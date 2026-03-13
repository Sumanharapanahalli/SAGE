"""
PoseEngine — Knowledge Seeder
=============================
Seeds the vector memory with platform context so SAGE agents have
institutional knowledge on every request — no cold start.

Run once after first setup, and again after major architecture decisions.

Usage:
    SAGE_PROJECT=poseengine python solutions/poseengine/scripts/seed_knowledge.py
"""

import os
import sys

# Add SAGE root to path
SAGE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, SAGE_ROOT)

os.environ.setdefault("SAGE_PROJECT", "poseengine")

from src.memory.vector_store import vector_memory

KNOWLEDGE = [
    # ── Platform vision ────────────────────────────────────────────────────
    {
        "text": (
            "PoseEngine is a domain-agnostic human pose and action sequence detection platform. "
            "The core detects 17 COCO keypoints per frame and classifies temporal sequences into actions. "
            "Application domains plug in via config: yoga (pose correction), dance (move matching), "
            "retail (pickup/browse detection), sports (form analysis), therapy (ROM measurement). "
            "The core engine never stores biometric data — GDPR compliant by design."
        ),
        "metadata": {"type": "platform_vision", "domain": "all"},
    },
    # ── ML pipeline architecture ───────────────────────────────────────────
    {
        "text": (
            "PoseEngine ML pipeline: PyTorch training → ONNX export → TFLite (Android) + CoreML (iOS). "
            "Primary models: HRNet-W48 (server, mAP ~0.85), HRNet-W32 (balanced), "
            "MobileNetV3-Lite (mobile, 18MB, mAP ~0.79). "
            "Evaluation metrics: mAP (COCO), OKS (Object Keypoint Similarity), PCKh (head-normalised). "
            "Production thresholds: full model mAP >= 0.80, mobile model mAP >= 0.75, max mobile size 25MB. "
            "Experiment tracking via Weights & Biases (WandB). "
            "Training on GPU runners in GitLab CI/CD with validation stage gate before export."
        ),
        "metadata": {"type": "mlops_architecture", "domain": "ml"},
    },
    # ── Action sequence recognition ────────────────────────────────────────
    {
        "text": (
            "Action sequence recognition: input is N frames of 17 keypoints each (COCO format). "
            "Each keypoint: {x, y, confidence}. Key joints: nose, shoulders, elbows, wrists, hips, knees, ankles. "
            "Action is classified from the temporal pattern of joint angles and velocities. "
            "Deviation scoring compares detected angles to reference template per joint. "
            "Severity: delta < 5° = OK, 5-15° = warning, > 15° = correction required (yoga default). "
            "Sports/therapy use tighter thresholds (10°). Dance uses timing offset (ms) not angle."
        ),
        "metadata": {"type": "sequence_recognition", "domain": "all"},
    },
    # ── Yoga domain rules ──────────────────────────────────────────────────
    {
        "text": (
            "Yoga domain rules for PoseEngine: "
            "Key poses: Warrior I/II, Downward Dog, Tree Pose, Child's Pose, Mountain Pose. "
            "Correction threshold: joint deviation > 15° triggers feedback. "
            "Priority joints: spine alignment, hip angle, knee tracking (must be over second toe). "
            "Feedback tone: encouraging, breath-aware. Example: 'Exhale and lower your right hip'. "
            "Never give more than one correction at a time in real-time mode. "
            "Session tracking: hold time, rep count, progression over sessions. "
            "Breath cues are mandatory — pose correction without breath instruction is incomplete."
        ),
        "metadata": {"type": "domain_rules", "domain": "yoga"},
    },
    # ── Dance domain rules ─────────────────────────────────────────────────
    {
        "text": (
            "Dance domain rules for PoseEngine: "
            "Primary signal: timing offset of foot placement vs beat grid (in ms). "
            "Threshold: > 100ms off-beat = rhythm issue. "
            "Secondary signals: arm extension angle, head position, body lean. "
            "Scoring: timing_score (0-100) and move_match_score (0-100) reported separately. "
            "Feedback format: beat-referenced ('step lands 2 beats early'). "
            "Tutorials show side-by-side: reference instructor vs user skeleton overlay."
        ),
        "metadata": {"type": "domain_rules", "domain": "dance"},
    },
    # ── Retail domain rules ────────────────────────────────────────────────
    {
        "text": (
            "Retail domain rules for PoseEngine: "
            "Events: reach (arm extends toward shelf), pickup (object leaves shelf zone), "
            "place (object enters basket zone), browse (dwell > 3s at shelf face), queue_wait. "
            "GDPR critical: no biometric data stored. Only aggregate event counts and timing. "
            "No face detection. No individual tracking across sessions. "
            "Output: event_type, confidence, zone_id, timestamp. No personal identifiers. "
            "Dwell threshold: > 3s = engagement event. > 30s = potential friction signal."
        ),
        "metadata": {"type": "domain_rules", "domain": "retail"},
    },
    # ── Flutter mobile architecture ────────────────────────────────────────
    {
        "text": (
            "PoseEngine Flutter app architecture: camera frames processed via platform channels. "
            "Inference runs in a Dart isolate to avoid blocking the UI thread. "
            "Android: TFLite via tflite_flutter plugin + CameraX for frame capture. "
            "iOS: CoreML via coreml_flutter plugin + AVFoundation. "
            "Target: 30 FPS inference on mid-range devices (2019+). "
            "Pose overlay rendering: CustomPainter draws skeleton on top of camera preview. "
            "Flutter SDK breaking changes are a recurring issue — pin SDK version in pubspec.yaml. "
            "Firebase Crashlytics for crash reporting on both platforms."
        ),
        "metadata": {"type": "mobile_architecture", "domain": "mobile"},
    },
    # ── Current implementation gaps ────────────────────────────────────────
    {
        "text": (
            "PoseEngine current implementation gaps as of March 2026: "
            "1. Queue dispatcher does not handle poseengine task types (ANALYZE_TRAINING_LOG, etc). "
            "2. No temporal sequence analysis task type (ANALYZE_POSE_SEQUENCE) implemented. "
            "3. No feedback generation agent implemented (GENERATE_FEEDBACK task type defined but not wired). "
            "4. WandB integration not implemented — monitor does not poll W&B metrics. "
            "5. Model registry API endpoint does not exist — UI shows hardcoded placeholder data. "
            "6. MLOps tasks EVALUATE_MODEL, EXPORT_MODEL, REGISTER_MODEL not wired to any agent. "
            "7. Zero tests in solutions/poseengine/tests/ — only conftest.py exists. "
            "8. GitHub support missing — developer.py is GitLab-only but poseengine uses GitHub too."
        ),
        "metadata": {"type": "implementation_state", "domain": "all"},
    },
    # ── Agent team structure ───────────────────────────────────────────────
    {
        "text": (
            "PoseEngine has two teams with different cadences: "
            "ML team: focuses on training runs, model evaluation, ONNX export. Review cycle: weekly. "
            "Mobile team: focuses on Flutter CI, app releases, crash reports. Review cycle: per sprint (2 weeks). "
            "SAGE should route ANALYZE_TRAINING_LOG and EVALUATE_MODEL alerts to ML team. "
            "ANALYZE_CRASH_LOG, REVIEW_FLUTTER_CODE, ANALYZE_CI_LOG (flutter target) go to Mobile team. "
            "Planner should check which team is affected before scheduling tasks. "
            "Critical issues (model regression > 5% mAP, crash rate spike) bypass team routing and alert both."
        ),
        "metadata": {"type": "team_structure", "domain": "all"},
    },
    # ── Model evaluation decision history ─────────────────────────────────
    {
        "text": (
            "Architecture decision: HRNet-W48 chosen as primary server model over ViTPose-B. "
            "Reason: ViTPose-B has higher mAP (0.873 vs 0.847) but 340MB vs 142MB. "
            "Mobile constraint: max model size for OTA update is 25MB compressed. "
            "Decision: ViTPose-B in evaluation pipeline only, not production. "
            "MobileNetV3-Lite (18MB) is the production mobile model. "
            "Next evaluation: ViTPose-S (smaller variant) when released — target 80MB."
        ),
        "metadata": {"type": "architecture_decision", "domain": "ml"},
    },
]


def seed():
    print(f"\nSeeding PoseEngine vector memory with {len(KNOWLEDGE)} knowledge entries...\n")
    for i, item in enumerate(KNOWLEDGE, 1):
        vector_memory.add_feedback(item["text"], metadata=item["metadata"])
        print(f"  [{i:02d}/{len(KNOWLEDGE)}] {item['metadata']['type']} ({item['metadata']['domain']})")
    print(f"\nDone. Vector memory mode: {vector_memory.mode}")
    print("Run 'make run PROJECT=poseengine' to start the backend with seeded knowledge.\n")


if __name__ == "__main__":
    seed()
