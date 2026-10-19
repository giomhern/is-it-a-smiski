Two ResNet50 checkpoints for the independent Is It a Smiski? collector demo. Neither is an authenticity checker or series identifier.

- `smiski_classifier.pt`: existing default model. SHA-256 `3c9f5bd691a3b66b139dcde2518d8a09c65a74a7deb664cc355f0eaca22db376`. Original training partitions are unknown; its scores are diagnostic, not held-out generalization results.
- `smiski_baseline_v1.pt`: fresh frozen-ImageNet baseline. SHA-256 `6f7ea679e5e2827dabd0baed09345b397096e572a667653d8a78c35e4ec0068e`. Training provenance is attached as `smiski_baseline_v1.metadata.json`. On 146 folder-labeled test photos: accuracy 94.52%, macro F1 0.9397, Smiski recall 87.04%.
- Both use label 0 = Non-Smiski, label 1 = Smiski. Inference is EXIF-corrected RGB, resized to 224×224, normalized with ImageNet mean/std, with no random augmentation.
- Scores are uncalibrated. The collection has label errors and incomplete provenance; related scenes may cross partitions. The test percentage is preliminary, not a production accuracy claim. See the attached model card and reports.

No training photos or credentials are included. Verify checkpoint SHA-256 before loading. The repository's installer accepts the corresponding model manifest.
