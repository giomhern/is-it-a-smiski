"""Export the installed checkpoint for the memory-constrained CPU API."""

import argparse
import os
import tempfile
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch

from backend.config import get_model_path
from backend.helpers.dataset import file_sha256
from backend.transfer.main import SmiskiClassifier


def export_model(checkpoint):
    checkpoint = Path(checkpoint)
    destination = checkpoint.with_suffix(".onnx")
    source_hash = file_sha256(checkpoint)
    if destination.exists():
        model = onnx.load(destination)
        if {p.key: p.value for p in model.metadata_props}.get(
            "checkpoint_sha256"
        ) == source_hash:
            return destination
    classifier = SmiskiClassifier(device=torch.device("cpu"))
    classifier.load(checkpoint)
    torch.set_num_threads(1)
    example = torch.linspace(-1, 1, 3 * 224 * 224).reshape(1, 3, 224, 224)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, suffix=".onnx", delete=False
        ) as output:
            temporary = Path(output.name)
        program = torch.onnx.export(
            classifier.model,
            (example,),
            input_names=["images"],
            output_names=["logits"],
        )
        program.save(temporary, external_data=False)
        model = onnx.load(temporary)
        onnx.helper.set_model_props(model, {"checkpoint_sha256": source_hash})
        onnx.checker.check_model(model)
        onnx.save(model, temporary)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        session = ort.InferenceSession(
            str(temporary), sess_options=options, providers=["CPUExecutionProvider"]
        )
        with torch.inference_mode():
            expected = classifier.model(example).numpy()
        actual = session.run(["logits"], {"images": example.numpy()})[0]
        np.testing.assert_allclose(actual, expected, rtol=1e-4, atol=1e-4)
        os.replace(temporary, destination)
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=get_model_path())
    args = parser.parse_args()
    print(f"Exported model ready: {export_model(args.checkpoint)}")


if __name__ == "__main__":
    main()
