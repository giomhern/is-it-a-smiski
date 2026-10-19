# Publish the initial checkpoint

The checkpoint already exists locally at `backend/models/smiski_classifier.pt` (about 90 MB). It is intentionally ignored by Git. Its SHA-256 is recorded in `backend/models/manifest.json`.

Before publishing, verify the file from the repository root:

```sh
uv run --locked python -m scripts.install_model
shasum -a 256 backend/models/smiski_classifier.pt
```

Create a GitHub Release named `model-v1` in `giomhern/my-smiski` and attach this verified file as `smiski_classifier.pt`. The release description should identify it as the initial two-class ResNet50 checkpoint, with labels `0 = Non-Smiski` and `1 = Smiski`, and include the manifest checksum. Only the checkpoint is needed; do not attach `.env` or the training dataset.

Once the asset is published, set `url` in `backend/models/manifest.json` to:

```text
https://github.com/giomhern/my-smiski/releases/download/model-v1/smiski_classifier.pt
```

This is the intended asset URL, not a currently available download. Do not configure it until the release exists.

Verify installation into a temporary location so the local checkpoint cannot mask a broken download:

```sh
MODEL_PATH=/tmp/smiski-release-check/model.pt uv run --locked python -m scripts.install_model
MODEL_PATH=/tmp/smiski-release-check/model.pt uv run --locked python -m scripts.test_model \
  --image_path tests/smiski/test-smiski.jpeg
```

Commit the updated manifest and README availability note after verification. Future checkpoints should get a new release, checksum, and manifest version rather than replacing a published asset silently.
