from ..backend.transfer.main import SmiskiClassifier
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Smiski classifier on an image.")
    parser.add_argument("--image_path", type=str, help="Path to the image ")

    args = parser.parse_args()
    image_path = args.image_path

    clf = SmiskiClassifier()
    clf.build_model()
    clf.load("backend/models/smiski_classifier.pt")
    result = clf.predict(image_path)

    print(f"Prediction: {'Smiski' if result['pred'] == 1 else 'Non-Smiski'}")
    print(f"Confidence: {result['probs'][result['pred']]:.2%}")
    print(f"Probabilities: Smiski={result['probs'][1]:.2%}, Non-Smiski={result['probs'][0]:.2%}")