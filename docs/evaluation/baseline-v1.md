# Frozen ImageNet baseline v1 — test evaluation

Evaluation status: **held_out_for_this_training_run**.

Checkpoint SHA-256: `6f7ea679e5e2827dabd0baed09345b397096e572a667653d8a78c35e4ec0068e`
Dataset fingerprint: `45d171ff988cf7f39b0781bff907a1eeb76d3fe2bac1d85af7dcc43096d36c5d`

Partition: `test`; photos: 146; duplicate groups: 146.

- Labels come from collection folders, not a complete manual review; some negatives visibly contain Smiskis.
- Duplicate grouping covers exact pixels, source-photo IDs, and nearby dHashes; crops, viewpoints and shooting sessions can still leak.
- Metrics are per image, not per independent scene; a small, source-biased dataset cannot establish real-world accuracy.
- Softmax scores are uncalibrated. No uncertainty threshold has been selected.

## Metrics

Accuracy: 94.521%; macro F1: 0.9397; balanced accuracy: 92.975%.

Brier score: 0.0418 (lower is better; this alone does not establish calibration).

| Class | Precision | Recall | F1 | Support |
| --- | ---: | ---: | ---: | ---: |
| Non-Smiski | 0.9286 | 0.9891 | 0.9579 | 92 |
| Smiski | 0.9792 | 0.8704 | 0.9216 | 54 |

## Confusion matrix

Rows are folder labels; columns are predictions.

| Actual / predicted | Non-Smiski | Smiski |
| --- | ---: | ---: |
| Non-Smiski | 91 | 1 |
| Smiski | 7 | 47 |

## Highest-score mistakes

Review these before changing labels: some folder labels may be wrong. Scores are uncalibrated.

| Image (relative to dataset root) | Folder label | Prediction | Score | Source |
| --- | --- | --- | ---: | --- |
| `non_smiski/sonny-angel-1759260679063-9296.jpg` | Non-Smiski | Smiski | 99.987% | [source](https://www.flickr.com/photos/66402693@N00/53423138139) |
| `smiski/smiski-1759088959159-5895.jpg` | Smiski | Non-Smiski | 97.516% | unknown |
| `smiski/smiski-1759088999066-5152.jpg` | Smiski | Non-Smiski | 91.505% | unknown |
| `smiski/smiski-1759089001754-5745.jpg` | Smiski | Non-Smiski | 82.939% | unknown |
| `smiski/smiski-1759088956342-9221.jpg` | Smiski | Non-Smiski | 64.816% | unknown |
| `smiski/smiski-1759089001386-5477.jpg` | Smiski | Non-Smiski | 62.070% | unknown |
| `smiski/smiski-1759088953558-4744.jpg` | Smiski | Non-Smiski | 54.547% | unknown |
| `smiski/smiski-1759089000348-9166.jpg` | Smiski | Non-Smiski | 54.533% | unknown |
