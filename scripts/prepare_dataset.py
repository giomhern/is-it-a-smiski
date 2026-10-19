"""Create a versioned dataset inventory, audit, and duplicate-aware splits."""

import argparse
import json
from collections import Counter
from pathlib import Path

from backend.helpers.dataset import build_snapshot, default_data_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument(
        "--output", type=Path, default=Path("docs/dataset/split-v1.json")
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--distance", type=int, default=6)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(
            "Output exists. Use a new versioned output path to preserve the original split."
        )
    if not 0 <= args.distance <= 16:
        parser.error("--distance must be between 0 and 16")
    snapshot = build_snapshot(args.data_dir, args.seed, args.distance)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2) + "\n")
    print(f"Dataset fingerprint: {snapshot['fingerprint']}")
    for split in ("train", "validation", "test"):
        rows = [record for record in snapshot["records"] if record["split"] == split]
        print(
            f"{split}: {len(rows)} photos, {len({row['group'] for row in rows})} groups, labels {dict(Counter(row['label'] for row in rows))}"
        )
    print(f"Excluded: {dict(Counter(row['reason'] for row in snapshot['excluded']))}")
    print(f"Manifest warnings: {len(snapshot['warnings'])}")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
