"""
SAGE Framework — OpenML (Machine Learning) Runner
===================================================
Domain-specific execution for data science and ML engineering.

Workflow: load data → EDA → feature engineer → train → evaluate → track experiment

Differs from OpenSWE because:
  - Verification is metric-based (accuracy, F1), not boolean pass/fail
  - Training may require GPU
  - Data leakage detection is a first-class concern
  - Experiment tracking (MLflow) is mandatory for reproducibility

Roles: data_scientist
Docker: sage/ml-toolchain:latest
"""

import logging

from src.integrations.base_runner import (
    BaseRunner, RunResult, VerificationReport, VerificationFinding,
    VerificationSeverity, Exercise, ExerciseScore,
    register_runner, ML_ROLES,
)

logger = logging.getLogger("Runner.openml")


class OpenMLRunner(BaseRunner):
    """Machine learning execution runner."""

    def __init__(self):
        super().__init__(
            name="openml",
            roles=list(ML_ROLES),
            docker_image="sage/ml-toolchain:latest",
        )

    def execute(self, task, workspace, sandbox_handle=None):
        run_id = self._new_run_id()
        try:
            description = task.get("description", "")
            task_type = task.get("task_type", "ML_MODEL")

            from src.core.llm_gateway import llm_gateway

            system_prompt = (
                "You are a senior data scientist / ML engineer.\n"
                "Generate production-quality ML code following these rules:\n"
                "- Always split data with stratification for classification\n"
                "- Never fit scalers/encoders on test data (data leakage)\n"
                "- Include evaluation metrics appropriate for the problem\n"
                "- Log all experiments with parameters and results\n"
                "- Include requirements.txt with pinned versions\n\n"
                "Output as JSON: {\"files\": [{\"path\": \"...\", \"content\": \"...\"}], "
                "\"model_type\": \"...\", \"metrics\": {\"accuracy\": N, \"f1\": N}, "
                "\"data_checks\": {\"leakage_risk\": false, \"class_imbalance\": false}}\n"
            )

            response = llm_gateway.generate_for_task(
                task_type=task_type,
                prompt=f"Task: {description}",
                system_prompt=system_prompt,
                trace_name="openml.generate",
            )

            files_changed = []
            metrics = {}
            try:
                import json
                start = response.find("{")
                end = response.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(response[start:end])
                    files_changed = [f["path"] for f in parsed.get("files", [])]
                    metrics.update(parsed.get("metrics", {}))
                    metrics["model_type"] = parsed.get("model_type", "unknown")
                    metrics["data_checks"] = parsed.get("data_checks", {})
            except Exception:
                pass

            return self._make_result(
                run_id=run_id, status="completed", tier="direct",
                output=response, files_changed=files_changed, metrics=metrics,
            )
        except Exception as exc:
            self.logger.error("OpenML execute failed: %s", exc)
            return self._make_error(run_id, str(exc))

    def verify(self, result, task):
        findings = []
        score = 30.0

        if result.status == "error":
            return VerificationReport(passed=False, score=0.0, findings=[
                VerificationFinding("execution", VerificationSeverity.ERROR, "Failed"),
            ])

        metrics = result.metrics or {}

        # Check for suspiciously perfect metrics (data leakage signal)
        accuracy = metrics.get("accuracy")
        f1 = metrics.get("f1")
        if accuracy is not None and accuracy >= 0.99:
            findings.append(VerificationFinding(
                "leakage_warning", VerificationSeverity.WARNING,
                f"Suspiciously high accuracy ({accuracy}) — check for data leakage",
            ))
            score -= 10
        elif accuracy is not None and accuracy > 0:
            score += 20
            findings.append(VerificationFinding(
                "accuracy", VerificationSeverity.PASS, f"Accuracy: {accuracy}",
            ))

        if f1 is not None and f1 >= 0.99:
            findings.append(VerificationFinding(
                "leakage_warning_f1", VerificationSeverity.WARNING,
                f"Suspiciously high F1 ({f1}) — check for data leakage",
            ))

        # Check data leakage flags
        data_checks = metrics.get("data_checks", {})
        if data_checks.get("leakage_risk"):
            findings.append(VerificationFinding(
                "data_leakage", VerificationSeverity.CRITICAL,
                "Data leakage risk detected",
            ))
            score -= 20

        # Files produced
        if result.files_changed:
            score += 15

        # ML keywords
        output_lower = (result.output or "").lower()
        ml_kws = ["train", "test", "split", "accuracy", "model", "predict", "evaluate", "feature"]
        if sum(1 for k in ml_kws if k in output_lower) >= 3:
            score += 15

        # Metric presence
        if any(k in metrics for k in ["accuracy", "f1", "auc", "rmse", "loss"]):
            score += 10

        score = max(0.0, min(score, 100.0))
        return VerificationReport(passed=score >= 40.0, score=score, findings=findings, metrics=metrics)

    def get_toolchain(self):
        return {
            "runner": self.name, "docker_image": self.docker_image,
            "roles": self.roles,
            "tools": ["python", "jupyter", "pandas", "sklearn", "pytorch", "mlflow"],
            "packages": ["pandas", "scikit-learn", "pytorch", "mlflow", "numpy",
                         "matplotlib", "seaborn", "xgboost", "lightgbm"],
        }

    def get_workflow(self):
        return [
            {"step": 1, "name": "data_load", "description": "Load and inspect dataset"},
            {"step": 2, "name": "eda", "description": "Exploratory data analysis"},
            {"step": 3, "name": "feature_engineering", "description": "Create and select features"},
            {"step": 4, "name": "train", "description": "Train model with cross-validation"},
            {"step": 5, "name": "training", "description": "Hyperparameter tuning"},
            {"step": 6, "name": "evaluate", "description": "Evaluate on held-out test set"},
            {"step": 7, "name": "experiment_track", "description": "Log experiment to MLflow"},
            {"step": 8, "name": "package", "description": "Package model for deployment"},
        ]

    def get_experience_keys(self):
        return ["task_type", "data_type", "model_family", "metric_target", "domain"]

    def get_exercises(self, difficulty="intermediate"):
        exercises = {
            "beginner": [
                Exercise(
                    id="ml-b01", role="data_scientist", task_type="ML_MODEL",
                    difficulty="beginner",
                    description="Train an iris flower classifier using scikit-learn",
                    acceptance_criteria=[
                        "Model accuracy > 0.90 on test set",
                        "Uses stratified train/test split",
                        "Evaluates with classification report",
                        "No data leakage (scaler fit on train only)",
                    ],
                    expected_artifacts=["train.py", "requirements.txt"],
                    tags=["classification", "sklearn", "beginner"],
                ),
            ],
            "intermediate": [
                Exercise(
                    id="ml-i01", role="data_scientist", task_type="ML_MODEL",
                    difficulty="intermediate",
                    description="Build a credit card fraud detector handling class imbalance",
                    acceptance_criteria=[
                        "Handles class imbalance (SMOTE or class weights)",
                        "F1 score > 0.75 on minority class",
                        "No data leakage in pipeline",
                        "Experiment tracked with MLflow",
                        "Model evaluation includes precision-recall curve",
                    ],
                    expected_artifacts=["fraud_detector.py", "evaluate.py", "requirements.txt"],
                    tags=["classification", "imbalanced", "fraud"],
                ),
            ],
            "advanced": [
                Exercise(
                    id="ml-a01", role="data_scientist", task_type="ML_MODEL",
                    difficulty="advanced",
                    description="Build an end-to-end time series forecasting pipeline for energy demand",
                    acceptance_criteria=[
                        "Feature engineering includes lag, rolling, calendar features",
                        "Model comparison (at least 2 approaches)",
                        "RMSE and MAPE metrics reported",
                        "Walk-forward validation (not random split)",
                        "Inference latency < 100ms",
                    ],
                    expected_artifacts=["pipeline.py", "features.py", "evaluate.py", "requirements.txt"],
                    tags=["timeseries", "forecasting", "advanced"],
                ),
            ],
        }
        return exercises.get(difficulty, exercises["intermediate"])

    def grade_exercise(self, exercise, result):
        score = 0.0
        criteria_results = {}
        hints = []

        if result.status == "completed":
            score += 20
            criteria_results["execution_success"] = True

        expected = set(exercise.expected_artifacts)
        produced = set(result.files_changed)
        match = len(expected & produced) / max(len(expected), 1)
        score += match * 20
        criteria_results["artifacts_match"] = match >= 0.5

        metrics = result.metrics or {}
        # Check model metrics
        acc = metrics.get("accuracy")
        f1 = metrics.get("f1")
        if acc is not None and acc > 0:
            score += 15
            criteria_results["has_accuracy"] = True
            if acc >= 0.99:
                hints.append("Perfect accuracy may indicate data leakage")
                score -= 5
        if f1 is not None and f1 > 0:
            score += 10
            criteria_results["has_f1"] = True

        # ML keywords
        output_lower = (result.output or "").lower()
        ml_kws = ["train", "test", "split", "fit", "predict", "score", "accuracy"]
        if sum(1 for k in ml_kws if k in output_lower) >= 3:
            score += 15
            criteria_results["ml_patterns"] = True

        if result.verification and result.verification.passed:
            score += 10

        score = max(0.0, min(score, 100.0))
        return ExerciseScore(
            exercise_id=exercise.id, passed=score >= 50, score=score,
            criteria_results=criteria_results,
            feedback="Solid ML work" if score >= 70 else "Review ML best practices",
            improvement_hints=hints,
        )


_runner = OpenMLRunner()
register_runner(_runner)
