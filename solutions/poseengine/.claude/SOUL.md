# SOUL.md — poseengine solution

## What This Solution Is

PoseEngine is a **domain-agnostic human pose and action sequence detection platform**,
not a single application. The core engine is shared; application domains plug in via config.

```
CORE ENGINE (shared)
  ├── Keypoint detection    → 17 COCO joints per frame
  ├── Sequence recognition  → N frames → action label + temporal pattern
  ├── Deviation scoring     → detected vs reference per joint (degrees)
  └── Feedback generation   → deviation → human-readable correction

APPLICATION LAYER (domain-specific config)
  ├── Yoga      → pose correction, breath cues, session progression
  ├── Dance     → move matching, timing score, rhythm feedback
  ├── Retail    → item pickup detection, dwell time, queue behaviour (GDPR: no biometrics stored)
  ├── Sports    → form analysis, rep counting, injury risk signal
  └── Therapy   → ROM measurement, exercise compliance
```

## ML Stack

- **Training:** PyTorch → distributed GPU (GitLab CI/CD runners)
- **Models:** HRNet-W48 (server), HRNet-W32 (balanced), MobileNetV3-Lite (mobile, 18MB)
- **Export:** ONNX → TFLite (Android) + CoreML (iOS)
- **Metrics:** mAP (COCO), OKS, PCKh; production gate: mAP ≥ 0.80 full / ≥ 0.75 mobile
- **Tracking:** Weights & Biases (WandB) for experiment tracking
- **Quantization:** INT8 / FP16 for mobile (PTQ and QAT)

## Mobile Stack

- **Framework:** Flutter (Dart), Android + iOS
- **Inference:** TFLite via tflite_flutter (Android), CoreML via platform channel (iOS)
- **Threading:** Dart isolate for off-main-thread inference
- **Target:** 30 FPS on mid-range devices (2019+)
- **Crash reporting:** Firebase Crashlytics

## Two Teams, Different Cadences

| Team | Focus | Review cycle | SAGE routes |
|---|---|---|---|
| ML team | Training, evaluation, model export | Weekly | ANALYZE_TRAINING_LOG, EVALUATE_MODEL, EXPORT_MODEL |
| Mobile team | Flutter CI, app releases, crash reports | Per sprint (2w) | ANALYZE_CRASH_LOG, REVIEW_FLUTTER_CODE, ANALYZE_CI_LOG |

Critical issues (mAP regression > 5%, crash rate spike) → alert both teams.

## SAGE Agent Roles for This Solution

| Role | Purpose |
|---|---|
| `tech_lead` | Proposes what to build next, identifies gaps, plans implementation waves |
| `ml_engineer` | Model architecture, training optimisation, ONNX export, quantization |
| `mobile_developer` | Flutter/Dart, camera pipeline, TFLite/CoreML integration, UX performance |
| `data_scientist` | Dataset curation, annotation quality, benchmark evaluation, A/B testing |
| `devops_engineer` | CI/CD pipelines, GPU runners, model registry, deployment automation |
| `sequence_analyst` | Temporal pose sequence analysis, action classification, deviation detection |
| `domain_adapter` | Routes pose analysis to domain-specific rules (yoga/dance/retail/sports) |
| `feedback_generator` | Converts deviation scores to human-readable correction instructions |

## How SAGE Helps Build This

1. **Ask the Tech Lead** — go to Agents → Tech Lead → describe what you want to build
2. **Tech Lead proposes a wave plan** — independent tasks in Wave 1, dependent in Wave 2+
3. **Approve the plan** — Planner decomposes into tasks, queue executes
4. **Agents learn** — every correction fed back into vector memory → next proposal better

```bash
# Seed vector memory with platform context (run once after setup)
SAGE_PROJECT=poseengine python solutions/poseengine/scripts/seed_knowledge.py

# Inspect current gaps
python solutions/poseengine/mcp_servers/codebase_server.py gaps

# Start SAGE with poseengine
make run PROJECT=poseengine
make ui
```

## GDPR Constraint

Retail domain: **never store biometric data**. Only aggregate event counts and timing.
No face detection. No individual tracking across sessions. This is a hard constraint —
any feature request that requires storing keypoints per-person in retail context must be rejected.

## Key Domain Thresholds

| Domain | Correction trigger | Key signal |
|---|---|---|
| Yoga | Joint deviation > 15° | Spine, hip angle, knee over toe |
| Dance | Timing offset > 100ms | Foot placement vs beat grid |
| Retail | Dwell > 3s at shelf | Arm reach, object zone intersection |
| Sports | Joint deviation > 10° | Form vs optimal biomechanical template |
| Therapy | Any deviation from prescribed exercise | ROM degrees per joint |
