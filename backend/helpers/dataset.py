"""Auditable, portable dataset snapshots with duplicate-aware train/val/test splits."""

import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from backend.config import ROOT_DIR

LABELS = {"non_smiski": 0, "smiski": 1}
SPLITS = {"train": 0.7, "validation": 0.15, "test": 0.15}
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_fingerprint(snapshot):
    payload = {key: value for key, value in snapshot.items() if key != "fingerprint"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def image_signatures(path):
    with Image.open(path) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGB")
        pixels = hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()
        # 128-bit dHash: low Hamming distance flags candidate near-duplicates.
        small = list(
            image.convert("L").resize((17, 8), Image.Resampling.LANCZOS).getdata()
        )
        dhash = 0
        for y in range(8):
            for x in range(16):
                dhash = (dhash << 1) | (small[y * 17 + x] > small[y * 17 + x + 1])
        return pixels, f"{dhash:032x}", image.width, image.height


def group_records(records, distance=6):
    """Union exact bytes/pixels, source photo IDs, and nearby dHashes transitively."""
    parents = list(range(len(records)))

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(a, b):
        parents[find(b)] = find(a)

    seen = {}
    hashes = [int(record["dhash"], 16) for record in records]
    for i, record in enumerate(records):
        for field in ("sha256", "pixel_sha256", "source_page"):
            value = record.get(field)
            if value:
                key = (field, value)
                if key in seen:
                    union(i, seen[key])
                seen[key] = i
        for j in range(i):
            if (hashes[i] ^ hashes[j]).bit_count() <= distance:
                union(i, j)
    components = defaultdict(list)
    for i, record in enumerate(records):
        components[find(i)].append(record)
    for members in components.values():
        group = min(record["sha256"] for record in members)
        for record in members:
            record["group"] = group
    return list(components.values())


def assign_splits(records, seed=42):
    """Allocate whole groups per class; large groups can make ratios approximate."""
    rng = random.Random(seed)
    for label in (0, 1):
        grouped = defaultdict(list)
        for record in records:
            if record["label"] == label:
                grouped[record["group"]].append(record)
        groups = [grouped[key] for key in sorted(grouped)]
        if len(groups) < 3:
            raise ValueError(
                f"Class {label} needs at least three independent groups for train/validation/test"
            )
        rng.shuffle(groups)
        groups.sort(key=lambda group: -len(group))
        total = sum(map(len, groups))
        counts = Counter()
        targets = {split: total * fraction for split, fraction in SPLITS.items()}
        for index, group in enumerate(groups):
            if index < 3:
                split = list(SPLITS)[index]
            else:
                split = min(
                    SPLITS,
                    key=lambda name: (
                        (
                            (counts[name] + len(group) - targets[name]) ** 2
                            - (counts[name] - targets[name]) ** 2
                        )
                        / targets[name]
                    ),
                )
            for record in group:
                record["split"] = split
            counts[split] += len(group)
    return records


def build_snapshot(data_dir, seed=42, distance=6):
    data_dir = Path(data_dir).resolve()
    records, excluded, warnings = [], [], []
    for folder, label in LABELS.items():
        class_dir = data_dir / folder
        metadata = {}
        manifest = class_dir / "download_manifest.jsonl"
        if manifest.exists():
            for line_number, line in enumerate(manifest.read_text().splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    raise ValueError(
                        f"Invalid JSON in {folder} manifest line {line_number}"
                    ) from None
                filename = (
                    entry.get("filepath") or entry.get("file") or entry.get("filename")
                )
                if filename and entry.get("status", "ok") == "ok":
                    metadata[Path(filename).name] = entry
        for path in sorted(class_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
                continue
            relative = path.relative_to(data_dir).as_posix()
            try:
                pixel_hash, dhash, width, height = image_signatures(path)
            except (
                OSError,
                UnidentifiedImageError,
                Image.DecompressionBombError,
            ) as error:
                excluded.append(
                    {
                        "path": relative,
                        "reason": "unreadable_image",
                        "error": type(error).__name__,
                    }
                )
                continue
            source = metadata.get(path.name, {})
            if source.get("label") not in (None, folder):
                warnings.append(
                    {
                        "path": relative,
                        "reason": "manifest_label_differs_from_folder",
                        "manifest_label": source["label"],
                    }
                )
            records.append(
                {
                    "path": relative,
                    "label": label,
                    "sha256": file_sha256(path),
                    "pixel_sha256": pixel_hash,
                    "dhash": dhash,
                    "width": width,
                    "height": height,
                    "source_page": source.get("page_url"),
                    "license": source.get("license"),
                }
            )
    if not records:
        raise ValueError(f"No readable dataset images found in {data_dir}")
    usable = []
    for members in group_records(records, distance):
        if len({record["label"] for record in members}) > 1:
            for record in members:
                excluded.append({**record, "reason": "cross_label_duplicate_group"})
            continue
        seen_pixels = {}
        for record in sorted(members, key=lambda row: row["path"]):
            pixels = record["pixel_sha256"]
            if pixels in seen_pixels:
                excluded.append(
                    {
                        **record,
                        "reason": "exact_pixel_duplicate",
                        "duplicate_of": seen_pixels[pixels],
                    }
                )
            else:
                seen_pixels[pixels] = record["path"]
                usable.append(record)
    assign_splits(usable, seed)
    snapshot = {
        "schema_version": 1,
        "seed": seed,
        "ratios": SPLITS,
        "grouping": {
            "algorithm": "sha256+RGB-pixels+source-photo+128-bit-dHash",
            "hamming_distance": distance,
        },
        "records": sorted(usable, key=lambda record: record["path"]),
        "excluded": sorted(excluded, key=lambda record: record["path"]),
        "warnings": warnings,
    }
    snapshot["fingerprint"] = dataset_fingerprint(snapshot)
    return snapshot


def load_snapshot(path, data_dir, verify_files=True):
    snapshot = json.loads(Path(path).read_text())
    if snapshot.get("schema_version") != 1 or snapshot.get(
        "fingerprint"
    ) != dataset_fingerprint(snapshot):
        raise ValueError(
            "Dataset snapshot fingerprint/schema is invalid; regenerate it explicitly"
        )
    groups, pixels, paths = {}, {}, set()
    root = Path(data_dir).resolve()
    for record in snapshot["records"]:
        relative = Path(record["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Snapshot paths must stay inside the dataset directory")
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Snapshot path escapes dataset directory")
        if record["split"] not in SPLITS or record["label"] not in (0, 1):
            raise ValueError("Invalid split or label in snapshot")
        if record["path"] in paths:
            raise ValueError("Repeated image path in snapshot")
        paths.add(record["path"])
        for mapping, key in (
            (groups, record["group"]),
            (pixels, record["pixel_sha256"]),
            (pixels, record["sha256"]),
        ):
            if key in mapping and mapping[key] != record["split"]:
                raise ValueError("Duplicate leakage across dataset splits")
            mapping[key] = record["split"]
        if verify_files and file_sha256(path) != record["sha256"]:
            raise ValueError(
                f"Dataset image changed since split creation: {record['path']}"
            )
    for split in SPLITS:
        if {row["label"] for row in snapshot["records"] if row["split"] == split} != {
            0,
            1,
        }:
            raise ValueError(f"Split {split} must include both classes")
    return snapshot


def default_data_dir():
    import os

    path = Path(os.getenv("DATA_DIR") or "data/raw").expanduser()
    return path if path.is_absolute() else ROOT_DIR / path
