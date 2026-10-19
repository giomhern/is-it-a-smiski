"""Shared ResNet50 inference and deterministic image preprocessing."""

from pathlib import Path

import torch
from PIL import Image
from torch import nn
from torch.utils.data import Dataset
from torchvision import models
from torchvision.models import ResNet50_Weights

from backend.helpers.preprocessing import preprocess_image

DEVICE = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "mps"
    if torch.backends.mps.is_available()
    else "cpu"
)


class SmiskiDataset(Dataset):
    def __init__(self, image_paths, labels):
        self.image_paths = image_paths
        self.labels = labels

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, index):
        with Image.open(self.image_paths[index]) as image:
            return torch.from_numpy(preprocess_image(image)), self.labels[index]


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
        # Meta tensors skip random weights; mmap avoids a second checkpoint copy.
        with torch.device("meta"):
            self.model = models.resnet50(weights=None)
            self.model.fc = nn.Linear(self.model.fc.in_features, 2)
        state = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
        self.model.load_state_dict(state, assign=True)
        self.model.to(self.device)
        self.model.eval()

    def predict(self, image):
        if self.model is None:
            raise RuntimeError("Load or build a model before prediction")
        if isinstance(image, (str, Path)):
            with Image.open(image) as raw:
                return self.predict(raw)
        tensor = torch.from_numpy(preprocess_image(image)).unsqueeze(0).to(self.device)
        self.model.eval()
        with torch.inference_mode():
            probabilities = self.model(tensor).softmax(1).cpu().numpy()[0]
        return {"pred": int(probabilities.argmax()), "probs": probabilities}
