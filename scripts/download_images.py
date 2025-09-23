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


async def flickr_search(session: aiohttp.ClientSession, key: str, query: str, limit: int, license_filter: Optional[str]) -> List[Dict[str, Any]]:
    per_page = 250 # per page photo limit 
    pages = math.ceil(limit / per_page)
    out: List[Dict[str, Any]] = [] 

    licenses = "1, 2, 3, 4, 5, 6, 7, 8, 9, 10" if license_filter == "cc" else None 
    for page in range(1, pages + 1):
        params = {
            "method": "flickr.photos.search", 
            "api_key": key, 
            "text": query, 
            "content_type": 1, 
            "media": "photos", 
            "safe_search": 1, 
            "per_page": per_page, 
            "page": page, 
            "extras": "owner_name, license, url_o, url_l, url_c, url_m", 
            "format": "json", 
            "nojsoncallback": 1
        }

        if licenses:
            params["license"] = licenses
        async with session.get(FLICKR_ENDPOINT, params=params, timeout=TIMEOUT) as r:
            if r.status != 200:
                text = await r.text()
                print(f"[flickr] HTTP {r.status} for '{query}' page={page}: {text[:200]}", file=sys.stderr)
                break 
            data = r.json()
            photos = data.get("photos", {}).get("photo", [])
            for p in photos:
                url = p.get("url_o") or p.get("url_l") or p.get("url_c") or p.get("url_m")
                if not url:
                    continue 
                w = p.get("width_o") or p.get("width_l") or p.get("width_c") or p.get("width_m")
                h = p.get("height_o") or p.get("height_l") or p.get("height_c") or p.get("height_m")

                out.append({
                    "source_url": url, 
                    "page_url": f"https://www.flicker.com/photos/{p.get("owner")}/{p.get("id")}", 
                    "license": FLICKR_LICENSE_MAP.get(str(p.get("license")), None),
                    "width": int(w) if w else None,
                    "height": int(h) if h else None,
                    "query": query,
                    "provider": "flickr",
                })

        await asyncio.sleep(0.3 + random.random() * 0.6)
        if len(out) >= limit:
            break 
    return out[:limit]


async def fetch_bytes(session: aiohttp.ClientSession, url: str) -> Tuple[Optional[bytes], Optional[str], int]:
    try:
        async with session.get(url, headers={"User-Agent": UA}, allow_redirects=True, timeout=TIMEOUT) as r:
            if r.status != 200:
                return None, None, r.status
            return await r.read(), r.headers.get("Content-Type"), 200
    except Exception:
        return None, None, -1


        
                




