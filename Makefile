# Common tasks. Everything runs through uv; see CLAUDE.md (Commands).

.PHONY: install test lint format data data-diadata smoke all

install:
	uv sync

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

# GlucoBench (small, default) into data/raw/, with data/raw/MANIFEST.json.
data:
	uv run python scripts/download_data.py

# Adds DiaData's 5-minute archive (2.3 GB).
data-diadata:
	uv run python scripts/download_data.py --diadata

# experiments/run_benchmark.py arrives in phase 5 (docs/ROADMAP.md).
smoke:
	@echo "smoke: needs experiments/run_benchmark.py (phase 5)" >&2; exit 1

# Grows with the roadmap: from phase 6 it regenerates every table and figure.
all: lint test
