import argparse

from backend.config import get_model_path
from backend.transfer.main import SmiskiClassifier

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Smiski classifier on an image.")
    parser.add_argument(
        "--image_path", type=str, required=True, help="Path to the image"
    )

    args = parser.parse_args()
    image_path = args.image_path

    clf = SmiskiClassifier()
    clf.load(get_model_path())
    result = clf.predict(image_path)

    print(f"Prediction: {'Smiski' if result['pred'] == 1 else 'Non-Smiski'}")
    print(f"Model score: {result['probs'][result['pred']]:.2%}")
    print(
        f"Scores: Smiski={result['probs'][1]:.2%}, Non-Smiski={result['probs'][0]:.2%}"
    )
