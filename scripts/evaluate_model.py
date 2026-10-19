"""Evaluate a checkpoint against a fixed snapshot, recording provenance and mistakes."""

import argparse
import json
from pathlib import Path
import time

import torch
from torch.utils.data import DataLoader

from backend.config import get_model_path
from backend.helpers.dataset import default_data_dir, file_sha256, load_snapshot
from backend.helpers.evaluation import calculate_metrics, markdown_report
from backend.transfer.main import SmiskiClassifier, SmiskiDataset, val_transforms


def evaluation_status(checkpoint_hash, snapshot, metadata, split):
    if metadata is None:
        return "diagnostic_only_training_provenance_unknown"
    if metadata.get("checkpoint_sha256") != checkpoint_hash or metadata.get("dataset_fingerprint") != snapshot["fingerprint"]:
        raise ValueError("Training metadata does not match the checkpoint and dataset fingerprint")
    for partition, field in (("train", "training_image_sha256"), ("validation", "validation_image_sha256")):
        expected = sorted(row["sha256"] for row in snapshot["records"] if row["split"] == partition)
        if metadata.get(field) != expected:
            raise ValueError("Training metadata does not match the declared train/validation partitions")
    return "held_out_for_this_training_run" if split == "test" else "training_or_model_selection_partition"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=get_model_path())
    parser.add_argument("--snapshot", type=Path, default=Path("docs/dataset/split-v1.json"))
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--split", choices=["train", "validation", "test"], default="test")
    parser.add_argument("--output", type=Path, default=Path("docs/evaluation/legacy-diagnostic.json"))
    parser.add_argument("--title", default="Initial checkpoint diagnostic")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if args.batch_size < 1 or args.threads < 1:
        parser.error("batch size and threads must be positive")
    if args.output.exists() or args.output.with_suffix(".md").exists():
        parser.error("Report exists; use a new --output to preserve earlier results")
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)
    snapshot = load_snapshot(args.snapshot, args.data_dir)
    records = [row for row in snapshot["records"] if row["split"] == args.split]
    checkpoint_hash = file_sha256(args.checkpoint)
    metadata_path = args.checkpoint.with_suffix(".metadata.json")
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else None
    status = evaluation_status(checkpoint_hash, snapshot, metadata, args.split)
    classifier = SmiskiClassifier(device=torch.device("cpu"))
    classifier.load(args.checkpoint)
    dataset = SmiskiDataset([args.data_dir / row["path"] for row in records], [row["label"] for row in records], val_transforms)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False)
    rows, started = [], time.perf_counter()
    with torch.inference_mode():
        for images, labels in loader:
            scores = classifier.model(images).softmax(1)
            for score, label in zip(scores, labels):
                record = records[len(rows)]
                prediction = int(score.argmax())
                rows.append({
                    "path": record["path"], "sha256": record["sha256"], "group": record["group"],
                    "source_page": record.get("source_page"), "label": int(label),
                    "prediction": prediction, "smiski_score": float(score[1]), "score": float(score[prediction]),
                })
    metrics = calculate_metrics([row["label"] for row in rows], [row["prediction"] for row in rows], [row["smiski_score"] for row in rows])
    limitations = [
        "Labels come from collection folders, not a complete manual review; some negatives visibly contain Smiskis.",
        "Duplicate grouping covers exact pixels, source-photo IDs, and nearby dHashes; crops, viewpoints and shooting sessions can still leak.",
        "Metrics are per image, not per independent scene; a small, source-biased dataset cannot establish real-world accuracy.",
        "Softmax scores are uncalibrated. No uncertainty threshold has been selected.",
    ]
    if metadata is None:
        limitations.insert(0, "The initial checkpoint predates this split and may have seen these photos. These numbers are NOT held-out generalization results.")
    report = {
        "schema_version": 1, "title": args.title, "evaluation_status": status,
        "checkpoint_sha256": checkpoint_hash, "dataset_fingerprint": snapshot["fingerprint"],
        "split": args.split, "groups": len({row["group"] for row in rows}),
        "decision_rule": "argmax of two logits; no tuned threshold",
        "preprocessing": "EXIF transpose, RGB, resize 224x224, ImageNet mean/std; no random augmentation",
        "runtime": {"device": "cpu", "threads": args.threads, "torch_version": torch.__version__, "inference_and_decode_seconds": time.perf_counter() - started},
        "metrics": metrics, "limitations": limitations, "predictions": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    args.output.with_suffix(".md").write_text(markdown_report(report))
    print(f"{status}: accuracy {metrics['accuracy']:.3%}, macro F1 {metrics['macro_f1']:.4f}; {args.output}")


if __name__ == "__main__":
    main()
