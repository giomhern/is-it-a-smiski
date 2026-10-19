"""CPU inference for the exported ResNet50 checkpoint."""

import numpy as np
import onnxruntime as ort

from backend.helpers.dataset import file_sha256
from backend.helpers.preprocessing import preprocess_image

ort.disable_telemetry_events()


class SmiskiPredictor:
    def __init__(self, checkpoint):
        path = checkpoint.with_suffix(".onnx")
        if not path.is_file():
            raise FileNotFoundError(
                f"Exported model missing: {path}. Run uv run --locked --extra training "
                "python -m scripts.export_model."
            )
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        options.add_session_config_entry("session.disable_prepacking", "1")
        self.session = ort.InferenceSession(
            str(path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        source_hash = self.session.get_modelmeta().custom_metadata_map.get(
            "checkpoint_sha256"
        )
        if source_hash != file_sha256(checkpoint):
            raise ValueError(
                "Export does not match checkpoint; rerun scripts.export_model"
            )

    def predict(self, image):
        pixels = preprocess_image(image)[None]
        logits = self.session.run(["logits"], {"images": pixels})[0][0]
        scores = np.exp(logits - logits.max())
        scores /= scores.sum()
        return {"pred": int(scores.argmax()), "probs": scores}
