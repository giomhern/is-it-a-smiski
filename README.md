# Is It a Smiski?

A collector's take on computer vision. Upload a photo or try an example to see whether a ResNet50 model recognizes a Smiski.

Built with **Next.js** and **Flask**, using **PyTorch** for training/export and **ONNX Runtime** for CPU inference. Images are processed in memory and never saved.

**[Try the live app](https://is-it-a-smiski.onrender.com)** · Hosted on Render's free tier; the first prediction may take a minute while the API wakes up.

![Smiski photo classifier](docs/screenshots/app.jpg)

Drag and drop a JPG, PNG, or WebP, or try the bundled Smiski and Sonny Angel examples. See the prediction and model score, then replace or clear the photo. The static frontend and Docker API run on Render's free hosting.

## Run locally

Run the API and frontend in two terminals.

### 1. First-time setup

Install **Python 3.11**, **Node.js 22** (includes npm), and [uv](https://docs.astral.sh/uv/getting-started/installation/), then clone the repository:

```sh
git clone https://github.com/giomhern/is-it-a-smiski.git
cd is-it-a-smiski
```

If you already have the repository, open its root directory. Install dependencies and download the model:

```sh
uv sync --locked
npm --prefix frontend ci
test -f .env || cp .env.example .env
test -f frontend/.env.local || cp frontend/.env.example frontend/.env.local
uv run --locked python -m scripts.install_model
uv run --locked --extra training python -m scripts.export_model
```

These commands keep existing environment files. The installer downloads about 90 MB of checksum-verified weights from the [model release](https://github.com/giomhern/is-it-a-smiski/releases/tag/model-v1). No training data or Flickr credentials are needed to run the app. The one-time export uses CPU-only PyTorch on Linux; the API uses ONNX Runtime to fit small hosts.

### 2. Start the API — terminal 1

From the repository root:

```sh
uv run --locked python -m backend.api.app
```

Leave it running at http://localhost:5050. Check readiness at http://localhost:5050/health; it should return `{"status":"ok"}`.

### 3. Start the frontend — terminal 2

From the repository root:

```sh
npm --prefix frontend run dev
```

Open **http://localhost:3000**, choose an example or upload a photo, then click **Classify**. Keep both terminals running; press `Ctrl+C` in each to stop. On later runs, repeat only steps 2 and 3.

### If something does not work

- **Model missing:** repeat the install and export commands from step 1.
- **Cannot reach the API:** check that it is running on port 5050 and `frontend/.env.local` contains `NEXT_PUBLIC_API_URL=http://localhost:5050`. Restart the frontend after editing it.
- **Port already in use:** stop the existing process on 3000 or 5050. Use `localhost:3000` so the browser origin matches the default API configuration.

## API

`GET /health` checks readiness. `POST /api/predict` accepts one multipart `image` (JPEG, PNG, or WebP; up to 10 MiB; JPEG/PNG up to 32 megapixels, WebP up to 16 megapixels; each side up to 16,384 pixels) and returns a prediction, confidence, and both class scores.

Prediction attempts share an instance-wide budget of 30 per minute and 300 per hour. Excess requests return `429` with `Retry-After` before parsing uploads; health checks remain available. SQLite keeps the two counters across worker restarts, resetting on container replacement. This bounds inference work, but does not guarantee availability during abuse or distribute limits across multiple instances. Multipart requests are limited to two parts and 128 KiB per text field. The Docker runtime uses a non-root user with read-only application files.

```sh
curl -f -F image=@tests/smiski/test-smiski.jpeg http://localhost:5050/api/predict
```

## Model

The default checkpoint has unknown training provenance; its scores are uncalibrated. A separate frozen-ImageNet baseline reached 94.52% accuracy on 146 folder-labeled test photos, but labels are imperfect and it fails the included Sonny Angel example. This is preliminary evidence, not a real-world accuracy claim or authenticity check. See the short [model card](docs/MODEL_CARD.md).

## Training and evaluation

Training is optional and requires local photos in `data/raw/{smiski,non_smiski}/` (or `DATA_DIR`). Generated splits, reports, and training metadata stay outside Git.

Collect review candidates with the free [Openverse API](https://api.openverse.org/v1/) (no key needed):

```sh
uv run --locked python -m scripts.collect_candidates \
  --queries "smiski" "smiski figurine" "スミスキー" --label smiski
uv run --locked python -m scripts.collect_candidates \
  --queries "Sonny Angel" --title-phrase --label non_smiski
uv run --locked python -m scripts.collect_candidates \
  --queries "green figurine" "frog figurine" --label non_smiski
open data/candidates-v1/index.html
```

This separate collector leaves the Flickr downloader unchanged. It requests up to 10 results per query, filters to CC0/CC BY images, saves source/creator/license metadata, rejects corrupt or undersized images, and flags possible blur, exposure problems, and near duplicates. Use `--title-phrase` for brands to avoid matches in unrelated descriptions. Results without category metadata are included; visually confirm they are photographs of the intended subject. Exact pixel duplicates are rejected within the collection; reruns preserve existing candidates. Downloads stay under ignored `data/candidates-v1/`, outside training folders.

Inspect the gallery, verify each original source/license and host terms, then download review decisions. Import them to resume later:

```sh
uv run --locked python -m scripts.collect_candidates \
  --decisions ~/Downloads/review-decisions.json
```

Approval records a reviewed label in `manifest.json`; it does not move images into training. Openverse metadata does not establish permission, and quality/duplicate flags need visual review. Before creating a new dataset, check against existing photos and keep related photographer/shoot/listing images in the same split. Collection respects rate limits and stops on HTTP 429; retry later. See [Openverse terms](https://docs.openverse.org/terms_of_service.html).

```sh
uv run --locked python -m scripts.prepare_dataset
uv run --locked --extra training python -m scripts.train_model --output backend/models/my_model.pt
uv run --locked --extra training python -m scripts.evaluate_model \
  --checkpoint backend/models/my_model.pt --output data/evaluation/my_model.json
```

Scripts refuse to overwrite existing results. Training uses only train/validation partitions; evaluation checks checkpoint and split provenance. Use a new snapshot/output path for a changed dataset and a fresh test set after tuning on previous test results.

The original v1 split is preserved unchanged in [Git history](https://github.com/giomhern/is-it-a-smiski/blob/8723cbaf84d39f44c37dfa79cd3737099bfc3faf/docs/dataset/split-v1.json). To reproduce that run with the original photos, download it instead of creating a new split:

```sh
mkdir -p data/splits
curl --fail --location --output data/splits/split-v1.json \
  https://raw.githubusercontent.com/giomhern/is-it-a-smiski/8723cbaf84d39f44c37dfa79cd3737099bfc3faf/docs/dataset/split-v1.json
```

Historical reports and baseline metadata are archived with the [model release](https://github.com/giomhern/is-it-a-smiski/releases/tag/model-v1).

## Deploy on Render

Create both services from this repository's `main` branch:

| Setting | Backend (Web Service) | Frontend (Static Site) |
| --- | --- | --- |
| Live URL | [API](https://is-it-a-smiski-api.onrender.com/health) | [App](https://is-it-a-smiski.onrender.com) |
| Runtime | Docker | Static |
| Root directory | Repository root | `frontend` |
| Plan | Free | Free |
| Build command | Dockerfile | `npm ci && npm run build` |
| Publish directory | — | `out` |
| Health check | `/health` | — |

Deploy the backend first. Set the frontend's `NEXT_PUBLIC_API_URL` to its HTTPS URL before building. Set the backend's `ALLOWED_ORIGINS` to the frontend's exact HTTPS origin, without a trailing slash. Rebuild the frontend after changing its API URL.

Current values: `NEXT_PUBLIC_API_URL=https://is-it-a-smiski-api.onrender.com` and `ALLOWED_ORIGINS=https://is-it-a-smiski.onrender.com`.

The free backend sleeps after 15 minutes without traffic, so the first prediction may take a minute. Static hosting keeps the frontend available while it wakes up. Both services share Render's included bandwidth and build limits.

The current services use the public repository connection. After pushing updates, use **Manual Deploy → Deploy latest commit** on the affected service in Render.

## Docker backend

The image exports the verified checkpoint during its build and serves it without PyTorch. The model is preloaded once; each request gets a fresh worker so large upload buffers are reclaimed.

```sh
docker build --platform linux/amd64 -t is-it-a-smiski:local .
docker run --rm -p 5050:5050 --memory 512m --memory-swap 512m is-it-a-smiski:local
```

Stop an existing local API before using port 5050. Run the constrained regression check with Docker open:

```sh
uv run --locked python -m scripts.check_memory
```

## Checks

```sh
uv run --locked --extra training python -m unittest discover -s tests/unit -v
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

Inference tests require the installed checkpoint and its export. Contribution and coding standards live in [AGENTS.md](AGENTS.md).

The development lint dependency `braces` has an [unpatched advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm). It is not included in the deployed static site or API image.

Independent fan project; unaffiliated with [Smiski](https://smiski.com/e/smiski/).
