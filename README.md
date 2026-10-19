# Is It a Smiski?

A small machine learning web app by a Smiski collector. Upload a photo to get a **Smiski / Non-Smiski** prediction from a fine-tuned ResNet50 model.

[Meet Smiski](https://smiski.com/e/smiski/). This is an independent fan project, unaffiliated with the brand.

## Architecture

- **Frontend:** Next.js 15, React 19, Tailwind CSS 4, Motion.
- **API:** Flask, served with Gunicorn in production.
- **Model:** PyTorch / torchvision ResNet50, two classes (`0 = Non-Smiski`, `1 = Smiski`).
- **Uploads:** decoded in memory for prediction; the API does not save uploaded photos.
- **Training data and checkpoint:** kept outside Git. Flickr credentials are only needed for dataset collection.

```text
backend/
  api/app.py             Flask API
  config.py              Repository-relative paths and environment
  helpers/load_data.py   Dataset manifest loader
  models/manifest.json   Checkpoint identity and SHA-256
  transfer/main.py       Classifier and training entry point
frontend/                Next.js app
scripts/
  install_model.py       Verified checkpoint installation
  test_model.py          Single-photo prediction CLI
  download_images.py     Optional Flickr dataset downloader
tests/                   Sample photos and setup/API smoke tests
pyproject.toml           Python dependencies (Python 3.11)
uv.lock                  Full Python dependency lock
```

## Local setup

Prerequisites: **Python 3.11**, **Node.js 22**, npm, and [uv](https://docs.astral.sh/uv/getting-started/installation/). Run commands from the repository root unless a command changes directory. With nvm installed, `nvm install` selects the version in `.nvmrc`.

### 1. Install Python dependencies

```sh
uv sync --locked
cp .env.example .env
```

Keep an existing `.env` if you already have one. Real environment variables take precedence over `.env`. The training dependencies are optional: `uv sync --locked --extra training`.

### 2. Install the checkpoint

**The initial checkpoint is not publicly hosted yet.** A fresh clone needs a copy from the maintainer or a trusted URL hosting those exact bytes. The model manifest deliberately has no placeholder download URL.

If you already have `backend/models/smiski_classifier.pt`, verify it:

```sh
uv run --locked python -m scripts.install_model
```

Otherwise, install a copy supplied by the maintainer:

```sh
uv run --locked python -m scripts.install_model --source /path/to/smiski_classifier.pt
```

For a hosted copy, set `MODEL_URL` in `.env` or pass an HTTPS URL to `--source`. The installer verifies the SHA-256 in `backend/models/manifest.json`, uses an atomic replacement, and leaves the existing file intact if validation fails. An already verified checkpoint requires no network access. Model loading does not download ImageNet weights.

To make the fresh-clone workflow self-contained, the maintainer should upload the existing checkpoint as a GitHub Release asset, then set its permanent download URL in the manifest. See [checkpoint release instructions](docs/model-release.md). Retraining produces a different checkpoint and requires updating the manifest hash before distribution.

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

Keep an existing `.env.local` if already configured. Open `http://localhost:3000`. The frontend example points `NEXT_PUBLIC_API_URL` at `http://localhost:5050`; restart Next.js after changing it. This variable is public and must never contain secrets.

### 5. Try a prediction

From the repository root:

```sh
curl -f http://localhost:5050/health
curl -f -F image=@tests/smiski/test-smiski.jpeg http://localhost:5050/api/predict
uv run --locked python -m scripts.test_model --image_path tests/smiski/test-smiski.jpeg
```

`POST /api/predict` expects multipart form data named `image` and returns:

```json
{
  "prediction": "Smiski",
  "confidence": 0.87,
  "probabilities": { "smiski": 0.87, "non_smiski": 0.13 }
}
```

Values above illustrate the response schema, not an accuracy claim. These are model scores. Evaluation and calibration are still pending; the current validation/inference transform also includes random augmentation, so scores can vary between requests.

## Checks

```sh
# Requires the checkpoint for real API inference tests.
uv run --locked python -m unittest discover -s tests/unit -v

cd frontend
npm run lint
npm run typecheck
npm run build
npm start
```

The backend smoke tests exercise both sample images, invalid uploads, checkpoint integrity failures, portable data paths, and startup without an ImageNet download. They verify the inference workflow, not held-out model accuracy. The frontend uses Google Fonts at build time, so the build needs network access to Google's font servers.

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

## Optional training

```sh
uv sync --locked --extra training
uv run --locked --extra training python -m backend.transfer.main
```

Provide images under `data/raw/smiski/` and `data/raw/non_smiski/`, or set `DATA_DIR`. Each class can contain images directly or a `download_manifest.jsonl`. Moved manifests can resolve images by basename within the class directory. Training downloads ImageNet initialization weights on its first run and saves the checkpoint to `MODEL_PATH`.

Dataset collection accepts an explicit API key from the shell (the downloader does not load `.env` itself):

```sh
FLICKR_API_KEY=your-key uv run --locked --extra training python -m scripts.download_images \
  --queries smiski --out data/raw/smiski --label smiski --license-filter cc
```

Review source permissions and attribution before distributing collected photos. Dataset evaluation and documentation will be expanded separately.

### Conda alternative

From the repository root, `conda env create -f environment.yml` installs Python 3.11 and the same declared dependencies with training extras. Activate with `conda activate my-smiski`, then use `python` in place of `uv run --locked python`. Conda/pip resolves transitive dependencies independently; use the uv workflow above for the committed full lock.
