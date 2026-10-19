import io
import json
import random
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import torch
from PIL import Image

from backend.helpers.dataset import (
    build_snapshot,
    dataset_fingerprint,
    group_records,
    load_snapshot,
)
from backend.helpers.evaluation import calculate_metrics
from backend.transfer.main import val_transforms
from scripts.evaluate_model import evaluation_status
from scripts.train_model import training_partitions


def fixture_dataset(directory):
    root = Path(directory)
    randomizer = random.Random(18)
    for name in ("smiski", "non_smiski"):
        folder = root / name
        folder.mkdir()
        for index in range(10):
            Image.frombytes("RGB", (32, 32), randomizer.randbytes(32 * 32 * 3)).save(
                folder / f"{index:02d}.png"
            )
    # A contradictory duplicate is quarantined in both folders.
    image = (root / "smiski/00.png").read_bytes()
    (root / "non_smiski/conflicting.png").write_bytes(image)
    # Same-class exact duplicates contribute only one sample.
    (root / "smiski/duplicate.png").write_bytes((root / "smiski/01.png").read_bytes())
    (root / "smiski/broken.jpg").write_bytes(b"broken image")
    return root


class DatasetTests(unittest.TestCase):
    def test_split_reproducibility_quarantine_and_no_group_leakage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = fixture_dataset(directory)
            snapshot = build_snapshot(root)
            self.assertEqual(snapshot, build_snapshot(root))
            reasons = Counter(row["reason"] for row in snapshot["excluded"])
            self.assertEqual(
                reasons,
                {
                    "cross_label_duplicate_group": 2,
                    "exact_pixel_duplicate": 1,
                    "unreadable_image": 1,
                },
            )
            groups = {}
            for record in snapshot["records"]:
                groups.setdefault(record["group"], set()).add(record["split"])
            self.assertTrue(all(len(splits) == 1 for splits in groups.values()))
            snapshot_path = root / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot))
            self.assertEqual(load_snapshot(snapshot_path, root), snapshot)
            for split in ("train", "validation", "test"):
                self.assertEqual(
                    {
                        row["label"]
                        for row in snapshot["records"]
                        if row["split"] == split
                    },
                    {0, 1},
                )

    def test_near_duplicates_and_source_photo_are_grouped_transitively(self):
        records = [
            {"sha256": "a", "pixel_sha256": "a", "dhash": "00", "source_page": None},
            {
                "sha256": "b",
                "pixel_sha256": "b",
                "dhash": "01",
                "source_page": "same-photo",
            },
            {
                "sha256": "c",
                "pixel_sha256": "c",
                "dhash": "ff",
                "source_page": "same-photo",
            },
        ]
        self.assertEqual(len(group_records(records, distance=1)), 1)
        self.assertEqual(len({row["group"] for row in records}), 1)

    def test_changed_images_and_split_tampering_fail_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = fixture_dataset(directory)
            snapshot = build_snapshot(root)
            path = root / "snapshot.json"
            path.write_text(json.dumps(snapshot))
            photo = root / snapshot["records"][0]["path"]
            original = photo.read_bytes()
            photo.write_bytes(b"changed bytes")
            with self.assertRaisesRegex(ValueError, "changed since split"):
                load_snapshot(path, root)
            photo.write_bytes(original)
            record = snapshot["records"][0]
            record["split"] = "test" if record["split"] != "test" else "train"
            path.write_text(json.dumps(snapshot))
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                load_snapshot(path, root)

    def test_explicit_cross_split_group_leakage_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = fixture_dataset(directory)
            snapshot = build_snapshot(root)
            train = next(row for row in snapshot["records"] if row["split"] == "train")
            test = next(row for row in snapshot["records"] if row["split"] == "test")
            test["group"] = train["group"]
            snapshot["fingerprint"] = dataset_fingerprint(snapshot)
            path = root / "snapshot.json"
            path.write_text(json.dumps(snapshot))
            with self.assertRaisesRegex(ValueError, "leakage"):
                load_snapshot(path, root)

    def test_training_partitions_do_not_include_reserved_test_photos(self):
        with tempfile.TemporaryDirectory() as directory:
            root = fixture_dataset(directory)
            snapshot = build_snapshot(root)
            path = root / "snapshot.json"
            path.write_text(json.dumps(snapshot))
            verified = load_snapshot(path, root)
            train, validation = training_partitions(verified)
            self.assertTrue(all(row["split"] == "train" for row in train))
            self.assertTrue(all(row["split"] == "validation" for row in validation))
            used = {root / row["path"] for row in train + validation}
            reserved = {
                root / row["path"]
                for row in snapshot["records"]
                if row["split"] == "test"
            }
            self.assertTrue(used.isdisjoint(reserved))


class EvaluationTests(unittest.TestCase):
    def test_metrics_match_known_confusion_matrix(self):
        result = calculate_metrics([0, 0, 1, 1], [0, 1, 1, 1], [0.1, 0.8, 0.7, 0.9])
        self.assertEqual(result["confusion_matrix"]["counts"], [[1, 1], [0, 2]])
        self.assertEqual(result["accuracy"], 0.75)
        self.assertAlmostEqual(result["per_class"]["Smiski"]["precision"], 2 / 3)
        self.assertAlmostEqual(result["per_class"]["Smiski"]["recall"], 1)
        self.assertAlmostEqual(result["per_class"]["Smiski"]["f1"], 0.8)
        self.assertAlmostEqual(result["brier_score"], 0.1875)

    def test_no_predicted_positives_is_well_defined(self):
        result = calculate_metrics([0, 1], [0, 0], [0.1, 0.2])
        self.assertEqual(result["per_class"]["Smiski"]["precision"], 0)
        self.assertEqual(result["per_class"]["Smiski"]["f1"], 0)

    def test_legacy_checkpoint_cannot_claim_held_out_results(self):
        self.assertEqual(
            evaluation_status("hash", {}, None, "test"),
            "diagnostic_only_training_provenance_unknown",
        )
        snapshot = {
            "fingerprint": "dataset",
            "records": [
                {"sha256": "train", "split": "train"},
                {"sha256": "val", "split": "validation"},
            ],
        }
        metadata = {
            "checkpoint_sha256": "hash",
            "dataset_fingerprint": "dataset",
            "training_image_sha256": ["train"],
            "validation_image_sha256": ["val"],
        }
        self.assertEqual(
            evaluation_status("hash", snapshot, metadata, "test"),
            "held_out_for_this_training_run",
        )
        metadata["training_image_sha256"] = ["test"]
        with self.assertRaisesRegex(ValueError, "partitions"):
            evaluation_status("hash", snapshot, metadata, "test")

    def test_validation_transform_is_deterministic(self):
        image = Image.frombytes(
            "RGB", (64, 64), random.Random(43).randbytes(64 * 64 * 3)
        )
        self.assertTrue(torch.equal(val_transforms(image), val_transforms(image)))


class ServingConsistencyTests(unittest.TestCase):
    def test_repeated_api_uploads_return_identical_predictions(self):
        from backend.api.app import app
        from backend.config import ROOT_DIR

        client = app.test_client()
        for fixture in ("smiski/test-smiski.jpeg", "non-smiski/test-sonny-angel.jpg"):
            payload = (ROOT_DIR / "tests" / fixture).read_bytes()
            results = []
            for _ in range(3):
                response = client.post(
                    "/api/predict", data={"image": (io.BytesIO(payload), "photo.jpg")}
                )
                self.assertEqual(response.status_code, 200)
                results.append(response.json)
            self.assertEqual(results[0], results[1])
            self.assertEqual(results[1], results[2])


if __name__ == "__main__":
    unittest.main()
