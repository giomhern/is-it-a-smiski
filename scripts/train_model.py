"""Train a reproducible frozen-ImageNet ResNet50 baseline without reading test images."""

import argparse
import json
import random
import time
from collections import Counter
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from backend.helpers.dataset import default_data_dir, file_sha256, load_snapshot
from backend.transfer.main import SmiskiClassifier, SmiskiDataset


def training_partitions(snapshot):
    """Only training and validation photos are eligible for fitting/selection."""
    train = [row for row in snapshot["records"] if row["split"] == "train"]
    validation = [row for row in snapshot["records"] if row["split"] == "validation"]
    return train, validation


def extract_features(model, records, data_dir, batch_size):
    dataset = SmiskiDataset(
        [data_dir / row["path"] for row in records], [row["label"] for row in records]
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
    features, labels = [], []
    model.eval()
    with torch.inference_mode():
        for images, targets in loader:
            features.append(model(images).cpu())
            labels.append(targets)
    # Clone outside inference_mode: the head's backward pass needs ordinary tensors.
    return torch.cat(features).clone(), torch.cat(labels).clone()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot", type=Path, default=Path("docs/dataset/split-v1.json")
    )
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument(
        "--output", type=Path, default=Path("backend/models/smiski_baseline_v1.pt")
    )
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    metadata_path = args.output.with_suffix(".metadata.json")
    if args.output.exists() or metadata_path.exists():
        parser.error(
            "Output checkpoint or metadata already exists; choose a new --output"
        )
    if min(args.epochs, args.batch_size, args.threads) < 1 or args.lr <= 0:
        parser.error("epochs, batch size, threads and learning rate must be positive")
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)
    snapshot = load_snapshot(args.snapshot, args.data_dir)
    train, validation = training_partitions(snapshot)
    classifier = SmiskiClassifier(device=torch.device("cpu"))
    classifier.build_model()
    model = classifier.model
    model.requires_grad_(False)
    head = nn.Linear(model.fc.in_features, 2)
    model.fc = nn.Identity()
    started = time.perf_counter()
    print(
        f"Extracting ImageNet features: {len(train)} train, {len(validation)} validation; test partition untouched",
        flush=True,
    )
    train_features, train_labels = extract_features(
        model, train, args.data_dir, args.batch_size
    )
    print("Training features ready", flush=True)
    val_features, val_labels = extract_features(
        model, validation, args.data_dir, args.batch_size
    )
    model.fc = head
    counts = torch.bincount(train_labels, minlength=2)
    weights = len(train_labels) / (2 * counts.float())
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.Adam(head.parameters(), lr=args.lr)
    generator = torch.Generator().manual_seed(args.seed)
    loader = DataLoader(
        TensorDataset(train_features, train_labels),
        batch_size=32,
        shuffle=True,
        generator=generator,
    )
    best_loss, best_state, best_epoch = float("inf"), None, None
    history = []
    for epoch in range(1, args.epochs + 1):
        head.train()
        for features, labels in loader:
            optimizer.zero_grad()
            criterion(head(features), labels).backward()
            optimizer.step()
        head.eval()
        with torch.no_grad():
            outputs = head(val_features)
            val_loss = nn.functional.cross_entropy(outputs, val_labels).item()
            val_accuracy = (outputs.argmax(1) == val_labels).float().mean().item()
        history.append(
            {
                "epoch": epoch,
                "validation_loss": val_loss,
                "validation_accuracy": val_accuracy,
            }
        )
        if val_loss < best_loss:
            best_loss, best_epoch = val_loss, epoch
            best_state = {
                key: value.detach().clone() for key, value in head.state_dict().items()
            }
        if epoch == 1 or epoch % 10 == 0:
            print(
                f"Epoch {epoch}: validation loss={val_loss:.4f}, accuracy={val_accuracy:.3%}",
                flush=True,
            )
    head.load_state_dict(best_state)
    classifier.save(args.output)
    metadata = {
        "schema_version": 1,
        "checkpoint_sha256": file_sha256(args.output),
        "dataset_fingerprint": snapshot["fingerprint"],
        "initialization": "torchvision.ResNet50_Weights.IMAGENET1K_V2",
        "method": "frozen ImageNet backbone; class-balanced linear head; deterministic features, no augmentation",
        "selection": "lowest unweighted validation cross-entropy; fixed argmax decision rule",
        "seed": args.seed,
        "epochs": args.epochs,
        "selected_epoch": best_epoch,
        "feature_batch_size": args.batch_size,
        "head_batch_size": 32,
        "optimizer": "Adam",
        "lr": args.lr,
        "threads": args.threads,
        "device": "cpu",
        "torch_version": torch.__version__,
        "training_seconds": time.perf_counter() - started,
        "training_counts": dict(Counter(row["label"] for row in train)),
        "training_image_sha256": sorted(row["sha256"] for row in train),
        "validation_image_sha256": sorted(row["sha256"] for row in validation),
        "history": history,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    print(
        f"Saved {args.output}; selected epoch {best_epoch}; checkpoint SHA-256 {metadata['checkpoint_sha256']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
