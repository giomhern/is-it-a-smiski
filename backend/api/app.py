import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from PIL import Image

from backend.config import get_model_path
from backend.helpers.uploads import webp_pixels
from backend.inference import SmiskiPredictor

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_WEBP_PIXELS = 16_000_000
MAX_IMAGE_DIMENSION = 16_384
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

clf = SmiskiPredictor(get_model_path())


@app.route("/api/predict", methods=["POST"])
def predict():
    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400
    if len(request.files.getlist("image")) != 1:
        return jsonify({"error": "Please upload one photo at a time"}), 400
    file = request.files["image"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400
    try:
        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(0)
        if size > MAX_IMAGE_BYTES:
            return jsonify({"error": "Choose a photo under 10 MB"}), 413
        pixels = webp_pixels(file.stream, size)
        if pixels is not None and pixels > MAX_WEBP_PIXELS:
            return jsonify({"error": "Choose a WebP photo under 16 megapixels"}), 400
        with Image.open(file.stream) as image:
            if image.format not in ALLOWED_FORMATS:
                return jsonify({"error": "Choose a JPG, PNG, or WebP photo"}), 400
            if max(image.size) > MAX_IMAGE_DIMENSION:
                return jsonify(
                    {"error": "Choose a photo under 16,384 pixels per side"}
                ), 400
            if image.width * image.height > MAX_IMAGE_PIXELS:
                return jsonify({"error": "Choose a photo under 40 megapixels"}), 400
            if image.format == "WEBP" and image.width * image.height > MAX_WEBP_PIXELS:
                return jsonify(
                    {"error": "Choose a WebP photo under 16 megapixels"}
                ), 400
            image.load()
            try:
                result = clf.predict(image)
            except Exception:
                app.logger.exception("Prediction failed")
                return jsonify({"error": "Unable to classify this image"}), 500
    except (OSError, ValueError, Image.DecompressionBombError):
        return jsonify({"error": "Please upload a valid image"}), 400

    return jsonify(
        {
            "prediction": "Smiski" if result["pred"] == 1 else "Non-Smiski",
            "confidence": float(result["probs"][result["pred"]]),
            "probabilities": {
                "smiski": float(result["probs"][1]),
                "non_smiski": float(result["probs"][0]),
            },
        }
    )


@app.errorhandler(413)
def upload_too_large(error):
    return jsonify({"error": "Upload exceeds the 16 MB request limit"}), 413


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5050")))
