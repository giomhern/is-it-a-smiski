"""Exercise the Docker API with Render Free's CPU and memory limits."""

import io
import json
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:5052"


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def upload(payload, expected):
    boundary = "smiski-memory-test"
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="photo.jpg"\r\n\r\n'.encode()
        + payload
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = Request(
        f"{URL}/api/predict",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urlopen(request, timeout=120) as response:
            status = response.status
            result = json.load(response)
            assert result["prediction"] in ("Smiski", "Non-Smiski")
    except HTTPError as error:
        status = error.code
        error.close()
    assert status == expected, (status, expected)


def main():
    container = docker(
        "run",
        "--detach",
        "--platform",
        "linux/amd64",
        "--memory",
        "512m",
        "--memory-swap",
        "512m",
        "--cpus",
        "0.1",
        "--publish",
        "127.0.0.1:5052:5050",
        "is-it-a-smiski:local",
    )
    try:
        started = time.monotonic()
        while True:
            try:
                with urlopen(f"{URL}/health", timeout=5) as response:
                    assert json.load(response) == {"status": "ok"}
                break
            except (URLError, TimeoutError, ConnectionError):
                if time.monotonic() - started > 120:
                    raise TimeoutError("API did not start within 120 seconds")
                time.sleep(0.5)
        print(f"Healthy after {time.monotonic() - started:.1f}s", flush=True)
        cases = [
            ((4000, 3000), "RGB", "JPEG", 1, 200),
            ((8000, 4000), "RGB", "JPEG", 1, 200),
            ((8000, 4000), "RGBA", "PNG", 1, 200),
            ((8000, 4000), "RGB", "JPEG", 6, 200),
            ((8000, 4000), "RGBA", "PNG", 6, 200),
            ((8000, 4000), "CMYK", "JPEG", 1, 200),
            ((4000, 4000), "RGBA", "WEBP", 1, 200),
            ((8000, 5000), "RGBA", "WEBP", 1, 400),
            ((8001, 4000), "RGB", "JPEG", 1, 400),
            ((8000, 5000), "RGBA", "PNG", 6, 400),
        ]
        for run in range(2):
            for size, mode, fmt, orientation, expected in cases:
                with Image.new(mode, size) as image, io.BytesIO() as payload:
                    exif = image.getexif()
                    exif[274] = orientation
                    image.save(payload, format=fmt, exif=exif)
                    upload(payload.getvalue(), expected)
                events = docker(
                    "exec", container, "cat", "/sys/fs/cgroup/memory.events"
                )
                counters = dict(line.split() for line in events.splitlines())
                assert counters["oom"] == counters["oom_kill"] == "0", events
                print(
                    f"Round {run + 1}: {size} {mode} {fmt} EXIF {orientation}: {expected}",
                    flush=True,
                )
            for photo in ("smiski/test-smiski.jpeg", "non-smiski/test-sonny-angel.jpg"):
                upload((ROOT / "tests" / photo).read_bytes(), 200)
            upload(b"not an image", 400)
        print(docker("stats", "--no-stream", "--format", "{{.MemUsage}}", container))
        print("Passed at 512 MiB, no swap, 0.1 CPU; no OOM events.")
    finally:
        subprocess.run(
            ["docker", "exec", container, "cat", "/sys/fs/cgroup/memory.events"],
            check=False,
        )
        print(docker("logs", "--tail", "10", container))
        docker("rm", "--force", container)


if __name__ == "__main__":
    main()
