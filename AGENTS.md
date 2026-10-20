# AGENTS.md

For an AI assistant helping a researcher with Ghost Lows. Full rules: [docs/reference/ENGINEERING.md](docs/reference/ENGINEERING.md).

## Map

- `src/ghostlows/`: loaders, metrics, simulator, faults, alarms, scoring, upload-report flags.
- `experiments/`: configs and scripts behind every table and figure.
- `scripts/`: download, app build, reproducibility check, sample export, packaging.
- `results/`: tables and figures; [results/README.md](results/README.md) is the full record.
- `app/`: the browser-only upload report.
- `tests/`: pytest, including checks of the rules below.
- [docs/CLINICAL_REVIEW.md](docs/CLINICAL_REVIEW.md): clinical claims awaiting sign-off.
- [docs/PRIVACY_AND_SAFETY.md](docs/PRIVACY_AND_SAFETY.md): upload-report rules.
- [docs/CITATIONS.md](docs/CITATIONS.md): every source key.
- [RESEARCH.md](docs/reference/RESEARCH.md): questions, hypotheses, limitations.
- [BENCHMARK.md](docs/reference/BENCHMARK.md): alarms, metrics, operating point, statistics.
- [SIMULATION.md](docs/reference/SIMULATION.md), [SIMULATION_NOTES.md](docs/reference/SIMULATION_NOTES.md): cohort and faults, specified and built.
- [DATA.md](docs/reference/DATA.md): datasets, schema, export formats.
- [DECISIONS.md](docs/reference/DECISIONS.md): decisions and dated amendments.
- `docs/development/`: build history, not specification.

## How to walk someone through this repo

Read in order: README, SUMMARY, results Summary, RESEARCH §2–3 and §6, BENCHMARK, DECISIONS Amendments.

| Question | Table |
|---|---|
| How much is compression? | [RQ1](results/README.md#rq1-cgm-only-alarms-as-compression-nights-increase-default-mix), by cause |
| Do trend alarms suffer more? | [H1](results/README.md#h1-trend-versus-threshold-alarms-as-compression-nights-increase) |
| Does insulin and carb context help? | [H2](results/README.md#h2-what-insulin-and-carb-context-adds-compression-false-alarms-cgm--time--iobcob--cgm--time) |
| Does a Kalman filter do better? | [RQ3](results/README.md#rq3-exploratory-a-kalman-filter-with-an-explicit-compressed-state) |
| Does it hold on real data? | [Real data](results/README.md#real-data) |
| What changed after pre-registration? | [Amendments](docs/reference/DECISIONS.md#amendments) |
| What are the limits? | [RESEARCH §6](docs/reference/RESEARCH.md#6-known-limitations-to-state-up-front) |

## Hard rules

Other files cite these numbers. [Full text](docs/reference/ENGINEERING.md#hard-rules).

1. Literature values carry `# SOURCE: <key>` from [CITATIONS.md](docs/CITATIONS.md); never invent one.
2. Values we chose carry `# ASSUMPTION: <why>` and are configurable.
3. Code depending on a clinical claim carries `# CLINICAL-REVIEW: CRn`.
4. Causality: alarms use only past data; a test proves it.
5. No leakage: leave-patients-out splits; CIs across patients.
6. Faults never touch truth (`truth_glucose`).
7. Safety wording: "possible compression artifact"; never "not real", "fake", "ignore" ([rules](docs/PRIVACY_AND_SAFETY.md)).
8. No user data leaves the browser: no backend, no analytics.
9. No data in git, never patient data.
10. Do not overclaim: effect sizes with CIs, limitations from RESEARCH §6.
11. Amend before computing: a dated amendment in DECISIONS first; `protocol-v1` never moves.

## Commands

```
uv sync
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run ghostlows benchmark --config experiments/configs/smoke.yaml
uv run python experiments/make_results_readme.py   # results/README.md
make data data-azt1d && make results                # hours
```

Browser tests: [CONTRIBUTING.md](CONTRIBUTING.md#tests-and-lint).
