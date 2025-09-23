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


async def main():
    ap = argparse.ArgumentParser(description="Flickr image downloader with manifest")
    ap.add_argument("--queries", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--per-query", type=int, default=200)
    ap.add_argument("--min-width", type=int, default=256)
    ap.add_argument("--min-height", type=int, default=256)
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument("--license-filter", choices=["cc"], default=None,
                    help="Use 'cc' to restrict to Creative Commons / PD / CC0 (recommended).")
    ap.add_argument("--manifest-prefix", default="download_manifest")
    args = ap.parse_args()

    key = os.getenv("FLICKR_API_KEY")
    if not key:
        print("ERROR: set FLICKR_API_KEY", file=sys.stderr)
        sys.exit(2)

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / f"{args.manifest_prefix}.csv"
    jsonl_path = outdir / f"{args.manifest_prefix}.jsonl"

    connector = aiohttp.TCPConnector(limit_per_host=max(4, args.concurrency))
    async with aiohttp.ClientSession(connector=connector) as session, \
        open(csv_path, "w", newline="", encoding="utf-8") as csvf, \
        open(jsonl_path, "w", encoding="utf-8") as jsonlf:

        writer = csv.DictWriter(csvf, fieldnames=[
            "id","label","query","provider","source_url","page_url","license",
            "filepath","width","height","sha256","status","reason"
        ])
        writer.writeheader()

        # Search
        all_records: List[Dict[str, Any]] = []
        for q in args.queries:
            print(f"[flickr] searching '{q}' (limit={args.per_query})")
            recs = await flickr_search(session, key, q, args.per_query, args.license_filter)
            all_records.extend(recs)
            await asyncio.sleep(0.2 + random.random() * 0.3)
        print(f"[flickr] {len(all_records)} candidate URLs")

        # Download
        sem = asyncio.Semaphore(args.concurrency)
        seen_urls, seen_hashes = set(), set()

        async def worker(rec: Dict[str, Any]) -> Dict[str, Any]:
            async with sem:
                url = rec["source_url"]
                if not url:
                    return {"status": "skip", "reason": "no_url"}
                if url in seen_urls:
                    return {"status": "skip", "reason": "dup_url"}

                b, ct, status = await fetch_bytes(session, url)
                if not b:
                    return {"status": "skip", "reason": f"http_{status}"}
                hsh = sha256_bytes(b)
                if hsh in seen_hashes:
                    return {"status": "skip", "reason": "dup_hash"}

                w, h = read_w_h(b)
                if (w and w < args.min_width) or (h and h < args.min_height):
                    return {"status": "skip", "reason": "too_small", "width": w, "height": h}

                ext = pick_ext(url, ct)
                fname = f"{slugify(rec['query'])}-{int(time.time()*1000)}-{random.randint(1000,9999)}{ext}"
                path = outdir / fname
                try:
                    with open(path, "wb") as f:
                        f.write(b)
                except Exception:
                    return {"status": "skip", "reason": "write_error"}

                seen_urls.add(url)
                seen_hashes.add(hsh)
                return {"status": "ok", "filepath": str(path), "sha256": hsh, "width": w, "height": h}

        tasks = [asyncio.create_task(worker(r)) for r in all_records if r.get("source_url")]
        done = 0
        for coro, rec in zip(asyncio.as_completed(tasks), [r for r in all_records if r.get("source_url")]):
            res = await coro
            row = {
                "id": hashlib.md5((rec["source_url"] or str(time.time())).encode()).hexdigest(),
                "label": args.label,
                "query": rec["query"],
                "provider": rec["provider"],
                "source_url": rec["source_url"],
                "page_url": rec["page_url"],
                "license": rec.get("license"),
                "filepath": res.get("filepath"),
                "width": res.get("width"),
                "height": res.get("height"),
                "sha256": res.get("sha256"),
                "status": res["status"],
                "reason": res.get("reason"),
            }
            writer.writerow(row)
            jsonl_path.write_text("", encoding="utf-8") if not jsonl_path.exists() else None
            with open(jsonl_path, "a", encoding="utf-8") as jf:
                jf.write(str(row) + "\n")
            done += 1
            if done % 25 == 0:
                print(f"downloaded {done}/{len(tasks)}")

        print(f"✅ Done. Saved to {outdir}")
        print(f"   Manifest CSV:   {csv_path}")
        print(f"   Manifest JSONL: {jsonl_path}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")



