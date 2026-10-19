import hashlib
import io
import json
import os
import tempfile
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch

from PIL import Image

from backend.config import ROOT_DIR, get_model_path
from backend.helpers.dataset import default_data_dir
from scripts.install_model import install_model


class SetupTests(unittest.TestCase):
    def test_relative_model_path_is_anchored_to_repository(self):
        with patch.dict(os.environ, {"MODEL_PATH": "custom/model.pt"}):
            self.assertEqual(get_model_path(), ROOT_DIR / "custom/model.pt")

    def test_relative_dataset_path_is_anchored_to_repository(self):
        with patch.dict(os.environ, {"DATA_DIR": "custom/photos"}):
            self.assertEqual(default_data_dir(), ROOT_DIR / "custom/photos")

    def test_checkpoint_install_is_verified_and_preserves_existing_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination, manifest = (
                root / name for name in ("source.pt", "model.pt", "manifest.json")
            )
            source.write_bytes(b"valid checkpoint")
            manifest.write_text(
                json.dumps(
                    {
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "url": None,
                    }
                )
            )
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

    def test_alternative_manifest_install_has_an_explicit_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.pt"
            source.write_bytes(b"alternative model")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "filename": "baseline.pt",
                        "url": None,
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    }
                )
            )
            destination = root / "baseline.pt"
            install_model(str(source), destination, manifest)
            self.assertEqual(destination.read_bytes(), source.read_bytes())

    def test_checkpoint_can_be_downloaded_from_a_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.pt").write_bytes(b"downloaded checkpoint")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "sha256": hashlib.sha256(b"downloaded checkpoint").hexdigest(),
                        "url": None,
                    }
                )
            )
            handler = partial(SimpleHTTPRequestHandler, directory=directory)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch("scripts.install_model.MANIFEST", manifest):
                    destination = install_model(
                        f"http://127.0.0.1:{server.server_port}/source.pt",
                        root / "installed.pt",
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
        with patch(
            "torch.hub.download_url_to_file",
            side_effect=AssertionError("Unexpected model download"),
        ):
            from backend.api.app import app
        cls.client = app.test_client()

    def test_health_and_invalid_uploads(self):
        self.assertEqual(self.client.get("/health").json, {"status": "ok"})
        self.assertEqual(self.client.post("/api/predict").status_code, 400)
        response = self.client.post(
            "/api/predict", data={"image": (io.BytesIO(b"not an image"), "fake.jpg")}
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_multiple_photos(self):
        response = self.client.post(
            "/api/predict",
            data={
                "image": [
                    (io.BytesIO(b"first"), "first.jpg"),
                    (io.BytesIO(b"second"), "second.jpg"),
                ]
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("one photo", response.json["error"])

    def test_rejects_unsupported_format_despite_jpeg_filename(self):
        data = io.BytesIO()
        Image.new("RGB", (8, 8)).save(data, format="GIF")
        data.seek(0)
        response = self.client.post(
            "/api/predict", data={"image": (data, "disguised.jpg")}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("JPG, PNG, or WebP", response.json["error"])

    def test_rejects_photo_above_documented_size_limit(self):
        from backend.api.app import MAX_IMAGE_BYTES

        response = self.client.post(
            "/api/predict",
            data={"image": (io.BytesIO(b"x" * (MAX_IMAGE_BYTES + 1)), "large.jpg")},
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn("10 MB", response.json["error"])

    def test_rejects_excessive_dimensions_before_decoding(self):
        with patch("backend.api.app.Image.open") as open_image:
            image = open_image.return_value.__enter__.return_value
            image.format = "JPEG"
            image.width, image.height = 8_000, 6_000
            response = self.client.post(
                "/api/predict", data={"image": (io.BytesIO(b"fixture"), "large.jpg")}
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("40 megapixels", response.json["error"])
            image.convert.assert_not_called()
            image.load.assert_not_called()

    def test_truncated_photo_returns_client_error(self):
        payload = (ROOT_DIR / "tests/smiski/test-smiski.jpeg").read_bytes()
        response = self.client.post(
            "/api/predict",
            data={"image": (io.BytesIO(payload[:-100]), "truncated.jpg")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("valid image", response.json["error"])

    def test_inference_errors_return_generic_server_error(self):
        from backend.api.app import app

        with (
            patch(
                "backend.api.app.clf.predict", side_effect=OSError("internal detail")
            ),
            patch.object(app.logger, "exception"),
            (ROOT_DIR / "tests/smiski/test-smiski.jpeg").open("rb") as image,
        ):
            response = self.client.post(
                "/api/predict", data={"image": (image, "smiski.jpg")}
            )
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("internal detail", response.get_data(as_text=True))

    def test_real_predictions_have_valid_response(self):
        for fixture in ("smiski/test-smiski.jpeg", "non-smiski/test-sonny-angel.jpg"):
            with self.subTest(fixture=fixture):
                with (ROOT_DIR / "tests" / fixture).open("rb") as stream:
                    response = self.client.post(
                        "/api/predict", data={"image": (stream, Path(fixture).name)}
                    )
                self.assertEqual(response.status_code, 200)
                result = response.json
                self.assertIn(result["prediction"], ("Smiski", "Non-Smiski"))
                self.assertGreaterEqual(result["confidence"], 0)
                self.assertLessEqual(result["confidence"], 1)
                self.assertAlmostEqual(
                    sum(result["probabilities"].values()), 1, places=5
                )


if __name__ == "__main__":
    unittest.main()
