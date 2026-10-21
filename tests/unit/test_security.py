import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from backend.helpers.rate_limit import retry_after


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = str(Path(directory.name) / "limits.db")

    def test_budget_is_atomic_and_remains_bounded(self):
        with (
            ThreadPoolExecutor(max_workers=8) as pool,
            patch("backend.helpers.rate_limit.time.time", return_value=100),
        ):
            results = list(pool.map(lambda _: retry_after(self.path), range(40)))
        self.assertEqual(results.count(0), 30)
        self.assertEqual(results.count(20), 10)
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM budgets").fetchone()[0], 2
            )

    def test_hourly_budget_survives_minute_resets(self):
        for minute in range(10):
            with patch(
                "backend.helpers.rate_limit.time.time", return_value=minute * 60
            ):
                for _ in range(30):
                    self.assertEqual(retry_after(self.path), 0)
        with patch("backend.helpers.rate_limit.time.time", return_value=600):
            self.assertEqual(retry_after(self.path), 3000)
        with patch("backend.helpers.rate_limit.time.time", return_value=3600):
            self.assertEqual(retry_after(self.path), 0)

    def test_fresh_process_cannot_reset_exhausted_budget(self):
        with patch("backend.helpers.rate_limit.time.time", return_value=100):
            for _ in range(30):
                retry_after(self.path)
        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from unittest.mock import patch; "
                    "from backend.helpers.rate_limit import retry_after; "
                    "import sys; "
                    "clock=patch('backend.helpers.rate_limit.time.time', return_value=100); "
                    "clock.start(); assert retry_after(sys.argv[1]) == 20"
                ),
                self.path,
            ],
            check=True,
        )


class ApiSecurityTests(unittest.TestCase):
    def setUp(self):
        from backend.api.app import app

        self.app = app
        self.client = app.test_client()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        config = patch.dict(
            app.config, {"RATE_LIMIT_DB": str(Path(directory.name) / "limits.db")}
        )
        config.start()
        self.addCleanup(config.stop)

    def test_throttles_before_parsing_and_keeps_health_available(self):
        with patch("backend.helpers.rate_limit.time.time", return_value=100):
            for _ in range(30):
                self.assertEqual(self.client.post("/api/predict").status_code, 400)
            with patch("backend.api.app.Image.open") as image:
                response = self.client.post(
                    "/api/predict", headers={"X-Forwarded-For": "spoofed"}
                )
                self.assertEqual(response.status_code, 429)
                self.assertEqual(response.headers["Retry-After"], "20")
                image.assert_not_called()
            self.assertEqual(self.client.get("/health").status_code, 200)
            self.assertEqual(self.client.options("/api/predict").status_code, 200)
        with patch("backend.helpers.rate_limit.time.time", return_value=120):
            self.assertEqual(self.client.post("/api/predict").status_code, 400)

    def test_storage_failure_does_not_allow_unlimited_predictions(self):
        with (
            patch("backend.api.app.retry_after", side_effect=sqlite3.OperationalError),
            patch.object(self.app.logger, "exception"),
        ):
            self.assertEqual(self.client.post("/api/predict").status_code, 503)

    def test_rejects_excessive_form_parts_and_text_fields(self):
        for data in ({"a": "1", "b": "2", "c": "3"}, {"a": "x" * (128 * 1024 + 1)}):
            response = self.client.post(
                "/api/predict", data=data, content_type="multipart/form-data"
            )
            self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
