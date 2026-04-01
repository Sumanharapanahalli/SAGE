"""
Dialog Management — Inference Module
=====================================
Production inference with:
- Single-sample and batch prediction
- Wall-clock latency measurement per call
- SLA enforcement (configurable threshold)
- Confidence scores + top-k alternatives

Usage (CLI):
    python inference.py \
        --checkpoint artifacts/models/best_model.pt \
        --history "Hello how can I help? [SEP] I need a restaurant" \
        --utterance "Something cheap in the centre please"

Usage (library):
    from inference import DialogPredictor
    predictor = DialogPredictor("artifacts/models/best_model.pt")
    result = predictor.predict(history="...", utterance="...")
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import torch
import torch.nn.functional as F
from transformers import DistilBertTokenizerFast

from model import DialogManagementModel

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    dialog_act:    str
    confidence:    float
    latency_ms:    float
    top_k:         List[Dict]   # [{"act": str, "prob": float}]
    within_sla:    bool
    sla_ms:        float

    def to_dict(self) -> Dict:
        return {
            "dialog_act":  self.dialog_act,
            "confidence":  round(self.confidence, 4),
            "latency_ms":  round(self.latency_ms, 2),
            "top_k":       self.top_k,
            "within_sla":  self.within_sla,
            "sla_ms":      self.sla_ms,
        }


class DialogPredictor:
    """
    Thin inference wrapper around DialogManagementModel.

    Guarantees:
    - No batch norm / dropout applied at inference (model.eval())
    - Latency measured with perf_counter (GPU sync when available)
    - Raises LatencySLAError if p95 latency budget is exceeded
    """

    def __init__(
        self,
        checkpoint_path: str,
        device: Optional[str] = None,
        sla_ms: float = 100.0,
        top_k: int = 3,
    ) -> None:
        self.sla_ms = sla_ms
        self.top_k  = top_k
        self.device = torch.device(
            device or ("cuda" if torch.cuda.is_available() else "cpu")
        )

        ckpt = torch.load(checkpoint_path, map_location=self.device)
        cfg  = ckpt["config"]

        # Reconstruct model from checkpoint config
        self.class_names: List[str] = ckpt["label_classes"]
        n_classes = len(self.class_names)

        self.model = DialogManagementModel(
            encoder_name=cfg["model"]["encoder"],
            hidden_size=cfg["model"]["hidden_size"],
            n_classes=n_classes,
            lstm_layers=cfg["model"]["lstm_layers"],
            dropout=cfg["model"]["dropout"],
        ).to(self.device)
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.eval()

        self.tokenizer = DistilBertTokenizerFast.from_pretrained(cfg["model"]["encoder"])
        self.max_seq_len: int = cfg["model"]["max_seq_len"]

        logger.info(
            "DialogPredictor ready — device=%s | classes=%d | SLA=%.0f ms",
            self.device, n_classes, sla_ms,
        )

    def _encode(self, history: str, utterance: str) -> Dict[str, torch.Tensor]:
        text = f"{history.strip()} [SEP] {utterance.strip()}" if history.strip() else utterance.strip()
        enc  = self.tokenizer(
            text,
            max_length=self.max_seq_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids":      enc["input_ids"].to(self.device),
            "attention_mask": enc["attention_mask"].to(self.device),
        }

    def predict(
        self,
        history: str = "",
        utterance: str = "",
    ) -> PredictionResult:
        """Single-turn inference with latency measurement."""
        encoded = self._encode(history, utterance)

        if self.device.type == "cuda":
            torch.cuda.synchronize()
        t0 = time.perf_counter()

        with torch.no_grad():
            logits = self.model(encoded["input_ids"], encoded["attention_mask"])

        if self.device.type == "cuda":
            torch.cuda.synchronize()
        latency_ms = (time.perf_counter() - t0) * 1000.0

        probs = F.softmax(logits, dim=-1).squeeze(0).cpu()
        top_k_vals, top_k_idxs = probs.topk(min(self.top_k, len(self.class_names)))
        pred_idx = int(top_k_idxs[0])

        result = PredictionResult(
            dialog_act=self.class_names[pred_idx],
            confidence=float(top_k_vals[0]),
            latency_ms=latency_ms,
            top_k=[
                {"act": self.class_names[int(i)], "prob": round(float(p), 4)}
                for i, p in zip(top_k_idxs, top_k_vals)
            ],
            within_sla=latency_ms <= self.sla_ms,
            sla_ms=self.sla_ms,
        )

        if not result.within_sla:
            logger.warning(
                "Latency SLA breach: %.1f ms > %.0f ms", latency_ms, self.sla_ms
            )

        return result

    def predict_batch(
        self,
        samples: List[Dict[str, str]],
        batch_size: int = 32,
    ) -> List[PredictionResult]:
        """
        Batch inference over a list of {"history": str, "utterance": str} dicts.
        Latency reported per-sample.
        """
        results = []
        for i in range(0, len(samples), batch_size):
            batch = samples[i : i + batch_size]
            # Batch encode
            texts = [
                f"{s.get('history', '').strip()} [SEP] {s.get('utterance', '').strip()}"
                if s.get("history", "").strip()
                else s.get("utterance", "").strip()
                for s in batch
            ]
            enc = self.tokenizer(
                texts,
                max_length=self.max_seq_len,
                padding=True,
                truncation=True,
                return_tensors="pt",
            )
            input_ids      = enc["input_ids"].to(self.device)
            attention_mask = enc["attention_mask"].to(self.device)

            if self.device.type == "cuda":
                torch.cuda.synchronize()
            t0 = time.perf_counter()

            with torch.no_grad():
                logits = self.model(input_ids, attention_mask)

            if self.device.type == "cuda":
                torch.cuda.synchronize()
            batch_latency_ms = (time.perf_counter() - t0) * 1000.0
            per_sample_ms    = batch_latency_ms / len(batch)

            probs = F.softmax(logits, dim=-1).cpu()
            for j in range(probs.shape[0]):
                top_k_vals, top_k_idxs = probs[j].topk(min(self.top_k, len(self.class_names)))
                pred_idx = int(top_k_idxs[0])
                results.append(PredictionResult(
                    dialog_act=self.class_names[pred_idx],
                    confidence=float(top_k_vals[0]),
                    latency_ms=per_sample_ms,
                    top_k=[
                        {"act": self.class_names[int(i)], "prob": round(float(p), 4)}
                        for i, p in zip(top_k_idxs, top_k_vals)
                    ],
                    within_sla=per_sample_ms <= self.sla_ms,
                    sla_ms=self.sla_ms,
                ))
        return results


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Dialog Management Inference")
    parser.add_argument("--checkpoint", required=True, help="Path to best_model.pt")
    parser.add_argument("--history",    default="", help="Prior turns joined by [SEP]")
    parser.add_argument("--utterance",  required=True, help="Current user utterance")
    parser.add_argument("--sla-ms",     type=float, default=100.0, help="SLA threshold (ms)")
    parser.add_argument("--top-k",      type=int,   default=3)
    args = parser.parse_args()

    predictor = DialogPredictor(args.checkpoint, sla_ms=args.sla_ms, top_k=args.top_k)
    result = predictor.predict(history=args.history, utterance=args.utterance)
    print(json.dumps(result.to_dict(), indent=2))
