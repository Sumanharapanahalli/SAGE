"""
bias_analysis.py
────────────────
Demographic subgroup bias analysis for FDA SaMD AI symptom checker.

Regulatory basis
────────────────
  • FDA Guidance "Artificial Intelligence and Machine Learning (AI/ML)-Based
    Software as a Medical Device (SaMD) Action Plan" (Jan 2021):
      – "Developers should use datasets that are sufficiently large and
        representative … to evaluate performance … across sub-populations"
  • 21st Century Cures Act §3051 (health equity mandate)
  • IEC 62304:2006+AMD1:2015 §5.1.3 — software safety classification
    considers whether bias could cause harm to a sub-population.

Fairness definitions used
─────────────────────────
  • Demographic Parity Difference (DPD): |P(Ŷ=1|A=0) − P(Ŷ=1|A=1)|
    → 0 = perfect parity; FDA suggests <0.05 threshold for triage tools
  • Equalized Odds Difference (EOD): max of |TPR gap|, |FPR gap| across groups
  • Disparate Impact Ratio (DIR): min(P(Ŷ=1|A=a)) / max(P(Ŷ=1|A=a))
    → EEOC 4/5 rule: DIR < 0.8 flags a disparity worth investigating
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    roc_auc_score,
)

logger = logging.getLogger(__name__)

FAIRNESS_THRESHOLD_DPD = 0.05   # FDA-informed threshold for triage SaMD
FAIRNESS_THRESHOLD_EOD = 0.10
FAIRNESS_THRESHOLD_DIR = 0.80   # EEOC 4/5 rule


@dataclass
class GroupMetrics:
    group_name: str
    group_value: str
    n_samples: int
    prevalence: float          # % positive in this group
    sensitivity: float         # TPR
    specificity: float         # TNR
    ppv: float                 # precision
    npv: float
    f1: float
    auroc: float
    n_positive_pred: int
    positive_pred_rate: float


@dataclass
class FairnessReport:
    protected_attribute: str
    reference_group: str
    group_metrics: list[GroupMetrics]
    demographic_parity_diff: float
    equalized_odds_diff: float
    disparate_impact_ratio: float
    passes_dpd: bool
    passes_eod: bool
    passes_dir: bool
    statistical_significance: dict[str, float]  # group → p-value vs reference
    recommendations: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BiasAnalyzer:
    """
    Evaluate model predictions for bias across demographic subgroups.

    Parameters
    ----------
    artifact_dir : where to write plots and JSON reports
    """

    def __init__(self, artifact_dir: str = "regulatory/bias"):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def analyze(
        self,
        df: pd.DataFrame,
        y_true_col: str,
        y_pred_col: str,
        y_prob_col: str,
        protected_attributes: list[str] | None = None,
    ) -> dict[str, FairnessReport]:
        """
        Run bias analysis for each protected attribute.

        Returns a dict keyed by attribute name.
        Saves JSON + PNG artifacts for regulatory submission.
        """
        if protected_attributes is None:
            protected_attributes = [c for c in ["race", "gender", "age_group", "insurance"]
                                     if c in df.columns]

        reports: dict[str, FairnessReport] = {}
        for attr in protected_attributes:
            if attr not in df.columns:
                logger.warning("Attribute '%s' not in dataframe — skipping.", attr)
                continue
            logger.info("Bias analysis: attribute=%s", attr)
            report = self._analyze_attribute(df, y_true_col, y_pred_col, y_prob_col, attr)
            reports[attr] = report
            self._save_report(report)
            self._plot_group_metrics(report)

        self._save_summary(reports)
        return reports

    # ── Core analysis ─────────────────────────────────────────────────────────

    def _analyze_attribute(
        self,
        df: pd.DataFrame,
        y_true_col: str,
        y_pred_col: str,
        y_prob_col: str,
        attr: str,
    ) -> FairnessReport:
        groups = sorted(df[attr].dropna().unique())
        group_metrics: list[GroupMetrics] = []

        for grp in groups:
            mask = df[attr] == grp
            gdf = df[mask]
            if len(gdf) < 10:
                logger.warning("Group %s=%s has only %d samples — metrics unreliable.", attr, grp, len(gdf))
                continue
            gm = self._compute_group_metrics(attr, str(grp), gdf, y_true_col, y_pred_col, y_prob_col)
            group_metrics.append(gm)

        if not group_metrics:
            raise ValueError(f"No groups with sufficient samples for attribute '{attr}'.")

        # Choose reference group = largest group
        ref_group = max(group_metrics, key=lambda g: g.n_samples)
        ref = ref_group.group_value

        dpd = self._demographic_parity_diff(group_metrics)
        eod = self._equalized_odds_diff(group_metrics)
        dir_ = self._disparate_impact_ratio(group_metrics)
        sig = self._statistical_significance(df, y_true_col, y_pred_col, attr, ref)
        recs = self._build_recommendations(dpd, eod, dir_, group_metrics, attr)

        return FairnessReport(
            protected_attribute=attr,
            reference_group=ref,
            group_metrics=group_metrics,
            demographic_parity_diff=dpd,
            equalized_odds_diff=eod,
            disparate_impact_ratio=dir_,
            passes_dpd=dpd <= FAIRNESS_THRESHOLD_DPD,
            passes_eod=eod <= FAIRNESS_THRESHOLD_EOD,
            passes_dir=dir_ >= FAIRNESS_THRESHOLD_DIR,
            statistical_significance=sig,
            recommendations=recs,
        )

    def _compute_group_metrics(
        self,
        attr: str,
        grp: str,
        gdf: pd.DataFrame,
        y_true_col: str,
        y_pred_col: str,
        y_prob_col: str,
    ) -> GroupMetrics:
        y_true = gdf[y_true_col].values
        y_pred = gdf[y_pred_col].values
        y_prob = gdf[y_prob_col].values if y_prob_col in gdf.columns else None

        unique_classes = np.unique(y_true)

        # Binary metrics for positive class
        if len(unique_classes) == 2:
            tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
            sensitivity = tp / max(tp + fn, 1)
            specificity = tn / max(tn + fp, 1)
            ppv = tp / max(tp + fp, 1)
            npv = tn / max(tn + fn, 1)
        else:
            # For multi-class, use macro average
            cm = confusion_matrix(y_true, y_pred)
            sensitivity = np.diag(cm).sum() / max(cm.sum(), 1)
            specificity = sensitivity  # approximate
            ppv = sensitivity
            npv = sensitivity
            tn = fp = fn = tp = 0  # not meaningful for multi-class

        f1 = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))

        try:
            if y_prob is not None and len(unique_classes) == 2:
                auroc = float(roc_auc_score(y_true, y_prob))
            elif y_prob is not None:
                auroc = float(roc_auc_score(y_true, y_prob, multi_class="ovr", average="weighted"))
            else:
                auroc = float("nan")
        except Exception:
            auroc = float("nan")

        pos_preds = int((y_pred == 1).sum()) if len(unique_classes) == 2 else int(len(y_pred))
        pos_rate = pos_preds / max(len(y_pred), 1)

        return GroupMetrics(
            group_name=attr,
            group_value=grp,
            n_samples=len(gdf),
            prevalence=float(y_true.mean()) if len(unique_classes) == 2 else float("nan"),
            sensitivity=round(float(sensitivity), 4),
            specificity=round(float(specificity), 4),
            ppv=round(float(ppv), 4),
            npv=round(float(npv), 4),
            f1=round(f1, 4),
            auroc=round(auroc, 4),
            n_positive_pred=pos_preds,
            positive_pred_rate=round(pos_rate, 4),
        )

    # ── Fairness metrics ──────────────────────────────────────────────────────

    def _demographic_parity_diff(self, groups: list[GroupMetrics]) -> float:
        rates = [g.positive_pred_rate for g in groups]
        return round(max(rates) - min(rates), 4)

    def _equalized_odds_diff(self, groups: list[GroupMetrics]) -> float:
        tpr_diff = max(g.sensitivity for g in groups) - min(g.sensitivity for g in groups)
        fpr_diff = max(1 - g.specificity for g in groups) - min(1 - g.specificity for g in groups)
        return round(max(tpr_diff, fpr_diff), 4)

    def _disparate_impact_ratio(self, groups: list[GroupMetrics]) -> float:
        rates = [g.positive_pred_rate for g in groups if g.positive_pred_rate > 0]
        if not rates:
            return 1.0
        return round(min(rates) / max(rates), 4)

    def _statistical_significance(
        self,
        df: pd.DataFrame,
        y_true_col: str,
        y_pred_col: str,
        attr: str,
        ref_group: str,
    ) -> dict[str, float]:
        """Chi-squared test: error rate of reference vs each other group."""
        ref_mask = df[attr] == ref_group
        ref_errors = (df.loc[ref_mask, y_true_col] != df.loc[ref_mask, y_pred_col]).astype(int)
        results: dict[str, float] = {}
        for grp in df[attr].unique():
            if str(grp) == ref_group:
                continue
            g_mask = df[attr] == grp
            g_errors = (df.loc[g_mask, y_true_col] != df.loc[g_mask, y_pred_col]).astype(int)
            # 2×2 contingency: correct vs error, ref vs group
            table = np.array([
                [(ref_errors == 0).sum(), (ref_errors == 1).sum()],
                [(g_errors == 0).sum(),   (g_errors == 1).sum()],
            ])
            try:
                chi2, p, _, _ = stats.chi2_contingency(table)
                results[str(grp)] = round(float(p), 4)
            except Exception:
                results[str(grp)] = float("nan")
        return results

    def _build_recommendations(
        self,
        dpd: float,
        eod: float,
        dir_: float,
        groups: list[GroupMetrics],
        attr: str,
    ) -> list[str]:
        recs: list[str] = []
        if dpd > FAIRNESS_THRESHOLD_DPD:
            recs.append(
                f"[{attr}] Demographic Parity Difference {dpd:.3f} exceeds {FAIRNESS_THRESHOLD_DPD}. "
                "Consider reweighting training samples or post-hoc threshold calibration per group."
            )
        if eod > FAIRNESS_THRESHOLD_EOD:
            recs.append(
                f"[{attr}] Equalized Odds Difference {eod:.3f} exceeds {FAIRNESS_THRESHOLD_EOD}. "
                "Investigate differential error rates — could indicate distribution shift or label noise."
            )
        if dir_ < FAIRNESS_THRESHOLD_DIR:
            recs.append(
                f"[{attr}] Disparate Impact Ratio {dir_:.3f} < {FAIRNESS_THRESHOLD_DIR} (EEOC 4/5 rule). "
                "Model may systematically under-serve a subgroup — flag for clinical review."
            )
        small = [g for g in groups if g.n_samples < 100]
        if small:
            recs.append(
                f"[{attr}] Groups with <100 samples: {[g.group_value for g in small]}. "
                "Metrics are unreliable — seek additional data collection for these populations."
            )
        return recs

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_report(self, report: FairnessReport) -> None:
        path = self.artifact_dir / f"bias_{report.protected_attribute}.json"
        data: dict[str, Any] = {
            "protected_attribute": report.protected_attribute,
            "reference_group": report.reference_group,
            "demographic_parity_diff": report.demographic_parity_diff,
            "equalized_odds_diff": report.equalized_odds_diff,
            "disparate_impact_ratio": report.disparate_impact_ratio,
            "passes_dpd": report.passes_dpd,
            "passes_eod": report.passes_eod,
            "passes_dir": report.passes_dir,
            "statistical_significance": report.statistical_significance,
            "recommendations": report.recommendations,
            "timestamp": report.timestamp,
            "group_metrics": [gm.__dict__ for gm in report.group_metrics],
        }
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2)
        logger.info("Bias report saved → %s", path)

    def _save_summary(self, reports: dict[str, FairnessReport]) -> None:
        path = self.artifact_dir / "bias_summary.json"
        summary = {}
        for attr, r in reports.items():
            summary[attr] = {
                "dpd": r.demographic_parity_diff,
                "eod": r.equalized_odds_diff,
                "dir": r.disparate_impact_ratio,
                "passes_all": r.passes_dpd and r.passes_eod and r.passes_dir,
                "n_recommendations": len(r.recommendations),
            }
        with open(path, "w") as fh:
            json.dump(summary, fh, indent=2)

    def _plot_group_metrics(self, report: FairnessReport) -> None:
        groups = report.group_metrics
        if len(groups) < 2:
            return

        labels = [g.group_value for g in groups]
        metrics = {
            "Sensitivity": [g.sensitivity for g in groups],
            "Specificity": [g.specificity for g in groups],
            "F1": [g.f1 for g in groups],
            "AUROC": [g.auroc for g in groups],
        }

        x = np.arange(len(labels))
        width = 0.2
        fig, ax = plt.subplots(figsize=(max(10, len(labels) * 2), 5))
        for i, (metric, vals) in enumerate(metrics.items()):
            ax.bar(x + i * width, vals, width, label=metric)

        ax.set_xlabel(report.protected_attribute)
        ax.set_ylabel("Score")
        ax.set_title(
            f"Model performance by {report.protected_attribute}\n"
            f"DPD={report.demographic_parity_diff:.3f}  EOD={report.equalized_odds_diff:.3f}  "
            f"DIR={report.disparate_impact_ratio:.3f}"
        )
        ax.set_xticks(x + width * 1.5)
        ax.set_xticklabels(labels, rotation=30, ha="right")
        ax.set_ylim(0, 1.1)
        ax.legend()
        ax.axhline(0.9, color="gray", linestyle="--", linewidth=0.8, label="0.90 reference")
        plt.tight_layout()
        path = self.artifact_dir / f"bias_{report.protected_attribute}.png"
        plt.savefig(path, dpi=150)
        plt.close()
        logger.info("Bias plot saved → %s", path)
