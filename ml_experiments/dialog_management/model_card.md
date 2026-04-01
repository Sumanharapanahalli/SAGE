# Model Card — Dialog Management (dialog_management_v1)

## Model Summary

| Field | Value |
|---|---|
| **Task** | Dialog act classification for conversational flow management |
| **Architecture** | DistilBERT encoder → LSTM state tracker → MLP policy head |
| **Base model** | `distilbert-base-uncased` (66M parameters) |
| **Domain** | Multi-domain task-oriented dialog (MultiWOZ-style) |
| **Input** | Conversation history + current utterance (packed into one sequence) |
| **Output** | Dialog act label + confidence score + top-k alternatives |
| **Framework** | PyTorch 2.1 + HuggingFace Transformers 4.36 |
| **License** | Apache 2.0 |

---

## Intended Use

**Primary use:** Predicting the next system dialog act in task-oriented conversations across multiple domains (restaurant, hotel, taxi, train, attraction, hospital, police).

**Suitable for:**
- Dialog management backends in task-oriented dialog systems
- Training data labelling pipelines
- Human-agent collaboration systems where act classification informs routing

**Not suitable for:**
- Open-domain / chit-chat dialog (trained on task-oriented domains only)
- Languages other than English (base model is English-only)
- Safety-critical decisions without human review

---

## Training Details

### Data

| Split | Size | Split Strategy |
|---|---|---|
| Train | ~1,420 samples | Stratified by dialog act |
| Validation | ~300 samples | Stratified by dialog act |
| Test | ~300 samples | Stratified by dialog act |

- **Dataset:** MultiWOZ-style synthetic data (replace with real MultiWOZ 2.4 in production)
- **Dialog acts:** 15 classes — inform, request, confirm, deny, greet, bye, book, recommend, nooffer, offerbook, offerbooked, reqmore, welcome, select, nobook
- **Class imbalance:** Present (ratio ~10:1 for inform vs nobook); addressed via class-weighted loss

### Hyperparameters

| Parameter | Value |
|---|---|
| Learning rate | 2e-5 (OneCycleLR with 10% warmup) |
| Batch size | 32 |
| Epochs | 20 (early stopping, patience=5) |
| Optimizer | AdamW (weight_decay=0.01) |
| Dropout | 0.3 |
| Grad clip | 1.0 |
| Seed | 42 |

### No-Leakage Guarantee

- Tokenizer loaded from pretrained checkpoint — no vocabulary fitting on corpus
- Label encoder fitted on full label set (not test statistics)
- Splits are stratified and isolated: test set never influences training
- Class weights computed from **training set only**

---

## Evaluation Metrics

### Test Set Performance

| Metric | Value |
|---|---|
| Accuracy | ~0.84 |
| F1 (weighted) | ~0.82 |
| F1 (macro) | ~0.76 |
| Inference latency P95 | < 100 ms (CPU) |

*Exact values depend on hardware and random seed; see `artifacts/reports/evaluation_report.json` for the current run.*

### Per-Class Performance

See `artifacts/reports/evaluation_report.json` → `per_class_metrics` for per-class precision, recall, F1, and support.

### Confusion Matrix

See `artifacts/reports/confusion_matrix.png`.

---

## Bias Evaluation

Bias is evaluated using **demographic parity** — per-group accuracy gap across user groups (A, B, C in synthetic data; replace with real demographic attributes in production).

| Metric | Threshold | Status |
|---|---|---|
| Demographic parity gap | ≤ 5 percentage points | See evaluation report |

- A gap > 5 pp triggers a `bias_flag: true` in the evaluation report
- **Recommendation:** If bias is detected, consider oversampling the under-performing group, adjusting class weights, or conducting a deeper intersectional analysis

---

## Inference Latency SLA

| Percentile | Target | Measured |
|---|---|---|
| P50 | — | See report |
| P95 | ≤ 100 ms | See report |
| P99 | — | See report |

Measured on single-sample CPU inference with a 10-iteration warm-up. GPU inference is typically 5–15× faster.

---

## Limitations

1. **Training data:** Synthetic data generator approximates MultiWOZ distributions but is not a substitute for real annotated dialog data. Retrain on real MultiWOZ 2.4 for production deployment.
2. **English only:** DistilBERT base is English-only; multilingual support requires `distilbert-base-multilingual-cased`.
3. **Static state:** The LSTM receives a single encoded turn per call. For full dialog state tracking over many turns, replace with a stateful inference loop that passes LSTM hidden states between calls.
4. **15 dialog acts:** Covers standard task-oriented acts. Extend `DIALOG_ACTS` in `dataset.py` and retrain for domain-specific act sets.
5. **Bias evaluation scope:** Demographic group attributes in this release are synthetic; production evaluation should use real user metadata.

---

## Ethical Considerations

- The model classifies dialog acts; it does not generate responses — ethical risks are bounded to misclassification rather than harmful generation.
- Bias evaluation is included by design. Any deployment should repeat bias analysis with real production traffic and real demographic groups.
- Human review is recommended for high-stakes routing decisions (medical, legal, financial domains).

---

## Reproducibility

Full reproduction:
```bash
pip install -r requirements.txt
python train.py --config config/dialog_management.yaml
# MLflow run ID logged to stdout; artifacts in ./artifacts/
```

All experiments are tracked in MLflow (`./mlruns`). Seed 42 is pinned across Python, NumPy, PyTorch, and CUDA.

---

## Version History

| Version | Date | Notes |
|---|---|---|
| v1.0.0 | 2026-03-28 | Initial release — DistilBERT+LSTM, 15 dialog acts, bias eval |

---

*Generated by SAGE ML Pipeline — dialog_management_v1*
