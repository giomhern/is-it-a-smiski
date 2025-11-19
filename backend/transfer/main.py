import torch
import torchvision 
import torch.nn as nn 
import torch.optim as optim 
import torchvision.transforms as transforms 
from torchvision import models
from torchvision.models import ResNet50_Weights
from torch.utils.data import DataLoader, Dataset 
from PIL import Image 
import os 
from pathlib import Path
from sklearn.model_selection import train_test_split
import json 
from ..helpers.load_data import load_data

DATA_DIR = "data/raw"
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
    
class SmiskiClassifier:
    def __init__(self, device=DEVICE, model_name="resnet50", pretrained=True, lr=LEARNING_RATE, batch_size=BATCH_SIZE):
        self.device = device
        self.model_name = model_name
        self.lr = lr 
        self.batch_size = batch_size
        
        self.model = None 
        self.criterion = nn.CrossEntropyLoss()
        self.optimizer = None 

    def build_model(self, num_classes=2, freeze_early=True):
        if self.model_name == "resnet50":
            self.model = models.resnet50(weights=ResNet50_Weights.DEFAULT)
        else:
            raise ValueError("Unsupported model name.")

        if freeze_early:
            for param in self.model.layer1.parameters():
                param.requires_grad = False 

        self.model.fc = nn.Linear(self.model.fc.in_features, num_classes)
        self.model = self.model.to(self.device)

        self.optimizer = optim.Adam(filter(lambda p: p.requires_grad, self.model.parameters()), lr=self.lr)

    def prepare_data(self, image_paths, labels, val_split=0.2, shuffle=True, random_state=42):
        train_paths, val_paths, train_labels, val_labels = train_test_split(
            image_paths, labels, test_size=val_split, shuffle=shuffle, random_state=random_state
        )

        train_ds = SmiskiDataset(train_paths, train_labels, transforms=train_transforms)
        val_ds = SmiskiDataset(val_paths, val_labels, transforms=val_transforms)

        self.train_loader = DataLoader(train_ds, batch_size=self.batch_size, shuffle=True)
        self.val_loader = DataLoader(val_ds, batch_size=self.batch_size, shuffle=False)

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
    
    def save(self, path="smiski_classifier.pt"):
        torch.save(self.model.state_dict(), path)

    def load(self, path, num_classes=2, freeze_early=True):
        self.build_model(num_classes=num_classes, freeze_early=freeze_early)
        self.model.load_state_dict(torch.load(path, map_location=self.device, weights_only=True))

    def predict(self, img):
        if isinstance(img, (str, Path)):
            img = Image.open(str(img)).convert("RGB")
        x = val_transforms(img).unsqueeze(0).to(self.device)
        self.model.eval()
        with torch.no_grad():
            out = self.model(x)
            probs = torch.softmax(out, dim=1).cpu().numpy()[0]
            pred = int(probs.argmax())
        return {"pred": pred, "probs": probs}
    
if __name__ == "__main__":
    # quick run example
    image_paths, labels = load_data()
    clf = SmiskiClassifier()
    clf.build_model()
    clf.prepare_data(image_paths, labels)
    clf.train()
    clf.save("smiski_classifier.pt")




    



