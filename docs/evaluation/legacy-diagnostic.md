# Initial checkpoint diagnostic

Evaluation status: **diagnostic_only_training_provenance_unknown**.

Checkpoint SHA-256: `3c9f5bd691a3b66b139dcde2518d8a09c65a74a7deb664cc355f0eaca22db376`
Dataset fingerprint: `45d171ff988cf7f39b0781bff907a1eeb76d3fe2bac1d85af7dcc43096d36c5d`

Partition: `test`; photos: 146; duplicate groups: 146.

- The initial checkpoint predates this split and may have seen these photos. These numbers are NOT held-out generalization results.
- Labels come from collection folders, not a complete manual review; some negatives visibly contain Smiskis.
- Duplicate grouping covers exact pixels, source-photo IDs, and nearby dHashes; crops, viewpoints and shooting sessions can still leak.
- Metrics are per image, not per independent scene; a small, source-biased dataset cannot establish real-world accuracy.
- Softmax scores are uncalibrated. No uncertainty threshold has been selected.

## Metrics

Accuracy: 98.630%; macro F1: 0.9853; balanced accuracy: 98.531%.

Brier score: 0.0207 (lower is better; this alone does not establish calibration).

| Class | Precision | Recall | F1 | Support |
| --- | ---: | ---: | ---: | ---: |
| Non-Smiski | 0.9891 | 0.9891 | 0.9891 | 92 |
| Smiski | 0.9815 | 0.9815 | 0.9815 | 54 |

## Confusion matrix

Rows are folder labels; columns are predictions.

| Actual / predicted | Non-Smiski | Smiski |
| --- | ---: | ---: |
| Non-Smiski | 91 | 1 |
| Smiski | 1 | 53 |

## Highest-score mistakes

Review these before changing labels: some folder labels may be wrong. Scores are uncalibrated.

| Image (relative to dataset root) | Folder label | Prediction | Score | Source |
| --- | --- | --- | ---: | --- |
| `non_smiski/sonny-angel-1759260679063-9296.jpg` | Non-Smiski | Smiski | 90.275% | [source](https://www.flickr.com/photos/66402693@N00/53423138139) |
| `smiski/smiski-1759088999801-5555.jpg` | Smiski | Non-Smiski | 69.293% | unknown |
