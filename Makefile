.PHONY: lint test format install _unhide-pth

install:
	uv sync --all-packages
	$(MAKE) _unhide-pth

lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

test: _unhide-pth
	.venv/bin/pytest

# Unhide editable-install .pth files (macOS-only; uv sets UF_HIDDEN on them,
# which makes Python's site.py skip them silently. No-op on Linux.)
_unhide-pth:
	@chflags nohidden .venv/lib/python*/site-packages/*.pth 2>/dev/null || true
