import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch
from functools import partial

from backend.config import ROOT_DIR, get_model_path
from backend.helpers.load_data import load_data
from scripts.install_model import install_model


class SetupTests(unittest.TestCase):
    def test_relative_model_path_is_anchored_to_repository(self):
        with patch.dict(os.environ, {"MODEL_PATH": "custom/model.pt"}):
            self.assertEqual(get_model_path(), ROOT_DIR / "custom/model.pt")

    def test_loader_resolves_moved_manifest_and_override(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for label in ("smiski", "non_smiski"):
                folder = root / label
                folder.mkdir()
                (folder / "photo.jpg").write_bytes(b"fixture")
                (folder / "download_manifest.jsonl").write_text(
                    json.dumps({"filepath": "/old/machine/photo.jpg"}) + "\n"
                )
            with patch.dict(os.environ, {"DATA_DIR": str(root)}):
                paths, labels = load_data()
            self.assertEqual(labels, [1, 0])
            self.assertTrue(all(Path(path).is_file() for path in paths))

    def test_checkpoint_install_is_verified_and_preserves_existing_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination, manifest = (root / name for name in ("source.pt", "model.pt", "manifest.json"))
            source.write_bytes(b"valid checkpoint")
            manifest.write_text(json.dumps({
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "url": None,
            }))
            with patch("scripts.install_model.MANIFEST", manifest):
                install_model(str(source), destination)
                self.assertEqual(source.read_bytes(), destination.read_bytes())
                # An installed checkpoint also works offline with an unavailable source.
                install_model(str(root / "unavailable.pt"), destination)
                destination.write_bytes(b"existing checkpoint")
                source.write_bytes(b"corrupt download")
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    install_model(str(source), destination)
                self.assertEqual(destination.read_bytes(), b"existing checkpoint")
                self.assertEqual(list(root.glob("*.part")), [])

    def test_missing_checkpoint_has_actionable_error(self):
        from backend.transfer.main import SmiskiClassifier
        with self.assertRaisesRegex(FileNotFoundError, "scripts.install_model"):
            SmiskiClassifier().load(ROOT_DIR / "missing-test-checkpoint.pt")

    def test_checkpoint_can_be_downloaded_from_a_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.pt").write_bytes(b"downloaded checkpoint")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "sha256": hashlib.sha256(b"downloaded checkpoint").hexdigest(), "url": None,
            }))
            handler = partial(SimpleHTTPRequestHandler, directory=directory)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch("scripts.install_model.MANIFEST", manifest):
                    destination = install_model(
                        f"http://127.0.0.1:{server.server_port}/source.pt", root / "installed.pt",
                    )
                self.assertEqual(destination.read_bytes(), b"downloaded checkpoint")
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


class ApiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The real checkpoint must load without fetching ImageNet weights.
        with patch("torch.hub.download_url_to_file", side_effect=AssertionError("Unexpected model download")):
            from backend.api.app import app
        cls.client = app.test_client()

    def test_health_and_invalid_uploads(self):
        self.assertEqual(self.client.get("/health").json, {"status": "ok"})
        self.assertEqual(self.client.post("/api/predict").status_code, 400)
        response = self.client.post("/api/predict", data={"image": (io.BytesIO(b"not an image"), "fake.jpg")})
        self.assertEqual(response.status_code, 400)

    def test_real_predictions_have_valid_response(self):
        for fixture in ("smiski/test-smiski.jpeg", "non-smiski/test-sonny-angel.jpg"):
            with self.subTest(fixture=fixture):
                with (ROOT_DIR / "tests" / fixture).open("rb") as stream:
                    response = self.client.post("/api/predict", data={"image": (stream, Path(fixture).name)})
                self.assertEqual(response.status_code, 200)
                result = response.json
                self.assertIn(result["prediction"], ("Smiski", "Non-Smiski"))
                self.assertGreaterEqual(result["confidence"], 0)
                self.assertLessEqual(result["confidence"], 1)
                self.assertAlmostEqual(sum(result["probabilities"].values()), 1, places=5)


if __name__ == "__main__":
    unittest.main()
