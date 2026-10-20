# AGENTS.md

The rules for anyone changing this repository, human or coding agent. Read them before your first change. Step-by-step how-tos are in [CONTRIBUTING.md](CONTRIBUTING.md).

## What this project is

An open benchmark that scores real-time CGM low-glucose alarms on **lows caught, false alarms per day and minutes of warning**, under a mixed sensor-fault suite (compression/PISA, dropout, stale, drift, spikes), plus a controlled ablation of what **insulin and carb context** adds. On top: an in-browser upload report for Dexcom Clarity / LibreView exports. **The benchmark is the contribution, not a new detector.** See [`docs/RESEARCH.md`](docs/RESEARCH.md).

## Hard rules

Other files cite these by number ("hard rule 5"); keep the numbering.

1. **Cite everything.** Any number, threshold, model shape or definition taken from the literature gets a comment `# SOURCE: <key>` using a key from `docs/CITATIONS.md`. If a source is not in that file, add it there (and to `docs/references.bib`) in the same commit. Never invent a citation, DOI, author or number.
2. **Mark assumptions.** Any value we chose ourselves gets `# ASSUMPTION: <why>` and must be configurable. Benchmark runs collect these into `assumptions.md`.
3. **Mark clinical dependencies.** Code depending on an item in `docs/CLINICAL_REVIEW.md` gets `# CLINICAL-REVIEW: CRn`.
4. **Causality.** Alarms may only use data up to the current time. Every alarm has a test that perturbing future samples does not change past scores.
5. **No leakage.** Leave-patients-out splits only. Confidence intervals are across patients, not seeds.
6. **Faults never touch truth.** `truth_glucose` is produced by the simulator and never modified by a fault.
7. **Safety wording.** In the app and any user-facing text: "possible compression artifact". Never "not real", "fake", "ignore". Follow `docs/PRIVACY_AND_SAFETY.md`.
8. **No user data leaves the browser.** The app has no backend. No analytics.
9. **No data in git.** `data/` and `results/*/` are gitignored. Never commit real patient data, even de-identified.
10. **Do not overclaim.** Results text reports effect sizes with CIs and states limitations from `docs/RESEARCH.md` §6.
11. **Amend before computing.** Any change to a result, metric or operating point needs a dated amendment in `docs/DECISIONS.md` (Amendments) before anything is computed. The tag `protocol-v1` is never moved.

## Markers

One comment per value, on its line or directly above it:

```python
DROPOUT_RATE_PER_MIN = np.log(10) / 20.0  # SOURCE: Facchinetti 2016 (90% of gaps < 20 min)
night_hours = (23.0, 7.0)  # ASSUMPTION: PISA onset window
# CLINICAL-REVIEW: CR17
```

- `tests/test_repo_rules.py` fails if a `SOURCE` key is not in the first column of `docs/CITATIONS.md`, if a `CLINICAL-REVIEW` id is not a `**CRn.` item in `docs/CLINICAL_REVIEW.md`, or if a ticked CR item does not end with `Signed off: <reviewer>, <YYYY-MM-DD>.`
- `collect_assumptions()` (`src/ghostlows/bench/pipeline.py`) gathers every `ASSUMPTION` in `src/ghostlows/` into each run's `assumptions.md` and into `results/tables/assumptions.md`.

## Stack

- Python **3.11** with **uv**. simglucose needs `setuptools<70` (it imports `gym` → `pkg_resources`). Python 3.13 cannot build `gym`.
- numpy, pandas, scipy, scikit-learn, pyarrow, pyyaml, matplotlib, plotly; pytest, ruff.
- App: **stlite** (Streamlit on Pyodide) as a static site on GitHub Pages. The app imports `ghostlows` as a pure-Python wheel, so keep `ghostlows.io`, `ghostlows.metrics` and `ghostlows.retro` free of simglucose and other non-Pyodide dependencies (a test checks this).

## Layout

```
src/ghostlows/  io (export and dataset loaders), metrics (consensus CGM metrics), sim (simglucose engine),
                faults (PISA, dropout, stale, drift, spikes), alarms, bench (events, scoring, CV, CIs),
                retro (upload-report flags), cli.py
experiments/    configs/*.yaml and the scripts behind every table and figure: run_benchmark, run_all,
                run_curves, real_data, make_figures, make_fault_figure, make_results_readme, sim_report, pilot/
scripts/        download_data, build_app, check_reproducible, make_sample_export, package_cohort
examples/       custom_alarm.py, the plug-in alarm (tested in CI)
results/        README.md (generated), tables/ and figures/ (committed); run outputs are gitignored
app/            the upload report: stlite app and index.html, no server
tests/          pytest; fixtures in tests/fixtures/ (synthetic only)
docs/           specifications (source of truth for behaviour); development records in docs/development/
paper.md        Journal of Open Source Software draft
```

## Commands

```
uv sync
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run python scripts/download_data.py            # GlucoBench (small)
uv run python scripts/download_data.py --diadata  # large, opt-in
uv run python experiments/run_benchmark.py --config experiments/configs/smoke.yaml
uv run python experiments/make_results_readme.py  # results/README.md from results/tables/
```

The `Makefile` wraps these and the long runs (`make results`, `make reproduce`).

## Working style

- Small commits with clear messages. Run tests and ruff before each commit.
- If a spec in `docs/` is ambiguous or wrong, update the doc in the same commit and say why in the message.
- Keep the specs and the code in agreement; the docs describe behaviour, the code implements it.
- `results/README.md` and `results/tables/assumptions.md` are generated by `experiments/make_results_readme.py`. Change the generator and regenerate; never edit them by hand.
- A push to `main` that touches `app/`, `src/ghostlows/` or `pyproject.toml` redeploys the upload report once its browser tests pass (`.github/workflows/pages.yml`).
