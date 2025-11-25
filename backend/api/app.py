import json
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import torch
from flask_cors import CORS, cross_origin
from pathlib import Path
import os
from backend.transfer.main import SmiskiClassifier 

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000"]}}, supports_credentials=True)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = '/tmp'

clf = SmiskiClassifier()
clf.build_model()
clf.load("backend/models/smiski_classifier.pt")

@app.route('/api/predict', methods=['POST'])
@cross_origin(origin="http://localhost:3000")
def predict():
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image provided"}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        result = clf.predict(filepath)
        os.remove(filepath)
        
        return jsonify({
            "prediction": "Smiski" if result['pred'] == 1 else "Non-Smiski", 
            "confidence": float(result['probs'][result['pred']]), 
            "probabilities": {
                "smiski": float(result['probs'][1]), 
                "non_smiski": float(result['probs'][0])
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200 



if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5050)