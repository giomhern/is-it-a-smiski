FROM ghcr.io/astral-sh/uv:0.12.9 AS uv
FROM python:3.11-slim-bookworm AS base
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./

FROM base AS export
RUN uv sync --locked --no-dev --extra training --no-cache
COPY backend backend
COPY scripts scripts
RUN .venv/bin/python -m scripts.install_model
RUN .venv/bin/python -m scripts.export_model

FROM base AS runtime
RUN uv sync --locked --no-dev --no-cache
COPY gunicorn.conf.py ./
COPY backend backend
COPY --from=export /app/backend/models/smiski_classifier.pt /app/backend/models/smiski_classifier.onnx /app/backend/models/
RUN groupadd --gid 10001 smiski && useradd --uid 10001 --gid smiski --no-create-home smiski \
    && chmod -R a+rX,a-w /app
USER smiski
# Return large temporary allocations instead of retaining them between uploads.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MALLOC_ARENA_MAX=2 \
    MALLOC_MMAP_THRESHOLD_=131072 \
    MALLOC_TRIM_THRESHOLD_=65536
EXPOSE 5050
CMD ["sh", "-c", "exec gunicorn --no-control-socket --bind 0.0.0.0:${PORT:-5050} --workers 1 --preload --max-requests 1 --timeout 120 backend.api.app:app"]
