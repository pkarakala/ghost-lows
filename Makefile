# Common tasks. Everything runs through uv; see AGENTS.md (Commands).

.PHONY: install test lint format data data-diadata data-azt1d smoke sample results reproduce all fault-figure sim-report package

# Parallel benchmark workers each run their own models; keep native thread pools small.
export OMP_NUM_THREADS ?= 2

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

# Adds AZT1D (776 MB), needed for H3.
data-azt1d:
	uv run python scripts/download_data.py --azt1d

# End-to-end check on 2 patients x 2 days (a few minutes).
smoke:
	uv run python experiments/run_benchmark.py --config experiments/configs/smoke.yaml

# The synthetic export behind the app's "Try it with sample data" (about a minute).
sample:
	uv run python scripts/make_sample_export.py

# Every table and figure in results/ (long: the full cohort is simulated once, then cached;
# the real-data track needs `make data data-azt1d`).
results:
	uv run python -m ghostlows.sim --config experiments/configs/sim_full.yaml
	uv run python experiments/real_data.py
	uv run python experiments/run_all.py

# A clean checkout of the commit behind the headline tables reproduces them (phase 10).
reproduce:
	uv run python scripts/check_reproducible.py --config rq1_pisa_sweep --resimulate 3

all: lint test results

# The example-faults figure in docs/figures/ (SIMULATION.md).
fault-figure:
	uv run python experiments/make_fault_figure.py

# The cohort report in docs/reference/SIMULATION_NOTES.md (needs the simulated cohort).
sim-report:
	uv run python experiments/sim_report.py --config experiments/configs/sim_full.yaml

# dist/ghostlows-bench-v1.zip: the frozen cohort for a dataset release (DECISIONS.md D18).
package:
	uv run python scripts/package_cohort.py
