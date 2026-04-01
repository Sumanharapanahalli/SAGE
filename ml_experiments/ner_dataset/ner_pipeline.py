"""
NER Dataset Preparation Pipeline
=================================
Ingests raw text + span annotations (JSONL), validates on ingestion,
tokenizes with spaCy, converts to BIO tags, builds stratified train/val/test
splits, exports to CoNLL-2003 format, and logs every run to experiments/.

Idempotency guarantee
---------------------
Each document is keyed by SHA-256(text). Re-running the pipeline on the same
input writes identical output; duplicate documents are detected and skipped.

Usage
-----
    python ner_pipeline.py --input data/raw --output data/processed
    python ner_pipeline.py --input data/raw --output data/processed --dry-run

Input JSONL schema (one document per line):
    {
        "doc_id": "doc_001",
        "text": "Apple was founded by Steve Jobs in Cupertino.",
        "entities": [
            {"start": 0,  "end": 5,  "label": "ORG"},
            {"start": 21, "end": 31, "label": "PER"},
            {"start": 35, "end": 44, "label": "LOC"}
        ],
        "source": "news_corpus",
        "language": "en"
    }

Output
------
    data/processed/train.conll
    data/processed/val.conll
    data/processed/test.conll
    data/processed/pipeline_manifest.json   ← split checksums, run metadata
    experiments/ner_prep_runs.jsonl         ← experiment log
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import spacy

# Add project src/ to path for shared ExperimentLogger
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from experiment_logger import ExperimentLogger  # noqa: E402 (path insert above)

from validators import (  # noqa: E402
    ALLOWED_ENTITY_TYPES,
    LabeledSentence,
    LabeledToken,
    RawDocument,
    validate_batch,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("ner_pipeline")

# ── Constants ────────────────────────────────────────────────────────────────

TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15  # 1 - TRAIN - VAL

assert abs(TRAIN_RATIO + VAL_RATIO + TEST_RATIO - 1.0) < 1e-9

RANDOM_SEED = 42

# Entity-density buckets used for stratification
# (ensures each split sees all density levels)
_DENSITY_BUCKETS = ["empty", "low", "medium", "high"]


# ── Data structures ───────────────────────────────────────────────────────────


@dataclass
class PipelineStats:
    """Accumulated statistics for one pipeline run."""

    raw_docs_ingested: int = 0
    docs_rejected: int = 0
    docs_deduplicated: int = 0
    sentences_total: int = 0
    tokens_total: int = 0
    entity_counts: dict[str, int] = field(default_factory=dict)
    split_sizes: dict[str, int] = field(default_factory=dict)

    def entity_f1_placeholder(self) -> float:
        """Returns -1.0 until gold/pred evaluation is run (prep pipeline)."""
        return -1.0

    def to_dict(self) -> dict:
        return {
            "raw_docs_ingested": self.raw_docs_ingested,
            "docs_rejected": self.docs_rejected,
            "docs_deduplicated": self.docs_deduplicated,
            "sentences_total": self.sentences_total,
            "tokens_total": self.tokens_total,
            "entity_counts": self.entity_counts,
            "split_sizes": self.split_sizes,
            "entity_f1": self.entity_f1_placeholder(),
        }


# ── Core helpers ──────────────────────────────────────────────────────────────


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _density_bucket(n_entities: int) -> str:
    """Map entity count → stratification bucket label."""
    if n_entities == 0:
        return "empty"
    if n_entities <= 2:
        return "low"
    if n_entities <= 5:
        return "medium"
    return "high"


def _spans_to_bio(
    doc: spacy.tokens.Doc,
    entities: list[dict],
    doc_id: str,
) -> list[LabeledToken]:
    """
    Convert character-level entity spans to BIO token tags.

    Strategy: token-level O assignment, then B/I overlay for each span.
    Tokens that straddle a span boundary are tagged O (ambiguous boundary).

    Parameters
    ----------
    doc      : spaCy Doc (already tokenized)
    entities : list of {"start": int, "end": int, "label": str}
    doc_id   : used only for warning messages

    Returns
    -------
    list[LabeledToken]
    """
    tags = ["O"] * len(doc)

    for ent in sorted(entities, key=lambda e: e["start"]):
        start, end, label = ent["start"], ent["end"], ent["label"].upper()
        in_span = False
        for i, token in enumerate(doc):
            # Token fully inside span
            if token.idx >= start and token.idx + len(token.text) <= end:
                tags[i] = f"B-{label}" if not in_span else f"I-{label}"
                in_span = True
            # Token straddles span boundary — skip (boundary ambiguity)
            elif token.idx < start < token.idx + len(token.text):
                logger.debug(
                    "doc %s: token %r straddles span start %d — tagged O",
                    doc_id,
                    token.text,
                    start,
                )
            elif token.idx < end < token.idx + len(token.text):
                logger.debug(
                    "doc %s: token %r straddles span end %d — tagged O",
                    doc_id,
                    token.text,
                    end,
                )
            else:
                if token.idx >= end:
                    in_span = False

    return [
        LabeledToken(text=tok.text, bio_tag=tag)
        for tok, tag in zip(doc, tags)
    ]


def _sentence_windows(
    doc: spacy.tokens.Doc,
    tokens: list[LabeledToken],
) -> Iterator[tuple[spacy.tokens.Span, list[LabeledToken]]]:
    """Yield (sentence_span, sentence_token_labels) pairs."""
    offset = 0
    for sent in doc.sents:
        n = len(list(sent))
        sent_tokens = tokens[offset : offset + n]
        yield sent, sent_tokens
        offset += n


def _compute_metrics_from_seqeval(
    all_true: list[list[str]],
    all_pred: list[list[str]],
) -> dict[str, float]:
    """
    Compute entity-level F1/precision/recall via seqeval.
    Returns empty dict if seqeval is not installed.
    """
    try:
        from seqeval.metrics import classification_report, f1_score, precision_score, recall_score

        return {
            "entity_precision": precision_score(all_true, all_pred),
            "entity_recall": recall_score(all_true, all_pred),
            "entity_f1": f1_score(all_true, all_pred),
            "classification_report": classification_report(all_true, all_pred),
        }
    except ImportError:
        logger.warning("seqeval not installed — skipping entity-level metrics.")
        return {}


# ── Pipeline class ─────────────────────────────────────────────────────────────


class NERDatasetPipeline:
    """
    End-to-end, idempotent NER dataset preparation pipeline.

    Parameters
    ----------
    input_dir  : directory containing *.jsonl raw annotation files
    output_dir : where CoNLL splits and manifest are written
    nlp_model  : spaCy model name (must be installed)
    strict     : if True, a single invalid doc aborts the run
    """

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        *,
        nlp_model: str = "en_core_web_sm",
        strict: bool = False,
    ) -> None:
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.strict = strict
        self.stats = PipelineStats()
        self._seen_hashes: set[str] = set()

        logger.info("Loading spaCy model: %s", nlp_model)
        self.nlp = spacy.load(nlp_model, disable=["ner"])  # disable built-in NER
        self.nlp.add_pipe("sentencizer")

        self._exp = ExperimentLogger(
            "ner_prep",
            log_dir=Path(__file__).parent / "experiments",
        )

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def _load_jsonl_files(self) -> list[dict]:
        raw: list[dict] = []
        files = sorted(self.input_dir.glob("*.jsonl"))
        if not files:
            raise FileNotFoundError(
                f"No *.jsonl files found in {self.input_dir}"
            )
        for f in files:
            logger.info("Reading %s", f)
            with open(f, encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        logger.warning("%s line %d: JSON parse error — %s", f.name, lineno, exc)
        return raw

    def _deduplicate(self, docs: list[RawDocument]) -> list[RawDocument]:
        """Drop documents whose text SHA-256 was already processed."""
        unique: list[RawDocument] = []
        for doc in docs:
            h = _sha256(doc.text)
            if h in self._seen_hashes:
                logger.debug("Skipping duplicate doc %r (hash=%s)", doc.doc_id, h[:12])
                self.stats.docs_deduplicated += 1
            else:
                self._seen_hashes.add(h)
                unique.append(doc)
        return unique

    # ── Labeling ──────────────────────────────────────────────────────────────

    def _label_document(
        self, raw_doc: RawDocument
    ) -> list[LabeledSentence]:
        """Tokenize text and convert spans to BIO-tagged sentences."""
        spacy_doc = self.nlp(raw_doc.text)
        entities_dicts = [e.model_dump() for e in raw_doc.entities]
        all_tokens = _spans_to_bio(spacy_doc, entities_dicts, raw_doc.doc_id)

        sentences: list[LabeledSentence] = []
        for s_idx, (sent, sent_tokens) in enumerate(
            _sentence_windows(spacy_doc, all_tokens)
        ):
            if not sent_tokens:
                continue
            sent_id = f"{raw_doc.doc_id}_s{s_idx:04d}"
            labeled = LabeledSentence(
                sentence_id=sent_id,
                doc_id=raw_doc.doc_id,
                tokens=sent_tokens,
            )
            sentences.append(labeled)
        return sentences

    # ── Splitting ─────────────────────────────────────────────────────────────

    def _stratified_split(
        self, sentences: list[LabeledSentence]
    ) -> dict[str, list[LabeledSentence]]:
        """
        Stratify by entity-density bucket so each split has representative
        entity coverage. Uses a deterministic shuffle via RANDOM_SEED.

        No sklearn dependency — implemented with bucket-level sequential
        allocation to avoid introducing a classification-only dependency.
        """
        import random as _random

        rng = _random.Random(RANDOM_SEED)

        # Group by density bucket
        buckets: dict[str, list[LabeledSentence]] = {b: [] for b in _DENSITY_BUCKETS}
        for sent in sentences:
            n = sum(1 for t in sent.tokens if t.bio_tag.startswith("B-"))
            buckets[_density_bucket(n)].append(sent)

        train_all, val_all, test_all = [], [], []

        for bucket_name, bucket_sents in buckets.items():
            rng.shuffle(bucket_sents)
            n = len(bucket_sents)
            n_train = int(n * TRAIN_RATIO)
            n_val = int(n * VAL_RATIO)

            train_all.extend(bucket_sents[:n_train])
            val_all.extend(bucket_sents[n_train : n_train + n_val])
            test_all.extend(bucket_sents[n_train + n_val :])

            logger.info(
                "  bucket=%-8s  total=%4d  train=%4d  val=%4d  test=%4d",
                bucket_name, n, len(bucket_sents[:n_train]),
                len(bucket_sents[n_train : n_train + n_val]),
                len(bucket_sents[n_train + n_val :]),
            )

        # Final shuffle within each split to mix buckets
        rng.shuffle(train_all)
        rng.shuffle(val_all)
        rng.shuffle(test_all)

        return {"train": train_all, "val": val_all, "test": test_all}

    # ── Export ────────────────────────────────────────────────────────────────

    @staticmethod
    def _sentences_to_conll(sentences: list[LabeledSentence]) -> str:
        """Serialize sentences to CoNLL-2003 format (token<TAB>tag per line)."""
        lines: list[str] = []
        for sent in sentences:
            for tok in sent.tokens:
                lines.append(f"{tok.text}\t{tok.bio_tag}")
            lines.append("")  # blank line = sentence boundary
        return "\n".join(lines)

    def _write_splits(
        self, splits: dict[str, list[LabeledSentence]]
    ) -> dict[str, str]:
        """Write CoNLL files; return dict of split_name → sha256 checksum."""
        checksums: dict[str, str] = {}
        for split_name, sents in splits.items():
            out_path = self.output_dir / f"{split_name}.conll"
            content = self._sentences_to_conll(sents)
            out_path.write_text(content, encoding="utf-8")
            checksums[split_name] = _sha256(content)
            self.stats.split_sizes[split_name] = len(sents)
            logger.info("Wrote %s  (%d sentences)", out_path, len(sents))
        return checksums

    def _write_manifest(
        self,
        checksums: dict[str, str],
        run_id: str,
        params: dict,
    ) -> None:
        """Write pipeline_manifest.json — split checksums + run metadata."""
        manifest = {
            "run_id": run_id,
            "params": params,
            "splits": {
                name: {
                    "path": f"{name}.conll",
                    "sentences": self.stats.split_sizes.get(name, 0),
                    "sha256": cs,
                }
                for name, cs in checksums.items()
            },
            "stats": self.stats.to_dict(),
        }
        manifest_path = self.output_dir / "pipeline_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        logger.info("Manifest written → %s", manifest_path)

    # ── Accumulate stats ──────────────────────────────────────────────────────

    def _accumulate_stats(self, sentences: list[LabeledSentence]) -> None:
        self.stats.sentences_total += len(sentences)
        for sent in sentences:
            self.stats.tokens_total += len(sent.tokens)
            for tok in sent.tokens:
                if tok.bio_tag.startswith("B-"):
                    etype = tok.bio_tag.split("-", 1)[1]
                    self.stats.entity_counts[etype] = (
                        self.stats.entity_counts.get(etype, 0) + 1
                    )

    # ── Check for class imbalance ─────────────────────────────────────────────

    def _check_class_imbalance(self, sentences: list[LabeledSentence]) -> bool:
        """
        Returns True if O-token ratio is so high (>95%) that training may
        be dominated by the O class.  Logs a warning but does not abort.
        """
        n_o = sum(
            1 for s in sentences for t in s.tokens if t.bio_tag == "O"
        )
        n_total = sum(len(s.tokens) for s in sentences)
        if n_total == 0:
            return False
        ratio = n_o / n_total
        if ratio > 0.95:
            logger.warning(
                "Class imbalance detected: %.1f%% of tokens are O. "
                "Consider weighted loss or data augmentation.",
                ratio * 100,
            )
            return True
        logger.info("O-token ratio: %.1f%% (within acceptable range)", ratio * 100)
        return False

    # ── Main entry ────────────────────────────────────────────────────────────

    def run(self, dry_run: bool = False) -> PipelineStats:
        """Execute the full pipeline. Returns accumulated stats."""
        params = {
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "train_ratio": TRAIN_RATIO,
            "val_ratio": VAL_RATIO,
            "test_ratio": TEST_RATIO,
            "random_seed": RANDOM_SEED,
            "strict": self.strict,
            "dry_run": dry_run,
        }
        run_id = self._exp.start_run(params=params)

        try:
            # 1. Ingest
            raw_dicts = self._load_jsonl_files()
            self.stats.raw_docs_ingested = len(raw_dicts)

            # 2. Validate on ingestion (fail-fast or collect errors)
            valid_docs, rejected = validate_batch(raw_dicts, strict=self.strict)
            self.stats.docs_rejected = len(rejected)
            if rejected:
                logger.warning("%d documents rejected at ingestion", len(rejected))

            # 3. Deduplicate (idempotency)
            unique_docs = self._deduplicate(valid_docs)
            logger.info(
                "Ingestion complete: %d valid, %d deduped → %d to label",
                len(valid_docs),
                self.stats.docs_deduplicated,
                len(unique_docs),
            )

            # 4. Label (tokenize + BIO tagging)
            all_sentences: list[LabeledSentence] = []
            for doc in unique_docs:
                sents = self._label_document(doc)
                all_sentences.extend(sents)

            self._accumulate_stats(all_sentences)
            logger.info(
                "Labeling complete: %d sentences, %d tokens, entities: %s",
                self.stats.sentences_total,
                self.stats.tokens_total,
                self.stats.entity_counts,
            )

            # 5. Class imbalance check
            class_imbalance = self._check_class_imbalance(all_sentences)

            # 6. Stratified split
            splits = self._stratified_split(all_sentences)

            if dry_run:
                logger.info("[DRY RUN] No files written.")
                self._exp.log_metrics(run_id, {"dry_run": 1.0, **self.stats.to_dict()})
                self._exp.end_run(run_id, status="dry_run")
                return self.stats

            # 7. Export CoNLL
            checksums = self._write_splits(splits)

            # 8. Write manifest
            self._write_manifest(checksums, run_id=run_id, params=params)

            # 9. Log experiment
            metrics: dict[str, float] = {
                "sentences_train": float(self.stats.split_sizes.get("train", 0)),
                "sentences_val": float(self.stats.split_sizes.get("val", 0)),
                "sentences_test": float(self.stats.split_sizes.get("test", 0)),
                "tokens_total": float(self.stats.tokens_total),
                "docs_rejected": float(self.stats.docs_rejected),
                "class_imbalance_flag": float(class_imbalance),
            }
            metrics.update(
                {f"entity_{k.lower()}_count": float(v) for k, v in self.stats.entity_counts.items()}
            )
            self._exp.log_metrics(run_id, metrics)
            self._exp.end_run(run_id, status="completed")

            logger.info("Pipeline complete. Run ID: %s", run_id)
            return self.stats

        except Exception as exc:
            self._exp.log_metrics(run_id, {"error": 1.0})
            self._exp.end_run(run_id, status="failed")
            logger.error("Pipeline failed: %s", exc)
            raise


# ── CLI ───────────────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="NER Dataset Preparation Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw"),
        help="Directory with *.jsonl annotation files",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed"),
        help="Directory where CoNLL splits are written",
    )
    p.add_argument(
        "--model",
        default="en_core_web_sm",
        help="spaCy model for tokenization",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Abort on first validation error (default: collect errors)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and split but do not write files",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    pipeline = NERDatasetPipeline(
        input_dir=args.input,
        output_dir=args.output,
        nlp_model=args.model,
        strict=args.strict,
    )
    stats = pipeline.run(dry_run=args.dry_run)

    # Print summary
    print("\n=== Pipeline Summary ===")
    print(json.dumps(stats.to_dict(), indent=2))


if __name__ == "__main__":
    main()
