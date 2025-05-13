# ──────────────── Stage 1: deps builder ────────────────
FROM python:3.12-slim AS builder

# install the 'uv' CLI
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# only copy your pyproject.toml & lockfile, so builds are invalidated
# only when those change
COPY pyproject.toml uv.lock ./

# install all deps into a .venv in /app
RUN uv sync --frozen --no-cache

# now copy just your app code (and any other needed scripts)
COPY app ./app
COPY celery_worker.py ./

# ──────────────── Stage 2: final image ────────────────
FROM python:3.12-slim

# bring in the uv CLI again
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# copy over the fully-built /app from the builder
COPY --from=builder /app /app

# drop any on-disk caches to slim the image
RUN rm -rf /app/.venv/.cache

# default command
CMD ["/app/.venv/bin/python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]