# Dataset audit and split v1

The snapshot records relative filenames and content hashes, not image files. Original photos remain in ignored `data/raw/`. The directory name supplies the label: `non_smiski = 0`, `smiski = 1`.

## What was found

The local collection has 1,079 readable photos: 415 positive and 664 negative folder labels. The first audit quarantined 99 photos in duplicate groups containing both labels and removed 7 redundant copies within a class. There are 973 retained photos:

| Partition | Non-Smiski | Smiski | Total | Duplicate groups |
| --- | ---: | ---: | ---: | ---: |
| Training | 431 | 250 | 681 | 680 |
| Validation | 92 | 54 | 146 | 145 |
| Test | 92 | 54 | 146 | 146 |

The manifest label says `smiski` for all 664 photos stored in the negative folder. This is recorded as a warning rather than silently treating the manifest as ground truth. Visual inspection of a small seeded sample also found photos containing large Smiski figures in the negative folder. Quarantining duplicate conflicts removes some contradictory examples but does not fix every label.

For retained photos, 601 manifest records say All Rights Reserved, 368 have unknown licensing/provenance, and 4 list other licenses. The positive manifest is empty. This repository does not redistribute the images; this inventory does not establish permission to redistribute or otherwise use them.

## Reproducibility and leakage controls

`split-v1.json` includes a SHA-256 fingerprint over its contents, the seed, ratios, preprocessing-independent content hashes, exclusions, warnings, and group IDs. Loaders verify both the fingerprint and each image's current bytes before training or evaluation. Existing snapshots/reports are not overwritten by their CLI commands.

Groups join images transitively when they share exact bytes, decoded RGB pixels after EXIF correction, a source-photo page, or a 128-bit horizontal difference hash within Hamming distance 6. Cross-label groups are quarantined. Exact decoded-pixel duplicates within a class keep one representative. Whole remaining groups are assigned per class toward 70/15/15 ratios using seed 42.

This is a conservative heuristic, not a guarantee that all related photos are detected. Different crops, shooting sessions, angles, people, and backgrounds can cross partitions. Source/photographer metadata is incomplete, particularly for positives. Broader source grouping and an independent external collection are still needed before making strong generalization claims.

## Reproduce and review

```sh
# Use a new filename; the original snapshot stays unchanged.
uv run --locked python -m scripts.prepare_dataset --output /tmp/smiski-split-reproduction.json
```

With the same image bytes and metadata, the snapshot fingerprint and assignments match v1. File modification timestamps and the machine's absolute dataset path do not affect the result.

Review the `excluded` entries with reason `cross_label_duplicate_group` and the report's highest-score mistakes locally. Correct labels only after inspecting the original photo and recording the decision. The rest of the collection also needs review, including packaging, statues, drawings, multiple objects, and unrelated street photos, to define precisely what counts as a positive.

After correcting labels, create a new versioned snapshot. Do not keep tuning on the v1 test results: reserve a new independently collected test set for the next model's final evaluation. Add challenging negatives deliberately (Sonny Angels, similar green figurines, and other toys), rather than relying on search queries as labels.
