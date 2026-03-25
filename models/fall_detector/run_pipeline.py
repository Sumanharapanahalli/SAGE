"""
Fall Detection — End-to-End Pipeline Orchestrator
==================================================
Runs the complete ML pipeline in order:
  1. Data assembly  (data_pipeline.build_dataset)
  2. Model training (train.train)
  3. INT8 quantization and TFLite export (quantize_export)
  4. Validation against IEC 62304 acceptance criteria (validate)
  5. C header generation for firmware (generate_c_header)

All intermediate artefacts are written to --output-dir (default: models/).
The pipeline halts with a non-zero exit code if any acceptance criterion fails.

Usage:
    python run_pipeline.py [--mobiact PATH] [--sisfall PATH] [--output-dir models/]

IEC 62304 Pipeline Document: FD-PIPE-001 Rev 1.0
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger("fall_detector.pipeline")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run full fall detection ML pipeline")
    p.add_argument("--mobiact",    type=Path, default=None)
    p.add_argument("--sisfall",    type=Path, default=None)
    p.add_argument("--output-dir", type=Path, default=Path("models"))
    p.add_argument("--firmware-dir", type=Path,
                   default=Path("firmware/fall_detection"))
    p.add_argument("--epochs",     type=int, default=100)
    p.add_argument("--batch-size", type=int, default=128)
    p.add_argument("--seed",       type=int, default=42)
    p.add_argument("--reviewer",   type=str,
                   default="[Pending — IEC 62304 Verification Engineer]")
    return p.parse_args()


def _separator(title: str) -> None:
    logger.info("=" * 60)
    logger.info("  %s", title)
    logger.info("=" * 60)


def run_pipeline(args: argparse.Namespace) -> int:
    """Returns 0 on full success, 1 on any failure."""
    pipeline_start = time.time()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Build dataset ─────────────────────────────────────────────
    _separator("STEP 1/5: Dataset assembly")
    from data_pipeline import build_dataset, train_val_test_split
    X, y, stats = build_dataset(
        mobiact_root=args.mobiact,
        sisfall_root=args.sisfall,
        rng_seed=args.seed,
    )
    X_train, y_train, X_val, y_val, X_test, y_test = train_val_test_split(
        X, y, seed=args.seed)

    # Save test split for validation step
    test_npz = args.output_dir / "test_data.npz"
    np.savez_compressed(test_npz, X_test=X_test, y_test=y_test)
    logger.info("Test data saved → %s", test_npz)

    # ── Step 2: Train model ───────────────────────────────────────────────
    _separator("STEP 2/5: Model training")
    import train as train_module
    train_args = argparse.Namespace(
        mobiact=args.mobiact,
        sisfall=args.sisfall,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        seed=args.seed,
    )
    train_result = train_module.train(train_args)
    training_json = args.output_dir / "training_result.json"
    logger.info("Training complete. Best ckpt: %s", train_result["checkpoint_path"])

    # ── Step 3: Quantize & export ─────────────────────────────────────────
    _separator("STEP 3/5: INT8 quantization + TFLite export")
    import quantize_export as quant_module

    model_path = Path(train_result["checkpoint_path"])
    calib_data = quant_module.get_calibration_data(1000, None, args.seed)

    int8_path  = quant_module.quantize_to_int8(model_path, calib_data, args.output_dir)
    fp32_path  = quant_module.export_fp32(model_path, args.output_dir)
    latency    = quant_module.estimate_latency_cycles(int8_path)

    quant_result = {
        "int8_path":        str(int8_path),
        "fp32_path":        str(fp32_path),
        "int8_size_kb":     round(int8_path.stat().st_size / 1024, 1),
        "fp32_size_kb":     round(fp32_path.stat().st_size / 1024, 1),
        "latency_estimate": latency,
    }
    quant_json = args.output_dir / "quantization_result.json"
    quant_json.write_text(json.dumps(quant_result, indent=2))
    logger.info("INT8 model: %.1f KB  |  latency est. %.2f ms",
                quant_result["int8_size_kb"],
                latency["latency_ms_at_80mhz"])

    # ── Step 4: Validate ──────────────────────────────────────────────────
    _separator("STEP 4/5: IEC 62304 validation")
    import validate as validate_module

    validate_args = argparse.Namespace(
        test_data=test_npz,
        tflite=int8_path,
        tflite_fp32=fp32_path,
        training_result=training_json,
        quant_result=quant_json,
        output=args.output_dir / "validation_report.json",
        reviewer=args.reviewer,
    )
    report = validate_module.validate(validate_args)

    if report["summary"]["failed"] > 0:
        logger.error("PIPELINE FAILED: %d acceptance criteria not met",
                     report["summary"]["failed"])
        return 1

    # ── Step 5: Generate C header ─────────────────────────────────────────
    _separator("STEP 5/5: C firmware header generation")
    import generate_c_header as hdr_module

    # Use the threshold found during validation
    threshold = report["model_info"].get("classification_threshold", 0.50)
    header_path = args.firmware_dir / "fall_detector_model.h"
    hdr_module.generate_header(int8_path, header_path, threshold)
    logger.info("C header generated → %s", header_path)

    # ── Summary ───────────────────────────────────────────────────────────
    elapsed = time.time() - pipeline_start
    _separator("PIPELINE COMPLETE")
    logger.info("Total time: %.1f s", elapsed)
    logger.info("")
    logger.info("Deliverables:")
    logger.info("  %-45s  INT8 TFLite model", str(int8_path))
    logger.info("  %-45s  Validation report (JSON)", str(validate_args.output))
    logger.info("  %-45s  Validation report (Markdown)", str(validate_args.output.with_suffix(".md")))
    logger.info("  %-45s  C firmware header", str(header_path))
    logger.info("")
    m = report["performance_metrics"]
    logger.info("Key metrics:")
    logger.info("  Sensitivity: %.4f  (target ≥0.95)  [%s]",
                m["sensitivity"], "PASS" if m["sensitivity"] >= 0.95 else "FAIL")
    logger.info("  Specificity: %.4f  (target ≥0.90)  [%s]",
                m["specificity"], "PASS" if m["specificity"] >= 0.90 else "FAIL")
    logger.info("  FP/day est.: %.2f   (target ≤2.0)   [%s]",
                m["fp_per_day"], "PASS" if m["fp_per_day"] <= 2.0 else "WARN")
    logger.info("  Model size:  %.1f KB (target ≤100 KB) [%s]",
                quant_result["int8_size_kb"],
                "PASS" if quant_result["int8_size_kb"] <= 100 else "FAIL")
    logger.info("  Latency est: %.2f ms (target ≤20 ms)  [%s]",
                latency["latency_ms_at_80mhz"],
                "PASS" if latency["latency_ms_at_80mhz"] <= 20 else "FAIL")

    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    args = parse_args()
    rc = run_pipeline(args)
    sys.exit(rc)
