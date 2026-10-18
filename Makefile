# Common tasks. Everything runs through uv; see CLAUDE.md (Commands).

.PHONY: install test lint format data data-diadata smoke results all

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

# End-to-end check on 2 patients x 2 days (a few minutes).
smoke:
	uv run python experiments/run_benchmark.py --config experiments/configs/smoke.yaml

# Every table and figure in results/ (long: the full cohort is simulated once, then cached).
results:
	uv run python -m ghostlows.sim --config experiments/configs/sim_full.yaml
	uv run python experiments/run_all.py

all: lint test results
