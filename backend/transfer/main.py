import torch
import torch.nn as nn
import torch.optim as optim
import torchvision.transforms as transforms
from torchvision import models
from torchvision.models import ResNet50_Weights
from torch.utils.data import DataLoader, Dataset
from PIL import Image, ImageOps
from pathlib import Path
from backend.config import get_model_path

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
# Validation and serving must use the same deterministic preprocessing.
val_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
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
        with Image.open(img_path) as raw:
            image = ImageOps.exif_transpose(raw).convert("RGB")
        if self.transforms:
            image = self.transforms(image)
        return image, label

class SmiskiClassifier:
    def __init__(self, device=DEVICE, model_name="resnet50", pretrained=True, lr=LEARNING_RATE, batch_size=BATCH_SIZE):
        self.device = device
        self.model_name = model_name
        self.pretrained = pretrained
        self.lr = lr
        self.batch_size = batch_size

        self.model = None
        self.criterion = nn.CrossEntropyLoss()
        self.optimizer = None

    def build_model(self, num_classes=2, freeze_early=True, pretrained=None):
        if self.model_name == "resnet50":
            use_pretrained = self.pretrained if pretrained is None else pretrained
            self.model = models.resnet50(weights=ResNet50_Weights.DEFAULT if use_pretrained else None)
        else:
            raise ValueError("Unsupported model name.")

        if freeze_early:
            for param in self.model.layer1.parameters():
                param.requires_grad = False

        self.model.fc = nn.Linear(self.model.fc.in_features, num_classes)
        self.model = self.model.to(self.device)

        self.optimizer = optim.Adam(filter(lambda p: p.requires_grad, self.model.parameters()), lr=self.lr)

    def prepare_data(self, snapshot_path=None, data_dir=None, random_state=42):
        from backend.config import ROOT_DIR
        from backend.helpers.dataset import default_data_dir, load_snapshot

        data_dir = Path(data_dir) if data_dir else default_data_dir()
        snapshot = load_snapshot(snapshot_path or ROOT_DIR / "docs/dataset/split-v1.json", data_dir)
        generator = torch.Generator().manual_seed(random_state)
        loaders = {}
        for split, transform in (("train", train_transforms), ("validation", val_transforms)):
            records = [row for row in snapshot["records"] if row["split"] == split]
            dataset = SmiskiDataset(
                [data_dir / row["path"] for row in records],
                [row["label"] for row in records], transforms=transform,
            )
            loaders[split] = DataLoader(
                dataset, batch_size=self.batch_size, shuffle=split == "train", generator=generator,
            )
        self.train_loader = loaders["train"]
        self.val_loader = loaders["validation"]
        self.dataset_fingerprint = snapshot["fingerprint"]

    def _train_epoch(self):
        self.model.train()
        total_loss = 0.0
        correct = 0
        total = 0
        for images, labels in self.train_loader:
            images, labels = images.to(self.device), labels.to(self.device)
            self.optimizer.zero_grad()
            outputs = self.model(images)
            loss = self.criterion(outputs, labels)
            loss.backward()
            self.optimizer.step()

            total_loss += loss.item() * images.size(0)
            _, preds = torch.max(outputs, 1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)

        return total_loss / total, correct / total

    def _validate_epoch(self):
        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0
        with torch.no_grad():
            for images, labels in self.val_loader:
                images, labels = images.to(self.device), labels.to(self.device)
                outputs = self.model(images)
                loss = self.criterion(outputs, labels)

                total_loss += loss.item() * images.size(0)
                _, preds = torch.max(outputs, 1)
                correct += (preds == labels).sum().item()
                total += labels.size(0)

        return total_loss / total, correct / total

    def train(self, epochs=EPOCHS):
        if self.model is None:
            raise RuntimeError("call build_model() before train()")
        for epoch in range(epochs):
            train_loss, train_acc = self._train_epoch()
            val_loss, val_acc = self._validate_epoch()
            print(f"Epoch {epoch+1}/{epochs}  Train Loss: {train_loss:.4f} Acc: {train_acc:.4f}  Val Loss: {val_loss:.4f} Acc: {val_acc:.4f}")

    def save(self, path=None):
        path = Path(path) if path else get_model_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), path)

    def load(self, path, num_classes=2, freeze_early=True):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(
                f"Model checkpoint missing: {path}. "
                "See README.md or run python -m scripts.install_model --help."
            )
        self.build_model(num_classes=num_classes, freeze_early=freeze_early, pretrained=False)
        self.model.load_state_dict(torch.load(path, map_location=self.device, weights_only=True))
        self.model.eval()

    def predict(self, img):
        if self.model is None:
            raise RuntimeError("Load or build a model before prediction")
        if isinstance(img, (str, Path)):
            with Image.open(img) as raw:
                image = ImageOps.exif_transpose(raw).convert("RGB")
        else:
            image = ImageOps.exif_transpose(img).convert("RGB")
        x = val_transforms(image).unsqueeze(0).to(self.device)
        self.model.eval()
        with torch.no_grad():
            out = self.model(x)
            probs = torch.softmax(out, dim=1).cpu().numpy()[0]
            pred = int(probs.argmax())
        return {"pred": pred, "probs": probs}

if __name__ == "__main__":
    raise SystemExit("Use python -m scripts.train_model --help for reproducible training.")
