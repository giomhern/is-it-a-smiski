"""Collect Openverse candidates for local review, without changing training data."""

import argparse
import hashlib
import html
import io
import json
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

from backend.config import ROOT_DIR
from backend.helpers.dataset import image_signatures

API = "https://api.openverse.org/v1/images/"
USER_AGENT = "is-it-a-smiski/0.1 (github.com/giomhern/is-it-a-smiski; dataset review)"
MAX_BYTES = 10 * 1024 * 1024
LICENSES = {"cc0", "by"}
DECISIONS = {"pending", "smiski", "non_smiski", "reject", "uncertain"}


class RateLimited(Exception):
    pass


def fetch(url, limit=MAX_BYTES):
    if urlsplit(url).scheme not in {"http", "https"}:
        raise ValueError("Only HTTP(S) URLs are supported")
    time.sleep(1)  # Small, sequential requests; never bypass provider limits.
    try:
        with urlopen(
            Request(url, headers={"User-Agent": USER_AGENT}), timeout=30
        ) as response:
            content = response.read(limit + 1)
    except HTTPError as error:
        if error.code == 429:
            raise RateLimited(
                f"Rate limited; stop and retry later (Retry-After: {error.headers.get('Retry-After', 'unspecified')})."
            ) from error
        raise
    if len(content) > limit:
        raise ValueError("Response exceeds size limit")
    return content


def inspect_image(content, min_side=512):
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(content)) as raw:
            if raw.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Unsupported image format")
            if raw.width * raw.height > 32_000_000:
                raise ValueError("Image exceeds 32 megapixels")
            extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[raw.format]
            image = ImageOps.exif_transpose(raw).convert("RGB")
    if min(image.size) < min_side:
        raise ValueError(f"Shorter side below {min_side}px")
    small = image.convert("L")
    small.thumbnail((256, 256))
    flags = []
    brightness = ImageStat.Stat(small).mean[0]
    if brightness < 25 or brightness > 235:
        flags.append("extreme_exposure")
    if ImageStat.Stat(small.filter(ImageFilter.FIND_EDGES)).stddev[0] < 8:
        flags.append("possible_blur_or_low_detail")
    return image, extension, flags


def save_manifest(out, records):
    temporary = out / "manifest.json.tmp"
    temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(out / "manifest.json")


def collect(out, records, queries, label, per_query):
    known_ids = {row["id"] for row in records}
    for query in queries:
        print(f"Searching {query!r} (up to {per_query} results)", flush=True)
        remaining, page = per_query, 1
        while remaining:
            data = json.loads(
                fetch(
                    API
                    + "?"
                    + urlencode(
                        {
                            "q": query,
                            "license": "cc0,by",
                            "category": "photograph",
                            "page_size": min(20, per_query),
                            "page": page,
                        }
                    )
                )
            )
            results = data.get("results", [])
            for result in results[:remaining]:
                if result["id"] in known_ids:
                    continue
                row = {
                    key: result.get(key)
                    for key in (
                        "id",
                        "title",
                        "creator",
                        "creator_url",
                        "license",
                        "license_version",
                        "license_url",
                        "attribution",
                        "source",
                        "provider",
                    )
                }
                row.update(
                    query=query,
                    proposed_label=label,
                    page_url=result.get("foreign_landing_url"),
                    source_url=result.get("url"),
                    collected_at=datetime.now(UTC).isoformat(),
                    status="rejected",
                    review="pending",
                    license_verified=False,
                )
                try:
                    if (
                        row["license"] not in LICENSES
                        or not row["license_url"]
                        or not row["page_url"]
                    ):
                        raise ValueError(
                            "Missing source/license metadata or disallowed license"
                        )
                    content = fetch(row["source_url"] or "")
                    image, extension, flags = inspect_image(content)
                    sha = hashlib.sha256(content).hexdigest()
                    path = out / "images" / (sha + extension)
                    path.write_bytes(content)
                    pixel_hash, dhash, width, height = image_signatures(path)
                    row.update(
                        sha256=sha,
                        pixel_sha256=pixel_hash,
                        dhash=dhash,
                        width=width,
                        height=height,
                    )
                    duplicate = next(
                        (
                            old
                            for old in records
                            if old.get("pixel_sha256") == pixel_hash
                        ),
                        None,
                    )
                    if duplicate:
                        row.update(
                            reason="exact_duplicate", duplicate_of=duplicate["id"]
                        )
                        if not any(
                            old.get("filepath") == path.relative_to(out).as_posix()
                            for old in records
                        ):
                            path.unlink()
                    else:
                        near = [
                            old["id"]
                            for old in records
                            if old.get("dhash")
                            and (int(old["dhash"], 16) ^ int(dhash, 16)).bit_count()
                            <= 6
                        ]
                        image.thumbnail((360, 360))
                        thumbnail = out / "thumbs" / (sha + ".jpg")
                        image.save(thumbnail, quality=85)
                        row.update(
                            status="candidate",
                            filepath=path.relative_to(out).as_posix(),
                            thumbnail=thumbnail.relative_to(out).as_posix(),
                            flags=flags,
                            near_duplicate_ids=near,
                        )
                except (
                    OSError,
                    ValueError,
                    UnidentifiedImageError,
                    Image.DecompressionBombError,
                    Image.DecompressionBombWarning,
                ) as error:
                    row["reason"] = str(error)
                records.append(row)
                known_ids.add(row["id"])
                save_manifest(out, records)
            remaining -= len(results[:remaining])
            if not results or page >= data.get("page_count", page):
                break
            page += 1


def apply_decisions(records, path):
    decisions = json.loads(path.read_text())
    if not isinstance(decisions, dict):
        raise TypeError("Decisions must be an object keyed by image ID")
    by_id = {row["id"]: row for row in records}
    updates = []
    for identifier, choice in decisions.items():
        if (
            identifier not in by_id
            or not isinstance(choice, dict)
            or choice.get("decision") not in DECISIONS
        ):
            raise ValueError(f"Unknown image or invalid decision: {identifier}")
        row = by_id[identifier]
        approved = choice["decision"] in {"smiski", "non_smiski"}
        verified = choice.get("license_verified") is True
        if approved and (row["status"] != "candidate" or not verified):
            raise ValueError(
                "Approval requires a usable candidate and source/license verification"
            )
        updates.append((row, choice["decision"], verified))
    for row, decision, verified in updates:
        row.update(review=decision, license_verified=verified)


def safe_link(url):
    return (
        html.escape(url, quote=True)
        if url and urlsplit(url).scheme in {"http", "https"}
        else "#"
    )


def gallery(out, records):
    cards = []
    for row in records:
        if row["status"] != "candidate":
            continue
        options = "".join(
            f'<option value="{value}" {"selected" if row["review"] == value else ""}>{value}</option>'
            for value in ("pending", "smiski", "non_smiski", "reject", "uncertain")
        )
        flags = row["flags"] + (
            ["possible near duplicate"] if row["near_duplicate_ids"] else []
        )
        cards.append(f'''<article data-id="{html.escape(row["id"], quote=True)}">
<a href="{row["filepath"]}"><img loading="lazy" src="{row["thumbnail"]}" alt="Candidate photograph"></a>
<p>Proposed: {row["proposed_label"]} · {html.escape(row["query"])}</p>
<p>{html.escape(row["title"] or "Untitled")} — {html.escape(row["creator"] or "Unknown creator")}</p>
<p>{html.escape(", ".join(flags) or "No automatic quality flags")} · {row["width"]}×{row["height"]}</p>
<p><a href="{safe_link(row["page_url"])}">Original source</a> · <a href="{safe_link(row["license_url"])}">{html.escape(row["license"])}</a></p>
<label>Decision <select>{options}</select></label><br>
<label><input type="checkbox" {"checked" if row["license_verified"] else ""}> I verified the original source, license, and host terms</label></article>''')
    (out / "index.html").write_text(
        """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Image candidate review</title>
<style>body{font:16px system-ui;background:#f6f7f4;color:#20261d;margin:24px}header{max-width:850px}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}article{background:white;padding:16px;border:1px solid #ccc;border-radius:8px}img{width:100%;height:260px;object-fit:contain}p{line-height:1.5}button,select{font:inherit;padding:8px}a{color:#285337}</style>
<header><h1>Image candidates</h1><p>Collected using Openverse; this project is not endorsed or certified by Openverse. Search labels and quality flags are suggestions. Inspect each original: positives need an identifiable physical Smiski; check negatives for hidden Smiskis. Exclude costumes, packaging-only shots, graphics, and ambiguous subjects. Verify permissions on the original host; API license metadata is not approval.</p>
<p>Keep related photographer/shoot/listing images together when splitting. Near-duplicate flags are approximate and only compare this collection. Rejected downloads and exact duplicates are listed in <a href="manifest.json">the manifest</a>.</p>
<p>Save decisions before closing or refreshing. To resume, import the downloaded JSON using the collector's --decisions option. No training photos are moved or created by approval.</p>
<button id="save">Download review decisions</button><p id="message" role="status"></p></header><main>"""
        + "\n".join(cards)
        + """</main><script>
document.querySelector('#save').addEventListener('click',()=>{
 const decisions={};
 for(const card of document.querySelectorAll('article')){
  const decision=card.querySelector('select').value,verified=card.querySelector('input').checked;
  if(['smiski','non_smiski'].includes(decision)&&!verified){document.querySelector('#message').textContent='Verify the source/license for each approved image first.';return;}
  decisions[card.dataset.id]={decision,license_verified:verified};
 }
 const url=URL.createObjectURL(new Blob([JSON.stringify(decisions,null,2)],{type:'application/json'}));
 const a=document.createElement('a');a.href=url;a.download='review-decisions.json';a.click();
 setTimeout(()=>URL.revokeObjectURL(url),1000);
 document.querySelector('#message').textContent='Decisions downloaded. Import the file to save them into the manifest.';
});</script></html>"""
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", nargs="+")
    parser.add_argument(
        "--label", choices=["smiski", "non_smiski"], help="Proposed label only"
    )
    parser.add_argument(
        "--per-query", type=int, default=10, help="Search results per query, 1–50"
    )
    parser.add_argument("--out", type=Path, default=ROOT_DIR / "data/candidates-v1")
    parser.add_argument(
        "--decisions", type=Path, help="Import gallery decisions without collecting"
    )
    args = parser.parse_args()
    if args.decisions and args.queries:
        parser.error("Use --decisions separately from --queries")
    if not args.decisions and (not args.queries or not args.label):
        parser.error("Collection requires --queries and --label")
    if not 1 <= args.per_query <= 50:
        parser.error("--per-query must be between 1 and 50")
    out = args.out.resolve()
    raw = (ROOT_DIR / "data/raw").resolve()
    if out == raw or raw in out.parents:
        parser.error("Use a candidate directory outside data/raw")
    if args.decisions and not (out / "manifest.json").is_file():
        parser.error("No candidate manifest exists at --out")
    for folder in ("images", "thumbs"):
        (out / folder).mkdir(parents=True, exist_ok=True)
    manifest = out / "manifest.json"
    records = json.loads(manifest.read_text()) if manifest.exists() else []
    failed = False
    try:
        if args.decisions:
            apply_decisions(records, args.decisions)
        else:
            collect(out, records, args.queries, args.label, args.per_query)
    except (RateLimited, URLError, ValueError, TypeError) as error:
        print(f"Stopped: {error}")
        failed = True
    finally:
        save_manifest(out, records)
        gallery(out, records)
    candidates = sum(row["status"] == "candidate" for row in records)
    print(
        f"{candidates} candidates, {len(records) - candidates} rejected/duplicates. Gallery: {out / 'index.html'}"
    )
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
