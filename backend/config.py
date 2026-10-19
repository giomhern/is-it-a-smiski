"""Paths and environment shared by the API, training, and CLI tools."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


def get_model_path():
    path = Path(os.getenv("MODEL_PATH") or "backend/models/smiski_classifier.pt").expanduser()
    return path if path.is_absolute() else ROOT_DIR / path
