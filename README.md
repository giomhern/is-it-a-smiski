# Is It a Smiski?

Upload a photo for a Smiski / Non-Smiski prediction. A small collector's project built with Next.js, Flask, and PyTorch ResNet50. Uploaded photos stay in memory.

![Smiski photo classifier](docs/screenshots/app.jpg)

## Run locally

Requires Python 3.11, Node 22, npm, and [uv](https://docs.astral.sh/uv/getting-started/installation/). From the repository root:

```sh
uv sync --locked
cp .env.example .env
uv run --locked python -m scripts.install_model
uv run --locked python -m backend.api.app
```

In another terminal:

```sh
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000. Keep existing environment files if already configured. The model installer downloads checksum-verified weights from the [model-v1 release](https://github.com/giomhern/is-it-a-smiski/releases/tag/model-v1).

## API and deployment

`GET /health` checks readiness. `POST /api/predict` accepts one multipart `image` (JPEG, PNG, or WebP; up to 10 MiB and 40 megapixels) and returns a prediction, confidence, and both class scores.

```sh
curl -f -F image=@tests/smiski/test-smiski.jpeg http://localhost:5050/api/predict
```

For production, install the model, set `ALLOWED_ORIGINS` to the frontend origin, and start the API:

```sh
uv run --locked gunicorn --bind "0.0.0.0:${PORT:-5050}" --workers 1 --timeout 120 backend.api.app:app
```

Set `NEXT_PUBLIC_API_URL` before building the frontend with `npm run build`; serve it with `npm start`. See [.env.example](.env.example) and [frontend/.env.example](frontend/.env.example) for configuration. Public hosting and rate limiting remain deployment work.

## Model

The default checkpoint has unknown training provenance; its scores are uncalibrated. A separate frozen-ImageNet baseline reached 94.52% accuracy on 146 folder-labeled test photos, but labels are imperfect and it fails the included Sonny Angel example. This is preliminary evidence, not a real-world accuracy claim or authenticity check. See the short [model card](docs/MODEL_CARD.md).

## Training and evaluation

Training is optional and requires local photos in `data/raw/{smiski,non_smiski}/` (or `DATA_DIR`). Generated splits, reports, and training metadata stay outside Git.

```sh
uv run --locked python -m scripts.prepare_dataset
uv run --locked python -m scripts.train_model --output backend/models/my_model.pt
uv run --locked python -m scripts.evaluate_model \
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

## Checks

```sh
uv run --locked python -m unittest discover -s tests/unit -v
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

Inference tests require the installed checkpoint. Contribution and coding standards live in [AGENTS.md](AGENTS.md).

Independent fan project; unaffiliated with [Smiski](https://smiski.com/e/smiski/).
