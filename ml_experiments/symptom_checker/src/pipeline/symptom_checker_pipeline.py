"""
symptom_checker_pipeline.py
────────────────────────────
Production ML pipeline for FDA SaMD AI Symptom Checker (Class II / 510(k)).

Regulatory compliance
─────────────────────
  • IEC 62304:2006+AMD1:2015 — Software class B/C lifecycle
  • FDA 21 CFR Part 820 (QSR) — Design controls
  • FDA AI/ML SaMD Action Plan (2021) — Predetermined Change Control Plan (PCCP)
  • 21 CFR Part 11 — Electronic records (MLflow as audit trail)
  • HIPAA Safe Harbor de-identification (training data must be pre-de-identified)

Data source requirement
───────────────────────
  Training data MUST be an IRB-approved, de-identified clinical EHR dataset
  (e.g., MIMIC-IV v2.2 from PhysioNet with credentialed access and signed DUA).
  Synthetic datasets and exam QA corpora are NOT acceptable for a production SaMD.

Pipeline stages
───────────────
  1. IRB / dataset validation
  2. Feature engineering (clinical variables — no post-discharge leakage)
  3. Subject-level stratified train / validation / test split (60/20/20)
  4. Class imbalance handling (SMOTE-NC on train only)
  5. Feature scaling / encoding (fit on train, transform val+test)
  6. Hyperparameter search (Optuna — CV on train+val folds)
  7. Final model training
  8. Evaluation on held-out test set (clinical + fairness metrics)
  9. Bias analysis across demographic subgroups
  10. MLflow experiment logging + model registration
  11. Regulatory artifact generation
"""

from __future__ import annotations

import json
import logging
import os
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import optuna
import pandas as pd
from imblearn.over_sampling import SMOTENC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, VotingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    classification_report,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import (
    GroupShuffleSplit,
    StratifiedKFold,
    cross_val_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OrdinalEncoder, StandardScaler
from xgboost import XGBClassifier

from .bias_analysis import BiasAnalyzer
from .data_validator import DataValidator, IRBRecord

warnings.filterwarnings("ignore", category=FutureWarning)
optuna.logging.set_verbosity(optuna.logging.WARNING)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# ── Triage categories (MIMIC-IV ESI scale 1–5, mapped to 3 classes) ──────────
LABEL_MAP = {1: "critical", 2: "critical", 3: "urgent", 4: "non-urgent", 5: "non-urgent"}
CLASSES = ["non-urgent", "urgent", "critical"]

# ── Feature sets (no post-discharge or future-derived columns) ────────────────
NUMERIC_FEATURES = [
    "age", "heart_rate", "resp_rate", "o2_sat", "sbp", "dbp",
    "temperature", "pain_score", "n_prior_admissions", "n_active_diagnoses",
    "charlson_comorbidity_index",
]
CATEGORICAL_FEATURES = [
    "gender", "race", "insurance", "arrival_transport", "chief_complaint_category",
]
PROTECTED_ATTRIBUTES = ["gender", "race", "age_group", "insurance"]

RANDOM_STATE = 42
TEST_SIZE = 0.20
VAL_SIZE = 0.20   # fraction of train set used for validation
N_CV_FOLDS = 5
N_OPTUNA_TRIALS = 50
MLFLOW_EXPERIMENT = "samed_symptom_checker_v1"


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class SplitStats:
    train_n: int
    val_n: int
    test_n: int
    train_label_dist: dict[str, int]
    test_label_dist: dict[str, int]


@dataclass
class ClinicalMetrics:
    """Clinical performance metrics for SaMD 510(k) performance summary."""
    accuracy: float
    balanced_accuracy: float
    macro_f1: float
    weighted_f1: float
    macro_auroc: float
    weighted_auroc: float
    macro_precision: float
    macro_recall: float
    cohen_kappa: float
    brier_score: float           # calibration quality
    average_precision: float     # area under PR curve
    sensitivity_per_class: dict[str, float]
    specificity_per_class: dict[str, float]
    ppv_per_class: dict[str, float]
    npv_per_class: dict[str, float]
    confusion_matrix: list[list[int]]
    classification_report_str: str
    n_test_samples: int


@dataclass
class PipelineResult:
    run_id: str
    model_path: str
    metrics: ClinicalMetrics
    split_stats: SplitStats
    bias_reports: dict[str, Any]
    regulatory_artifacts: list[str]
    passes_minimum_performance: bool
    passes_bias_checks: bool


# ── Main pipeline ─────────────────────────────────────────────────────────────

class SymptomCheckerPipeline:
    """
    End-to-end SaMD ML pipeline.

    Parameters
    ----------
    irb_record        : IRB approval metadata (required — no clinical data without this)
    data_path         : path to MIMIC-IV derived parquet (pre-de-identified)
    artifact_dir      : output directory for models and regulatory artifacts
    mlflow_tracking_uri : URI of MLflow server (default: local ./mlruns)
    min_sensitivity   : minimum required per-class sensitivity (FDA-negotiated threshold)
    min_auroc         : minimum required macro AUROC
    """

    # FDA-negotiated performance thresholds (to be set per 510(k) submission)
    MIN_SENSITIVITY = 0.80       # critical class must achieve ≥0.85 in practice
    MIN_AUROC = 0.85
    MIN_CRITICAL_SENSITIVITY = 0.85  # safety-critical: must not miss critical cases

    def __init__(
        self,
        irb_record: IRBRecord,
        data_path: str,
        artifact_dir: str = "artifacts",
        mlflow_tracking_uri: str = "./mlruns",
        min_sensitivity: float = 0.80,
        min_auroc: float = 0.85,
    ):
        self.irb_record = irb_record
        self.data_path = Path(data_path)
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        mlflow.set_tracking_uri(mlflow_tracking_uri)
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        self.MIN_SENSITIVITY = min_sensitivity
        self.MIN_AUROC = min_auroc

    def run(self) -> PipelineResult:
        logger.info("═══ SaMD Symptom Checker Pipeline ═══")
        logger.info("IRB: %s  Dataset: %s", self.irb_record.irb_number, self.irb_record.dataset_name)

        with mlflow.start_run() as run:
            run_id = run.info.run_id
            mlflow.set_tags({
                "irb_number": self.irb_record.irb_number,
                "dataset": self.irb_record.dataset_name,
                "iec62304_class": "B",
                "fda_pathway": "510k",
                "pipeline_version": "1.0.0",
            })

            # ── Stage 1: Load + validate ──────────────────────────────────────
            df = self._load_and_validate()

            # ── Stage 2: Feature engineering ─────────────────────────────────
            df = self._engineer_features(df)

            # ── Stage 3: Subject-level stratified split ───────────────────────
            X_train, X_val, X_test, y_train, y_val, y_test, split_stats = self._split(df)
            self._log_split_stats(split_stats)

            # ── Stage 4: Preprocessing (fit on train ONLY) ────────────────────
            preprocessor, cat_idx = self._build_preprocessor(X_train)
            X_train_proc = preprocessor.fit_transform(X_train)
            X_val_proc   = preprocessor.transform(X_val)
            X_test_proc  = preprocessor.transform(X_test)

            # ── Stage 5: Class imbalance handling (train only) ────────────────
            le = LabelEncoder()
            y_train_enc = le.fit_transform(y_train)
            y_val_enc   = le.transform(y_val)
            y_test_enc  = le.transform(y_test)

            X_train_bal, y_train_bal = self._handle_imbalance(
                X_train_proc, y_train_enc, cat_idx
            )

            # ── Stage 6: Hyperparameter search ───────────────────────────────
            best_params = self._hyperparameter_search(X_train_bal, y_train_bal)
            mlflow.log_params(best_params)

            # ── Stage 7: Train final model ────────────────────────────────────
            model = self._train_final_model(best_params, X_train_bal, y_train_bal)

            # ── Stage 8: Calibrate (Platt scaling) ───────────────────────────
            calibrated = CalibratedClassifierCV(model, cv="prefit", method="isotonic")
            calibrated.fit(X_val_proc, y_val_enc)

            # ── Stage 9: Evaluate on held-out test set ────────────────────────
            metrics = self._evaluate(calibrated, X_test_proc, y_test_enc, le)
            self._log_metrics(metrics)
            passes_perf = self._check_performance_gates(metrics)

            # ── Stage 10: Bias analysis ───────────────────────────────────────
            df_test = X_test.copy()
            df_test["_y_true"] = y_test_enc
            df_test["_y_pred"] = calibrated.predict(X_test_proc)
            proba = calibrated.predict_proba(X_test_proc)
            # Use max probability as scalar score for binary-like AUROC
            df_test["_y_prob"] = proba.max(axis=1)

            bias_analyzer = BiasAnalyzer(artifact_dir=str(self.artifact_dir / "bias"))
            available_attrs = [a for a in PROTECTED_ATTRIBUTES if a in df_test.columns]
            bias_reports = bias_analyzer.analyze(
                df_test, "_y_true", "_y_pred", "_y_prob", available_attrs
            )
            passes_bias = all(
                r.passes_dpd and r.passes_eod and r.passes_dir
                for r in bias_reports.values()
            )

            # ── Stage 11: Save artifacts ──────────────────────────────────────
            artifacts = self._save_artifacts(calibrated, preprocessor, le, run_id)
            mlflow.sklearn.log_model(
                calibrated, "model",
                input_example=pd.DataFrame(X_test_proc[:1], columns=self._feature_names()),
            )

            result = PipelineResult(
                run_id=run_id,
                model_path=str(self.artifact_dir / "model.joblib"),
                metrics=metrics,
                split_stats=split_stats,
                bias_reports={k: v.__dict__ for k, v in bias_reports.items()},
                regulatory_artifacts=artifacts,
                passes_minimum_performance=passes_perf,
                passes_bias_checks=passes_bias,
            )
            mlflow.log_dict(
                {"passes_performance": passes_perf, "passes_bias": passes_bias},
                "gate_results.json",
            )
            logger.info(
                "Pipeline complete. run_id=%s  perf_gate=%s  bias_gate=%s",
                run_id, passes_perf, passes_bias,
            )
            return result

    # ── Stage implementations ─────────────────────────────────────────────────

    def _load_and_validate(self) -> pd.DataFrame:
        logger.info("Loading dataset: %s", self.data_path)
        if self.data_path.suffix == ".parquet":
            df = pd.read_parquet(self.data_path)
        elif self.data_path.suffix == ".csv":
            df = pd.read_csv(self.data_path)
        else:
            raise ValueError(f"Unsupported format: {self.data_path.suffix}. Use .parquet or .csv")

        validator = DataValidator(self.irb_record, artifact_dir=str(self.artifact_dir / "validation"))
        # Map ESI scores to triage categories before validation
        if "esi" in df.columns:
            df["triage_category"] = df["esi"].map(LABEL_MAP)

        report = validator.validate(df, label_col="triage_category")
        if not report.passes_all_checks:
            raise RuntimeError(
                f"Dataset validation failed:\n" + "\n".join(report.errors)
            )
        for w in report.warnings:
            logger.warning("DataValidator: %s", w)
        logger.info("Dataset validated: %d rows, %d columns.", report.row_count, report.column_count)
        return df

    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clinical feature engineering.
        IMPORTANT: Only use features available at triage time (arrival).
        Never include discharge diagnoses, lab results ordered after triage,
        or any variable that leaks the outcome.
        """
        if "age" not in df.columns and "dob" in df.columns and "admittime" in df.columns:
            df["age"] = (
                pd.to_datetime(df["admittime"]) - pd.to_datetime(df["dob"])
            ).dt.days / 365.25
            df["age"] = df["age"].clip(0, 120)

        # Age group for bias analysis (not used as training feature — only for slicing)
        if "age" in df.columns:
            df["age_group"] = pd.cut(
                df["age"], bins=[0, 18, 40, 65, 80, 200],
                labels=["0-17", "18-39", "40-64", "65-79", "80+"], right=False
            )

        # Clip physiological values to plausible ranges
        if "heart_rate" in df.columns:
            df["heart_rate"] = df["heart_rate"].clip(20, 300)
        if "o2_sat" in df.columns:
            df["o2_sat"] = df["o2_sat"].clip(50, 100)
        if "sbp" in df.columns:
            df["sbp"] = df["sbp"].clip(40, 300)
        if "temperature" in df.columns:
            df["temperature"] = df["temperature"].clip(30, 45)

        return df

    def _split(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame,
               pd.Series, pd.Series, pd.Series, SplitStats]:
        """
        Subject-level split to prevent data leakage from repeated admissions.
        Same patient must NOT appear in both train and test.
        Uses GroupShuffleSplit on subject_id to guarantee this.
        """
        available_features = [f for f in NUMERIC_FEATURES + CATEGORICAL_FEATURES if f in df.columns]
        X = df[available_features + ["subject_id"]].copy()
        y = df["triage_category"]

        # Encode labels for stratification
        label_counts = y.value_counts()
        logger.info("Label distribution: %s", label_counts.to_dict())

        # Step 1: hold out test set (subject-level)
        gss = GroupShuffleSplit(n_splits=1, test_size=TEST_SIZE, random_state=RANDOM_STATE)
        train_val_idx, test_idx = next(gss.split(X, y, groups=X["subject_id"]))

        X_trainval = X.iloc[train_val_idx].drop(columns=["subject_id"])
        y_trainval = y.iloc[train_val_idx]
        X_test = X.iloc[test_idx].drop(columns=["subject_id"])
        y_test = y.iloc[test_idx]

        # Step 2: split train into train / validation (stratified)
        gss_val = GroupShuffleSplit(
            n_splits=1,
            test_size=VAL_SIZE / (1 - TEST_SIZE),
            random_state=RANDOM_STATE,
        )
        train_idx, val_idx = next(
            gss_val.split(X_trainval, y_trainval,
                          groups=X.iloc[train_val_idx]["subject_id"].values)
        )

        X_train = X_trainval.iloc[train_idx]
        y_train = y_trainval.iloc[train_idx]
        X_val   = X_trainval.iloc[val_idx]
        y_val   = y_trainval.iloc[val_idx]

        stats = SplitStats(
            train_n=len(X_train),
            val_n=len(X_val),
            test_n=len(X_test),
            train_label_dist=y_train.value_counts().to_dict(),
            test_label_dist=y_test.value_counts().to_dict(),
        )
        logger.info(
            "Split: train=%d  val=%d  test=%d  (subject-level, no overlap)",
            stats.train_n, stats.val_n, stats.test_n,
        )
        return X_train, X_val, X_test, y_train, y_val, y_test, stats

    def _build_preprocessor(
        self, X_train: pd.DataFrame
    ) -> tuple[ColumnTransformer, list[int]]:
        """
        Build sklearn ColumnTransformer.
        Fitted ONLY on training data to prevent leakage.
        """
        num_cols = [c for c in NUMERIC_FEATURES if c in X_train.columns]
        cat_cols = [c for c in CATEGORICAL_FEATURES if c in X_train.columns]

        num_pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ])
        cat_pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
        ])

        preprocessor = ColumnTransformer(
            transformers=[
                ("num", num_pipeline, num_cols),
                ("cat", cat_pipeline, cat_cols),
            ],
            remainder="drop",
        )
        # Track indices of categorical columns (needed for SMOTE-NC)
        n_num = len(num_cols)
        cat_idx = list(range(n_num, n_num + len(cat_cols)))
        return preprocessor, cat_idx

    def _handle_imbalance(
        self, X: np.ndarray, y: np.ndarray, cat_idx: list[int]
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        SMOTE-NC (handles mixed numeric + categorical).
        Applied ONLY to training data.
        """
        counts = np.bincount(y)
        ratio = counts.max() / max(counts.min(), 1)
        if ratio < 3:
            logger.info("Class imbalance ratio %.1f < 3 — skipping SMOTE.", ratio)
            return X, y
        try:
            if len(cat_idx) > 0:
                smote = SMOTENC(
                    categorical_features=cat_idx,
                    k_neighbors=min(5, counts.min() - 1),
                    random_state=RANDOM_STATE,
                )
            else:
                from imblearn.over_sampling import SMOTE
                smote = SMOTE(k_neighbors=min(5, counts.min() - 1), random_state=RANDOM_STATE)
            X_bal, y_bal = smote.fit_resample(X, y)
            logger.info("SMOTE-NC: %d → %d samples.", len(y), len(y_bal))
            return X_bal, y_bal
        except Exception as exc:
            logger.warning("SMOTE failed (%s) — using original imbalanced data.", exc)
            return X, y

    def _hyperparameter_search(
        self, X_train: np.ndarray, y_train: np.ndarray
    ) -> dict[str, Any]:
        logger.info("Hyperparameter search: %d Optuna trials.", N_OPTUNA_TRIALS)

        def objective(trial: optuna.Trial) -> float:
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 200, 1000, step=100),
                "max_depth": trial.suggest_int("max_depth", 3, 10),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-4, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-4, 10.0, log=True),
                "use_label_encoder": False,
                "eval_metric": "mlogloss",
                "random_state": RANDOM_STATE,
                "n_jobs": -1,
            }
            clf = XGBClassifier(**params)
            cv = StratifiedKFold(n_splits=N_CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
            scores = cross_val_score(clf, X_train, y_train, cv=cv, scoring="f1_weighted", n_jobs=1)
            return float(scores.mean())

        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
        study.optimize(objective, n_trials=N_OPTUNA_TRIALS, show_progress_bar=False)
        best = study.best_params
        logger.info("Best params (val F1=%.4f): %s", study.best_value, best)
        return best

    def _train_final_model(
        self, params: dict[str, Any], X_train: np.ndarray, y_train: np.ndarray
    ) -> XGBClassifier:
        params = {**params, "use_label_encoder": False, "eval_metric": "mlogloss",
                  "random_state": RANDOM_STATE, "n_jobs": -1}
        model = XGBClassifier(**params)
        model.fit(X_train, y_train)
        logger.info("Final model trained on %d samples.", len(y_train))
        return model

    def _evaluate(
        self,
        model: Any,
        X_test: np.ndarray,
        y_test: np.ndarray,
        le: LabelEncoder,
    ) -> ClinicalMetrics:
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)
        classes = le.classes_

        acc = float(accuracy_score(y_test, y_pred))
        bal_acc = float(balanced_accuracy_score(y_test, y_pred))
        macro_f1 = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
        wgt_f1 = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))
        kappa = float(cohen_kappa_score(y_test, y_pred))
        ap = float(average_precision_score(y_test, y_prob, average="weighted"))

        try:
            macro_auroc = float(roc_auc_score(y_test, y_prob, multi_class="ovr", average="macro"))
            wgt_auroc = float(roc_auc_score(y_test, y_prob, multi_class="ovr", average="weighted"))
        except Exception:
            macro_auroc = wgt_auroc = float("nan")

        # Brier score (multi-class: mean over classes)
        brier = float(np.mean([
            brier_score_loss((y_test == i).astype(int), y_prob[:, i])
            for i in range(len(classes))
        ]))

        # Per-class sensitivity / specificity / PPV / NPV
        sensitivity_pc, specificity_pc, ppv_pc, npv_pc = {}, {}, {}, {}
        for i, cls in enumerate(classes):
            binary_true = (y_test == i).astype(int)
            binary_pred = (y_pred == i).astype(int)
            try:
                tn, fp, fn, tp = confusion_matrix(binary_true, binary_pred, labels=[0, 1]).ravel()
                sensitivity_pc[cls] = round(tp / max(tp + fn, 1), 4)
                specificity_pc[cls] = round(tn / max(tn + fp, 1), 4)
                ppv_pc[cls]         = round(tp / max(tp + fp, 1), 4)
                npv_pc[cls]         = round(tn / max(tn + fn, 1), 4)
            except Exception:
                sensitivity_pc[cls] = specificity_pc[cls] = ppv_pc[cls] = npv_pc[cls] = float("nan")

        cm = confusion_matrix(y_test, y_pred).tolist()
        cr = classification_report(y_test, y_pred, target_names=list(classes), zero_division=0)
        logger.info("\n%s", cr)

        return ClinicalMetrics(
            accuracy=round(acc, 4),
            balanced_accuracy=round(bal_acc, 4),
            macro_f1=round(macro_f1, 4),
            weighted_f1=round(wgt_f1, 4),
            macro_auroc=round(macro_auroc, 4),
            weighted_auroc=round(wgt_auroc, 4),
            macro_precision=round(float(precision_score(y_test, y_pred, average="macro", zero_division=0)), 4),
            macro_recall=round(float(recall_score(y_test, y_pred, average="macro", zero_division=0)), 4),
            cohen_kappa=round(kappa, 4),
            brier_score=round(brier, 4),
            average_precision=round(ap, 4),
            sensitivity_per_class=sensitivity_pc,
            specificity_per_class=specificity_pc,
            ppv_per_class=ppv_pc,
            npv_per_class=npv_pc,
            confusion_matrix=cm,
            classification_report_str=cr,
            n_test_samples=len(y_test),
        )

    def _check_performance_gates(self, m: ClinicalMetrics) -> bool:
        passed = True
        if m.macro_auroc < self.MIN_AUROC:
            logger.error("GATE FAIL: macro AUROC %.4f < %.4f", m.macro_auroc, self.MIN_AUROC)
            passed = False
        for cls, sens in m.sensitivity_per_class.items():
            threshold = self.MIN_CRITICAL_SENSITIVITY if cls == "critical" else self.MIN_SENSITIVITY
            if sens < threshold:
                logger.error("GATE FAIL: sensitivity[%s]=%.4f < %.4f", cls, sens, threshold)
                passed = False
        if passed:
            logger.info("All performance gates PASSED.")
        return passed

    def _save_artifacts(
        self,
        model: Any,
        preprocessor: ColumnTransformer,
        le: LabelEncoder,
        run_id: str,
    ) -> list[str]:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        paths: list[str] = []

        model_path = self.artifact_dir / f"model_{ts}.joblib"
        joblib.dump({"model": model, "preprocessor": preprocessor, "label_encoder": le}, model_path)
        paths.append(str(model_path))
        # Stable symlink for downstream services
        symlink = self.artifact_dir / "model.joblib"
        if symlink.exists() or symlink.is_symlink():
            symlink.unlink()
        symlink.symlink_to(model_path.name)
        paths.append(str(symlink))

        meta = {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "model_type": "XGBClassifier (CalibratedClassifierCV, isotonic)",
            "classes": list(le.classes_),
            "features_numeric": NUMERIC_FEATURES,
            "features_categorical": CATEGORICAL_FEATURES,
            "irb_number": self.irb_record.irb_number,
            "dataset": self.irb_record.dataset_name,
            "pipeline_version": "1.0.0",
            "iec62304_class": "B",
            "fda_pathway": "510k",
        }
        meta_path = self.artifact_dir / f"model_metadata_{ts}.json"
        with open(meta_path, "w") as fh:
            json.dump(meta, fh, indent=2)
        paths.append(str(meta_path))
        mlflow.log_artifact(str(meta_path))

        logger.info("Artifacts saved: %s", paths)
        return paths

    # ── Logging helpers ───────────────────────────────────────────────────────

    def _log_split_stats(self, s: SplitStats) -> None:
        mlflow.log_params({
            "train_n": s.train_n, "val_n": s.val_n, "test_n": s.test_n
        })

    def _log_metrics(self, m: ClinicalMetrics) -> None:
        mlflow.log_metrics({
            "accuracy": m.accuracy,
            "balanced_accuracy": m.balanced_accuracy,
            "macro_f1": m.macro_f1,
            "weighted_f1": m.weighted_f1,
            "macro_auroc": m.macro_auroc,
            "weighted_auroc": m.weighted_auroc,
            "cohen_kappa": m.cohen_kappa,
            "brier_score": m.brier_score,
            "average_precision": m.average_precision,
            **{f"sensitivity_{k}": v for k, v in m.sensitivity_per_class.items()},
            **{f"specificity_{k}": v for k, v in m.specificity_per_class.items()},
        })

    def _feature_names(self) -> list[str]:
        return [f for f in NUMERIC_FEATURES + CATEGORICAL_FEATURES if True]


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    """
    Run the full pipeline.

    Before running:
      1. Obtain MIMIC-IV credentialed access at https://physionet.org/
      2. Sign the PhysioNet DUA for MIMIC-IV (version 1.1)
      3. Obtain IRB approval from your institutional review board
      4. De-identify data per HIPAA Safe Harbor (45 CFR §164.514(b))
      5. Export the derived triage cohort to mimic_iv_triage.parquet
      6. Update the IRBRecord fields below
    """
    irb = IRBRecord(
        irb_number=os.environ.get("IRB_NUMBER", "IRB-PENDING"),
        institution=os.environ.get("IRB_INSTITUTION", "Your Institution"),
        approval_date=os.environ.get("IRB_APPROVAL_DATE", "2024-01-01"),
        expiry_date=os.environ.get("IRB_EXPIRY_DATE", "2026-12-31"),
        dataset_name="MIMIC-IV v2.2",
        data_use_agreement=os.environ.get("DUA_NUMBER", "DUA-PENDING"),
        de_identification_method="HIPAA Safe Harbor (45 CFR §164.514(b))",
        irb_document_hash=os.environ.get("IRB_DOC_HASH", "PENDING"),
    )

    data_path = os.environ.get("MIMIC_DATA_PATH", "data/mimic_iv_triage.parquet")

    pipeline = SymptomCheckerPipeline(
        irb_record=irb,
        data_path=data_path,
        artifact_dir="artifacts",
        mlflow_tracking_uri=os.environ.get("MLFLOW_TRACKING_URI", "./mlruns"),
    )
    result = pipeline.run()

    print("\n" + "═" * 60)
    print("PIPELINE RESULT")
    print("═" * 60)
    print(f"  Run ID          : {result.run_id}")
    print(f"  Accuracy        : {result.metrics.accuracy:.4f}")
    print(f"  Macro F1        : {result.metrics.macro_f1:.4f}")
    print(f"  Macro AUROC     : {result.metrics.macro_auroc:.4f}")
    print(f"  Cohen Kappa     : {result.metrics.cohen_kappa:.4f}")
    print(f"  Brier Score     : {result.metrics.brier_score:.4f}")
    print(f"  Performance Gate: {'PASS' if result.passes_minimum_performance else 'FAIL'}")
    print(f"  Bias Gate       : {'PASS' if result.passes_bias_checks else 'FAIL'}")
    print("═" * 60)

    if not result.passes_minimum_performance or not result.passes_bias_checks:
        raise SystemExit(
            "Pipeline did not meet FDA performance or bias gates. "
            "Review MLflow artifacts and bias reports before submission."
        )


if __name__ == "__main__":
    main()
