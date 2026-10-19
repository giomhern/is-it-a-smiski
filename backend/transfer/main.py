"""Shared ResNet50 inference and deterministic image preprocessing."""

from pathlib import Path

import torch
from PIL import Image, ImageOps
from torch import nn
from torch.utils.data import Dataset
from torchvision import models, transforms
from torchvision.models import ResNet50_Weights

DEVICE = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "mps"
    if torch.backends.mps.is_available()
    else "cpu"
)
val_transforms = transforms.Compose(
    [
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ]
)


class SmiskiDataset(Dataset):
    def __init__(self, image_paths, labels):
        self.image_paths = image_paths
        self.labels = labels

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, index):
        with Image.open(self.image_paths[index]) as raw:
            image = ImageOps.exif_transpose(raw).convert("RGB")
        return val_transforms(image), self.labels[index]


class SmiskiClassifier:
    def __init__(self, device=DEVICE):
        self.device = device
        self.model = None

    def build_model(self, pretrained=True):
        weights = ResNet50_Weights.IMAGENET1K_V2 if pretrained else None
        self.model = models.resnet50(weights=weights)
        self.model.fc = nn.Linear(self.model.fc.in_features, 2)
        self.model.to(self.device)

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), path)

    def load(self, path):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(
                f"Model checkpoint missing: {path}. "
                "Run python -m scripts.install_model to download it."
            )
        self.build_model(pretrained=False)
        state = torch.load(path, map_location=self.device, weights_only=True)
        self.model.load_state_dict(state)
        self.model.eval()

    def predict(self, image):
        if self.model is None:
            raise RuntimeError("Load or build a model before prediction")
        if isinstance(image, (str, Path)):
            with Image.open(image) as raw:
                image = ImageOps.exif_transpose(raw).convert("RGB")
        else:
            image = ImageOps.exif_transpose(image).convert("RGB")
        tensor = val_transforms(image).unsqueeze(0).to(self.device)
        self.model.eval()
        with torch.inference_mode():
            probabilities = self.model(tensor).softmax(1).cpu().numpy()[0]
        return {"pred": int(probabilities.argmax()), "probs": probabilities}
