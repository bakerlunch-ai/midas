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

# Unhide editable-install .pth files. macOS iCloud's File Provider daemon
# continuously re-hides .pth files inside iCloud-synced directories
# (~/Desktop, ~/Documents). pytest collection no longer depends on these
# flags (cd93039 added explicit pythonpath in pyproject.toml), but we
# still chflags them so editor/IDE tooling that reads .pth works cleanly.
# Fail loud on macOS: if chflags errors, we want to know. No-op on Linux
# (chflags absent; the leading - tells make to ignore exit status there).
_unhide-pth:
	-chflags nohidden .venv/lib/python*/site-packages/*.pth
