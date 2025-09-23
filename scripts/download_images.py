import argparse, asyncio, csv, hashlib, io, os, random, re, sys, time, math
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import aiohttp
from PIL import Image

UA = "my-smiski/0.1 dataset bootstrapper"
TIMEOUT = aiohttp.ClientTimeout(total=30)
SAFE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
FLICKR_ENDPOINT = "https://api.flickr.com/services/rest/"

FLICKR_LICENSE_MAP = {
    "0": "All Rights Reserved",
    "1": "CC BY-NC-SA 2.0",
    "2": "CC BY-NC 2.0",
    "3": "CC BY-NC-ND 2.0",
    "4": "CC BY 2.0",
    "5": "CC BY-SA 2.0",
    "6": "CC BY-ND 2.0",
    "7": "No known copyright restrictions",
    "8": "US Gov Work",
    "9": "Public Domain",
    "10": "CC0",
}

def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "img"

def pick_ext(url: str, content_type: Optional[str]) -> str:
    uext = Path(url).suffix.lower()
    if uext in SAFE_EXTS:
        return uext
    ct = (content_type or "").split(";")[0].strip().lower()
    return {
        "image/jpeg": ".jpg", "image/jpg": ".jpg",
        "image/png": ".png", "image/webp": ".webp",
    }.get(ct, ".jpg")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def read_w_h(b: bytes) -> Tuple[Optional[int], Optional[int]]:
    try:
        im = Image.open(io.BytesIO(b))
        return im.width, im.height
    except Exception:
        return None, None

