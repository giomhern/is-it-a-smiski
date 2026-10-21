import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from scripts.collect_candidates import (
    RateLimited,
    apply_decisions,
    collect,
    gallery,
    inspect_image,
)


def photo(size=(512, 600), color="green"):
    stream = io.BytesIO()
    Image.new("RGB", size, color).save(stream, "PNG")
    return stream.getvalue()


def result(identifier, license="by"):
    return {
        "id": identifier,
        "license": license,
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "foreign_landing_url": "https://example.org/photo",
        "url": "https://example.org/photo.png",
        "title": '<script>alert("unsafe")</script>',
        "creator": "Photographer",
    }


class CandidateTests(unittest.TestCase):
    def test_rejects_corruption_small_images_and_unsupported_formats(self):
        for content in (b"not a photo", photo((100, 100))):
            with self.assertRaises((ValueError, OSError)):
                inspect_image(content)
        stream = io.BytesIO()
        Image.new("RGB", (512, 512)).save(stream, "GIF")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            inspect_image(stream.getvalue())
        _, _, flags = inspect_image(photo(color="black"))
        self.assertIn("extreme_exposure", flags)
        self.assertIn("possible_blur_or_low_detail", flags)

    def test_collection_deduplicates_resumes_and_never_assigns_training_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            for name in ("images", "thumbs"):
                (out / name).mkdir()
            records = []
            response = json.dumps(
                {
                    "results": [result("a"), result("b"), result("c", "by-nc")],
                    "page_count": 1,
                }
            ).encode()
            with patch(
                "scripts.collect_candidates.fetch",
                side_effect=[response, photo(), photo()],
            ) as fetch:
                collect(out, records, ["green toys"], "non_smiski", 3)
                self.assertEqual(fetch.call_count, 3)
            self.assertEqual(
                [row["status"] for row in records],
                ["candidate", "rejected", "rejected"],
            )
            self.assertEqual(records[1]["duplicate_of"], "a")
            self.assertTrue(all(row["review"] == "pending" for row in records))
            self.assertNotIn("label", records[0])
            self.assertEqual(len(list((out / "images").iterdir())), 1)
            with patch(
                "scripts.collect_candidates.fetch", return_value=response
            ) as fetch:
                collect(out, records, ["green toys"], "non_smiski", 3)
                self.assertEqual(fetch.call_count, 1)
            gallery(out, records)
            page = (out / "index.html").read_text()
            self.assertNotIn('<script>alert("unsafe")</script>', page)
            self.assertIn("&lt;script&gt;", page)
            self.assertIn("Photographer", page)

    def test_rate_limit_preserves_completed_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            for name in ("images", "thumbs"):
                (out / name).mkdir()
            response = json.dumps(
                {"results": [result("a"), result("b")], "page_count": 1}
            ).encode()
            records = []
            with (
                patch(
                    "scripts.collect_candidates.fetch",
                    side_effect=[response, photo(), RateLimited("retry later")],
                ),
                self.assertRaises(RateLimited),
            ):
                collect(out, records, ["toys"], "smiski", 2)
            self.assertEqual(len(json.loads((out / "manifest.json").read_text())), 1)

    def test_approval_requires_verification_and_invalid_import_is_atomic(self):
        records = [
            {"id": "a", "status": "candidate", "review": "pending"},
            {"id": "b", "status": "rejected", "review": "pending"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "decisions.json"
            for decisions in (
                [],
                {"a": None},
                {"a": {"decision": "smiski", "license_verified": False}},
                {
                    "a": {"decision": "reject"},
                    "b": {"decision": "smiski", "license_verified": True},
                },
                {"unknown": {"decision": "reject"}},
            ):
                path.write_text(json.dumps(decisions))
                with self.assertRaises((ValueError, TypeError)):
                    apply_decisions(records, path)
                self.assertEqual(records[0]["review"], "pending")
            path.write_text(
                json.dumps({"a": {"decision": "non_smiski", "license_verified": True}})
            )
            apply_decisions(records, path)
            self.assertEqual(records[0]["review"], "non_smiski")


if __name__ == "__main__":
    unittest.main()
