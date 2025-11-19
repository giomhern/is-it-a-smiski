import torch 
import torchvision 
import torch.nn as nn 
import torch.optim as optim 
import torchvision.transforms as transforms 
from torch.utils.data import DataLoader, Dataset 
from PIL import Image 
import os 
from pathlib import Path
from sklearn.model_selection import train_test_split
import json 

DATA_DIR = "/Users/giomhern/04 Projects/is-it-a-smiski/data/raw"
BATCH_SIZE = 32
EPOCHS = 10 
LEARNING_RATE = 0.001
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")

# data transforms 
train_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(10),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225])
])
val_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(10),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225])
])

# custom dataset class 
class SmiskiDataset(Dataset):
    def __init__(self, image_paths, labels, transforms=None):
        self.image_paths = image_paths
        self.labels = labels
        self.transforms = transforms
    
    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, index):
        img_path = self.image_paths[index]
        label = self.labels[index]
        image = Image.open(img_path).convert("RGB")
        if self.transforms:
            image = self.transforms(image)
        return image, label
    
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



