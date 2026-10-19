# Model release v1

The two model checkpoints, training metadata, model card, and evaluation reports are published at:

[Smiski models v1](https://github.com/giomhern/is-it-a-smiski/releases/tag/model-v1).

| Asset | Purpose |
| --- | --- |
| `smiski_classifier.pt` | Existing default checkpoint; training partitions unknown |
| `smiski_baseline_v1.pt` | Fresh frozen-ImageNet baseline |
| `smiski_baseline_v1.metadata.json` | Baseline training history, partitions and checksum |
| `MODEL_CARD.md` | Intended use, metrics, reviewed failures and limitations |
| `baseline-v1.json`, `baseline-v1.md` | Baseline test predictions and report |
| `legacy-diagnostic.json`, `legacy-diagnostic.md` | Explicitly diagnostic evaluation of the existing model |

Raw training photos and credentials are not included. Checkpoint files remain ignored by Git. The initial checkpoint's manifest is `backend/models/manifest.json`; the baseline uses `backend/models/baseline-v1.manifest.json`. Both include the verified SHA-256 and the permanent asset URL.

The release is a weights distribution. Clone the repository's current `main` for the deterministic inference and evaluation pipeline described in the model card.

## Verify a fresh download

From the repository root, install to temporary locations so existing local checkpoints cannot mask a broken download:

```sh
uv run --locked python -m scripts.install_model --destination /tmp/smiski-release-check/legacy.pt
uv run --locked python -m scripts.install_model \
  --manifest backend/models/baseline-v1.manifest.json \
  --destination /tmp/smiski-release-check/baseline.pt
MODEL_PATH=/tmp/smiski-release-check/legacy.pt uv run --locked python -m scripts.test_model \
  --image_path tests/smiski/test-smiski.jpeg
```

## Future versions

Create a new release tag, checkpoint manifest, dataset version and evaluation report for a changed model. Do not silently replace published weights or revise v1 labels after examining its test predictions. Record a manually reviewed label policy and evaluate on an independent collection before promoting a replacement default model.
