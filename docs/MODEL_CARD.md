# Model card

A photo-classification demo, not an authenticity checker. Both checkpoints use ResNet50 with labels `0 = Non-Smiski`, `1 = Smiski`. Preprocessing corrects EXIF orientation, converts to RGB, resizes to 224×224, and applies ImageNet normalization. Scores are uncalibrated. The CPU API serves an ONNX export of the same weights; PyTorch is used for training and historical evaluation.

- **Default model:** original checkpoint with unknown training history. Its evaluation cannot establish held-out accuracy.
- **Baseline v1:** frozen ImageNet V2 backbone, class-balanced linear head, seed 42; epoch 44 selected from 100 by validation loss. The duplicate-grouped dataset contains 681 training, 146 validation, and 146 test photos.
- **Baseline test results:** 94.52% accuracy, 0.9397 macro F1, 87.04% Smiski recall. Confusion counts (actual rows / predicted columns, Non-Smiski first): `[[91, 1], [7, 47]]`.
- **Limits:** imperfect folder labels, incomplete source permissions, source bias, and possible related scenes across splits. Small/occluded figures and cluttered scenes cause misses. The baseline calls the included Sonny Angel photo a Smiski (67.27% score), so it remains separate from the default model.
- **Next model work:** review labels and evaluate independently collected photos. Keep historical test results unchanged; do not tune on v1 mistakes and call that test set unseen.

[Release assets](https://github.com/giomhern/is-it-a-smiski/releases/tag/model-v1) archive weights, complete reports, and baseline training metadata. Checkpoint checksums remain in [the model manifests](../backend/models). Raw training photos are not distributed. [Setup and reproduction commands](../README.md).
