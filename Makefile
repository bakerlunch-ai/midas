.PHONY: lint test format install

install:
	uv sync --all-packages

lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

test:
	uv run pytest
