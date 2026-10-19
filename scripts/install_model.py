"""Install the published checkpoint, verifying its SHA-256 before replacing anything."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen

from backend.config import ROOT_DIR, get_model_path

MANIFEST = ROOT_DIR / "backend" / "models" / "manifest.json"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_model(source=None, destination=None, manifest_path=None):
    manifest = json.loads(Path(manifest_path or MANIFEST).read_text())
    if destination:
        destination = Path(destination)
    elif manifest_path:
        filename = manifest["filename"]
        if Path(filename).name != filename:
            raise ValueError("Manifest filename must not include a directory")
        destination = ROOT_DIR / "backend/models" / filename
    else:
        destination = get_model_path()
    expected = manifest["sha256"]
    if destination.is_file() and sha256(destination) == expected:
        return destination

    source = source or (os.getenv("MODEL_URL") if manifest_path is None else None) or manifest["url"]
    if not source:
        raise ValueError(
            "No checkpoint source configured. Set MODEL_URL to a trusted hosted checkpoint "
            "or pass --source /path/to/smiski_classifier.pt. "
            "See README.md for the model release and installation instructions."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".part", delete=False) as output:
            temporary = Path(output.name)
            parsed = urlparse(str(source))
            if parsed.scheme in ("https", "http"):
                with urlopen(str(source), timeout=60) as response:
                    shutil.copyfileobj(response, output)
            else:
                with Path(source).expanduser().open("rb") as stream:
                    shutil.copyfileobj(stream, output)
        if sha256(temporary) != expected:
            raise ValueError("Checkpoint checksum mismatch; existing model was left untouched.")
        temporary.replace(destination)
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="Trusted checkpoint URL or local checkpoint path")
    parser.add_argument("--manifest", type=Path, help="Alternative versioned checkpoint manifest")
    parser.add_argument("--destination", type=Path, help="Override the checkpoint output path")
    args = parser.parse_args()
    try:
        print(f"Checkpoint ready: {install_model(args.source, args.destination, args.manifest)}")
    except (OSError, ValueError) as error:
        parser.exit(1, f"Model installation failed: {error}\n")


if __name__ == "__main__":
    main()
