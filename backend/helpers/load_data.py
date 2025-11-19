from pathlib import Path
import json

DATA_DIR = "/Users/giomhern/04 Projects/is-it-a-smiski/data/raw"

def load_data():
    image_paths = []
    labels = []

    def resolve_record_path(rec, class_dir, manifest_parent):
        fp = rec.get("filepath") or rec.get("file") or rec.get("filename")
        if fp:
            p = Path(fp)
            if p.is_absolute() and p.exists():
                return p
            try:
                cand = (manifest_parent / fp).resolve()
                if cand.exists():
                    return cand
            except Exception:
                pass
            try:
                cand = class_dir / Path(fp).name
                if cand.exists():
                    return cand
            except Exception:
                pass

        fn = rec.get("filename")
        if fn:
            cand = class_dir / fn
            if cand.exists():
                return cand

        return None

    for class_name, label_value in (("smiski", 1), ("non_smiski", 0)):
        class_dir = Path(DATA_DIR) / class_name
        manifest_path = class_dir / "download_manifest.jsonl"

        if manifest_path.exists() and manifest_path.stat().st_size > 0:
            with manifest_path.open("r", encoding="utf-8") as fh:
                for line_no, line in enumerate(fh, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        print(f"warning: invalid json on line {line_no} in {manifest_path}, skipping")
                        continue

                    p = resolve_record_path(rec, class_dir, manifest_path.parent)
                    if p:
                        image_paths.append(str(p))
                        labels.append(label_value)
                    else:
                        continue
        else:
            if not class_dir.exists():
                print(f"warning: class directory does not exist: {class_dir}, skipping")
                continue
            exts = ("*.jpg", "*.jpeg", "*.png", "*.webp")
            found_any = False
            for ext in exts:
                for p in class_dir.glob(ext):
                    image_paths.append(str(p))
                    labels.append(label_value)
                    found_any = True
            if not found_any:
                print(f"warning: no manifest and no images found in {class_dir}, skipping")

    return image_paths, labels
