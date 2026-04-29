# Midas

Midas is a multi-service prediction market trading bot, organized as a monorepo.

## Layout

- `services/` — independently deployable services (one subdirectory each)
- `packages/` — shared Python libraries consumed by services
  - `bot-events/` — shared Pydantic v2 event schemas
- `deploy/` — Kubernetes manifests
- `docs/` — architecture and operational notes

## Tooling

- Python 3.12 (pinned via `.python-version`)
- [uv](https://docs.astral.sh/uv/) workspaces for dependency management
- [ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Make targets: `make lint`, `make format`, `make test`, `make install`

## Getting started

```bash
make install
make lint
make test
```
