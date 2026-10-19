# Is It a Smiski?

A small machine learning web app by a Smiski collector. Upload a photo to get a **Smiski / Non-Smiski** prediction from a fine-tuned ResNet50 model.

[Meet Smiski](https://smiski.com/e/smiski/). This is an independent fan project, unaffiliated with the brand.

![The simple Smiski photo upload screen](docs/screenshots/app.jpg)

Coding, design, verification, and commit standards are in [AGENTS.md](AGENTS.md). The [code audit](docs/CODE_AUDIT.md) records cleanup, verification, and remaining work.

## Architecture

- **Frontend:** Next.js 15, React 19, and a small CSS stylesheet.
- **API:** Flask, served with Gunicorn in production.
- **Model:** PyTorch / torchvision ResNet50, two classes (`0 = Non-Smiski`, `1 = Smiski`).
- **Uploads:** decoded in memory for prediction; the API does not save uploaded photos.
- **Training data and checkpoint:** kept outside Git. Flickr credentials are only needed for dataset collection.

```text
backend/
  api/app.py             Flask API
  config.py              Repository-relative paths and environment
  helpers/dataset.py     Audited snapshots and duplicate-aware splits
  models/manifest.json   Checkpoint identity and SHA-256
  transfer/main.py       Classifier and shared image preprocessing
frontend/                Next.js app
scripts/
  install_model.py       Verified checkpoint installation
  test_model.py          Single-photo prediction CLI
  download_images.py     Optional Flickr dataset downloader
  prepare_dataset.py     Dataset audit and immutable split creation
  train_model.py         Reproducible frozen-ImageNet baseline
  evaluate_model.py      Metrics, confusion matrix and failure reports
tests/                   Sample photos and setup/API smoke tests
pyproject.toml           Python dependencies (Python 3.11)
uv.lock                  Full Python dependency lock
```

## Model reliability

Serving and validation now use deterministic preprocessing: EXIF orientation correction, RGB, resize to 224×224, and ImageNet normalization. Repeated uploads of the same image return the same scores on the tested CPU environment.

A [dataset audit](docs/dataset/README.md) quarantined 99 cross-label duplicate-group photos and removed 7 exact duplicate copies. The remaining 973 photos are split 681/146/146 into training, validation and test partitions with versioned content hashes and duplicate grouping.

A freshly trained frozen-ImageNet baseline scored **94.52% accuracy, 0.9397 macro F1, and 87.04% Smiski recall** on 146 reserved test photos. These are preliminary results against imperfect folder labels, not a real-world accuracy claim. The existing default checkpoint's training history is unknown, so its evaluation is explicitly diagnostic. See the [model card](docs/MODEL_CARD.md), [baseline test report](docs/evaluation/baseline-v1.md), and [legacy diagnostic](docs/evaluation/legacy-diagnostic.md).

The baseline is a separate checkpoint; the API's default remains the existing demo model. The baseline also misclassified the included Sonny Angel demo photo, a useful hard-negative failure recorded in the model card. Both checkpoints use uncalibrated softmax scores. Label review and an independently collected external test set are the next modeling work.

## Local setup

Prerequisites: **Python 3.11**, **Node.js 22**, npm, and [uv](https://docs.astral.sh/uv/getting-started/installation/). Run commands from the repository root unless a command changes directory. With nvm installed, `nvm install` selects the version in `.nvmrc`.

### 1. Install Python dependencies

```sh
uv sync --locked
cp .env.example .env
```

Keep an existing `.env` if you already have one. Real environment variables take precedence over `.env`. Dataset collection dependencies are optional: `uv sync --locked --extra training`.

### 2. Install the checkpoint

Both checkpoints are available from the [model-v1 release](https://github.com/giomhern/is-it-a-smiski/releases/tag/model-v1). Install the default checkpoint (or verify an existing copy):

```sh
uv run --locked python -m scripts.install_model
```

To install a copy you already have elsewhere:

```sh
uv run --locked python -m scripts.install_model --source /path/to/smiski_classifier.pt
```

For a hosted copy, set `MODEL_URL` in `.env` or pass an HTTPS URL to `--source`. The installer verifies the SHA-256 in `backend/models/manifest.json`, uses an atomic replacement, and leaves the existing file intact if validation fails. An already verified checkpoint requires no network access. Model loading does not download ImageNet weights.

The manifests contain permanent release download URLs and checksums. The [release record](docs/model-release.md) lists the assets and verification workflow. Retraining produces a different checkpoint and requires a new manifest hash before distribution.

### 3. Run the API

```sh
uv run --locked python -m backend.api.app
```

The API runs at `http://localhost:5050`. `GET /health` returns `{"status":"ok"}` after the checkpoint has loaded. Missing checkpoints fail startup with setup instructions.

### 4. Run the frontend in another terminal

```sh
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Keep an existing `.env.local` if already configured. Open `http://localhost:3000`. The frontend example points `NEXT_PUBLIC_API_URL` at `http://localhost:5050`; restart Next.js after changing it. This variable is public and must never contain secrets. If development hits a file-watcher limit, start with `WATCHPACK_POLLING=true npm run dev`.

### 5. Try a prediction

From the repository root:

```sh
curl -f http://localhost:5050/health
curl -f -F image=@tests/smiski/test-smiski.jpeg http://localhost:5050/api/predict
uv run --locked python -m scripts.test_model --image_path tests/smiski/test-smiski.jpeg
```

`POST /api/predict` expects one multipart image named `image`: JPG, PNG, or WebP, up to 10 MB and 40 megapixels. These limits are enforced by the API. It returns:

```json
{
  "prediction": "Smiski",
  "confidence": 0.87,
  "probabilities": { "smiski": 0.87, "non_smiski": 0.13 }
}
```

Values above illustrate the response schema, not an accuracy claim. These are uncalibrated model scores. Inference has no random augmentation; exact repeatability is verified for repeated uploads on the tested CPU environment.

## Checks

```sh
# Requires the checkpoint for real API inference tests.
uv run --locked python -m unittest discover -s tests/unit -v

cd frontend
npm run lint
npm run typecheck
npm test
npm run build
npm start
```

The backend smoke tests exercise both sample images, invalid uploads, checkpoint integrity failures, portable data paths, and startup without an ImageNet download. They verify the inference workflow, not held-out model accuracy. Frontend regression tests cover file validation, response validation, service failures, cancellation, and timeouts.

Dependency maintenance: Next.js is updated within version 15, and the PostCSS override selects a patched version compatible with its existing major version. As of this setup check, `npm audit` still reports five high-severity entries in the development-only ESLint dependency chain, all stemming from the [braces advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm). The current braces release has no patched version. Recheck dependency advisories before public deployment.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `MODEL_PATH` | `backend/models/smiski_classifier.pt` | Absolute or repository-relative checkpoint path |
| `MODEL_URL` | unset | Trusted checkpoint source for the installer |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | Comma-separated frontend origins allowed by API CORS |
| `PORT` | `5050` | Port for the local Python API entry point |
| `DATA_DIR` | `data/raw` | Absolute or repository-relative training dataset root |
| `FLICKR_API_KEY` | unset | Only required for optional Flickr collection |
| `NEXT_PUBLIC_API_URL` | see frontend example | API origin compiled into the frontend |

## Production commands

The hosting service needs Python 3.11, the installed checkpoint, and the locked dependencies. Set `ALLOWED_ORIGINS` to your deployed frontend origin. Bind Gunicorn to the port supplied by your host:

```sh
uv run --locked gunicorn --bind "0.0.0.0:${PORT:-5050}" --workers 1 --timeout 120 backend.api.app:app
```

Set the frontend's `NEXT_PUBLIC_API_URL` before `npm run build`, then run `npm start`. The checkpoint loads once per worker; start with one worker and measure memory and latency before scaling. Public hosting, resource sizing, rate limits, and deployment automation are subsequent work.

## Reproduce training and evaluation

The image collection stays outside Git; these commands require a local copy under `data/raw/` or `DATA_DIR`. The committed snapshot verifies the original bytes and fails if images have changed. Do not present a new checkpoint's test score as an independent result if you selected its settings after reviewing the existing v1 test results.

```sh
# Train only on the snapshot's training partition. Select the head using validation loss.
# Use a separate directory so the recorded baseline stays intact.
uv run --locked python -m scripts.train_model \
  --output /tmp/smiski-reproduction/smiski_baseline_v1.pt

# Evaluate once after selection; the metadata binds the checkpoint to its partitions.
uv run --locked python -m scripts.evaluate_model \
  --checkpoint /tmp/smiski-reproduction/smiski_baseline_v1.pt \
  --output /tmp/smiski-reproduction/baseline-test.json \
  --title "Reproduced frozen ImageNet baseline"

# The older checkpoint has unknown training provenance: always diagnostic-only.
uv run --locked python -m scripts.evaluate_model \
  --output /tmp/smiski-reproduction/legacy-diagnostic.json
```

Training starts from torchvision's ImageNet V2 weights (downloaded on first use), freezes the backbone and trains a class-balanced linear head. It does not read test images for feature extraction or fitting. The script records hyperparameters, selected epoch, validation history, partition hashes and checkpoint SHA-256 in a `.metadata.json` sidecar. It never overwrites an existing checkpoint or metadata file. CPU threads, seeds and deterministic algorithms are configured explicitly; byte-for-byte reproducibility across different PyTorch builds/hardware is not promised.

For a changed or corrected dataset, create a new immutable snapshot rather than rewriting v1:

```sh
uv run --locked python -m scripts.prepare_dataset --output docs/dataset/split-v2.json
```

Both model scripts accept `--snapshot` and `--data-dir`. Evaluation refuses mismatched training metadata and identifies an unknown training history as diagnostic-only. Reports include per-class precision/recall/F1, accuracy, balanced accuracy, Brier score, confusion counts and mistake paths. Reports are not overwritten; use a new output name for each run.

The baseline has its own installer manifest:

```sh
uv run --locked python -m scripts.install_model \
  --manifest backend/models/baseline-v1.manifest.json
```

An alternative manifest installs to its declared filename under `backend/models/`, without replacing the default checkpoint. `--destination` overrides that path. `MODEL_URL` only overrides the default manifest. To serve the baseline, set `MODEL_PATH=backend/models/smiski_baseline_v1.pt` and restart the API.

## Optional dataset collection

```sh
uv sync --locked --extra training
```

Provide images under `data/raw/smiski/` and `data/raw/non_smiski/`, or set `DATA_DIR`. Snapshots inventory supported images in the two class directories, audit manifest metadata and group duplicates. Review the folder labels before treating them as ground truth.

Dataset collection accepts an explicit API key from the shell (the downloader does not load `.env` itself):

```sh
FLICKR_API_KEY=your-key uv run --locked --extra training python -m scripts.download_images \
  --queries smiski --out data/raw/smiski --label smiski --license-filter cc
```

Review source permissions and attribution before distributing collected photos. Dataset evaluation and documentation will be expanded separately.

### Conda alternative

From the repository root, `conda env create -f environment.yml` installs Python 3.11 and the same declared dependencies with training extras. Activate with `conda activate my-smiski`, then use `python` in place of `uv run --locked python`. Conda/pip resolves transitive dependencies independently; use the uv workflow above for the committed full lock.
