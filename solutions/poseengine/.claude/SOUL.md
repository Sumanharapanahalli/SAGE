# SOUL.md — poseengine solution

## What This Solution Is

PoseEngine is a computer vision + Flutter mobile product. This SAGE solution
supports the team building the pose estimation ML pipeline and the Flutter apps
that consume it.

## Domain Context

- **ML pipeline:** PyTorch model training, ONNX export, mobile optimisation (TFLite/CoreML)
- **Mobile:** Flutter (Dart), Android + iOS, camera integration
- **CI/CD:** GitLab pipelines with GPU runners for model validation
- **Tracking:** WandB for experiment tracking, Firebase for app analytics

## Key Concerns

- Model quality regressions (accuracy on benchmark poses) are high priority
- Flutter breaking changes between SDK versions cause recurring MR failures
- The mobile team and the ML team have different review cadences — the analyst
  should route alerts to the right team

## Running

```bash
make run PROJECT=poseengine
make ui
```
