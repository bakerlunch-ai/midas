# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Manifests first so source changes don't invalidate the dep-install layer
COPY pyproject.toml uv.lock ./
COPY packages/bot-events/pyproject.toml packages/bot-events/
COPY services/data-svc/pyproject.toml services/data-svc/

RUN uv sync --frozen --no-dev --package data-svc

COPY packages/bot-events/src packages/bot-events/src
COPY services/data-svc/src services/data-svc/src

RUN uv sync --frozen --no-dev --no-editable --package data-svc


FROM python:3.12-slim-bookworm AS runtime

RUN groupadd -r -g 1000 app \
    && useradd -r -u 1000 -g app -d /app -s /sbin/nologin app \
    && mkdir -p /app \
    && chown app:app /app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

USER app

EXPOSE 8080

CMD ["uvicorn", "data_svc.main:app", "--host", "0.0.0.0", "--port", "8080"]
