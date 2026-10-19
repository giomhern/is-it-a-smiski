import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from PIL import Image, UnidentifiedImageError

from backend.config import get_model_path
from backend.transfer.main import SmiskiClassifier

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

clf = SmiskiClassifier()
clf.load(get_model_path())


@app.route("/api/predict", methods=["POST"])
def predict():
    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400
    file = request.files["image"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400
    try:
        # Decode directly from the request: no shared temporary filenames or cleanup.
        with Image.open(file.stream) as image:
            result = clf.predict(image.convert("RGB"))
        return jsonify({
            "prediction": "Smiski" if result["pred"] == 1 else "Non-Smiski",
            "confidence": float(result["probs"][result["pred"]]),
            "probabilities": {
                "smiski": float(result["probs"][1]),
                "non_smiski": float(result["probs"][0]),
            },
        })
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return jsonify({"error": "Please upload a valid image"}), 400
    except Exception:
        app.logger.exception("Prediction failed")
        return jsonify({"error": "Unable to classify this image"}), 500


@app.errorhandler(413)
def upload_too_large(error):
    return jsonify({"error": "Upload exceeds the 16 MB request limit"}), 413


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5050")))
