# Smiski classifier model card

## Intended use

A collector's photo-classification demo: detect whether a photo contains a Smiski character. This is not an authenticity checker, series identifier, object detector, or a guarantee that a physical product is genuine. Training labels cover mixed scenes, statues, packaging and figures inconsistently; the positive-label policy needs a full review before expanding the product's claims.

Both checkpoints use torchvision ResNet50 with a two-output linear head. Labels are `0 = Non-Smiski`, `1 = Smiski`. Serving applies EXIF orientation correction, converts to RGB, resizes to 224×224, and normalizes with ImageNet mean/std. Validation and serving contain no random augmentation. The default decision is the larger of the two logits; softmax scores are uncalibrated.

## Checkpoints

| Artifact | Role | SHA-256 |
| --- | --- | --- |
| `smiski_classifier.pt` | Existing demo checkpoint; default API model | `3c9f5bd691a3b66b139dcde2518d8a09c65a74a7deb664cc355f0eaca22db376` |
| `smiski_baseline_v1.pt` | Newly trained baseline with recorded split provenance | `6f7ea679e5e2827dabd0baed09345b397096e572a667653d8a78c35e4ec0068e` |

The existing checkpoint has no reliable record of its original training partitions, seed, or selected epoch. It may have seen any photo in the current collection. Its [diagnostic report](evaluation/legacy-diagnostic.md) must not be presented as held-out accuracy or compared directly against the new baseline's test score.

The new baseline starts from `ResNet50_Weights.IMAGENET1K_V2`, freezes the entire backbone, and trains a class-balanced linear classifier on deterministic cached features. It does not initialize from the existing Smiski checkpoint. Training uses seed 42, 100 epochs, Adam with learning rate 0.001, and head batches of 32. Epoch 44 is selected by lowest unweighted validation cross-entropy, before evaluating test images. The complete training history, image hashes, software version, and checkpoint binding are in [`smiski_baseline_v1.metadata.json`](../backend/models/smiski_baseline_v1.metadata.json).

## Dataset and evaluation

[Dataset audit and reproducibility details](dataset/README.md). Snapshot v1 retains 973 of 1,079 local photos after duplicate/conflict handling: 681 train, 146 validation, 146 test. These are folder labels, not fully verified annotations. All 664 negative-folder manifest records are labeled `smiski` in the source metadata, and visual inspection found negative-folder photos containing Smiskis. Positive provenance is missing. Related scenes may remain across splits despite duplicate grouping.

The fresh baseline's [test report](evaluation/baseline-v1.md) contains per-image predictions, precision/recall/F1, a confusion matrix, and failure paths. The 146 test photos were not used for its feature extraction, fitting, or epoch selection. This establishes separation for that training run, not independence from all related scenes or accuracy in the real world.

| Metric | Fresh baseline, folder-labeled test partition |
| --- | ---: |
| Accuracy | 94.52% |
| Macro F1 | 0.9397 |
| Smiski precision | 0.9792 |
| Smiski recall | 0.8704 |
| Smiski F1 | 0.9216 |
| Brier score | 0.0418 |

Confusion matrix, rows actual folder labels and columns predictions:

| Actual / predicted | Non-Smiski | Smiski |
| --- | ---: | ---: |
| Non-Smiski | 91 | 1 |
| Smiski | 7 | 47 |

A 146-image, imperfectly labeled test set is preliminary evidence. No independent external evaluation or calibration study has been completed. Do not advertise the percentage above as production accuracy.

## Reviewed failures

Inspection of the eight baseline disagreements found:

- The highest-score apparent false positive shows people beside a large Smiski statue. The model's result is consistent with Smiski presence; the negative folder label is questionable. It remains unchanged in v1 so the published evaluation is not revised after seeing test predictions.
- Missed positives include small or partly occluded figures, a blue figure, a figure on a pumpkin, strong color casts, and cluttered promotional/retail scenes.
- Resizing the entire scene to 224×224 can erase a small subject. This classifier cannot tell a user which object it considered.
- An additional smoke check on the repository's two demo photos classified the Smiski photo correctly, but called `tests/non-smiski/test-sonny-angel.jpg` a Smiski with a 67.27% score. These two examples are not a benchmark and were not used to select the baseline. This known hard-negative failure is another reason to review data and evaluate new examples before promoting the baseline to the default API model.

The report lists exact image paths and available source links for review. No source photos are embedded in the repository's reports.

Reproduce the hard-negative check with `MODEL_PATH=backend/models/smiski_baseline_v1.pt uv run --locked python -m scripts.test_model --image_path tests/non-smiski/test-sonny-angel.jpg`.

## Limitations and next experiment

The collection is source-biased and includes ambiguous or incorrect labels. Exact and perceptual duplicate checks cannot prove that all alternate views, crops, people or backgrounds are isolated. Search queries are not ground truth. The existing checkpoint's unknown training history also prevents honest comparison between the two models.

First review labels and define whether statues, drawings, packaging and mixed scenes should count. Collect independently photographed positives and challenging negatives (Sonny Angels, green figurines, other toys). Create a new versioned dataset after corrections and keep an external final test set untouched while selecting the next model. Do not tune on v1 test mistakes and then continue calling the same partition unseen.

Do not use a softmax score as a calibrated probability. An “unsure” response should only be introduced after selecting an abstention threshold using validation data and reporting the resulting coverage and error rate on new test data.

## Distribution

Model manifests bind the downloadable weights to their checksums. Only checkpoint weights, metadata and documentation are intended for a model release; raw training photos and credentials stay out of Git and release assets. Dataset permissions and source attribution are incomplete, as recorded in the audit. Public release availability is tracked in the README and model manifests.
