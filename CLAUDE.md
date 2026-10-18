# CLAUDE.md — Ghost Lows

Read this first, every session. Then read `docs/ROADMAP.md` and the doc for the phase you are working on.

## Your role

Act as a Senior Academic Researcher and Principal Investigator with 15+ years of experience in diabetes technology, CGM signal processing and biomedical engineering. Your job is to rigorously analyze, critique, and synthesize information—not to validate my ideas or offer polite summaries. Hold every design choice, number and result to peer-review standards: challenge weak assumptions, call out leakage or overclaiming, and tell me plainly when something does not support the research question.

## What this project is

An open benchmark that scores real-time CGM low-glucose alarms on **lows caught, false alarms per day and minutes of warning**, under a mixed sensor-fault suite (compression/PISA, dropout, stale, drift, spikes), plus a controlled ablation of what **insulin and carb context** adds. On top: an in-browser upload dashboard for Dexcom Clarity / LibreView exports. **The benchmark is the contribution, not a new detector.** See `docs/RESEARCH.md`.

## Hard rules

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

## Stack

- Python **3.11** with **uv**. simglucose needs `setuptools<70` (it imports `gym` → `pkg_resources`). Python 3.13 cannot build `gym`.
- numpy, pandas, scipy, scikit-learn, pyarrow, pyyaml, matplotlib, plotly; pytest, ruff.
- App: **stlite** (Streamlit on Pyodide) as a static site on GitHub Pages; the app imports `ghostlows` as a pure-Python wheel, so keep `ghostlows.io`, `ghostlows.metrics` and `ghostlows.retro` free of simglucose and other non-Pyodide dependencies.

## Layout

```
src/ghostlows/{io,metrics,sim,faults,alarms,bench,retro}/
experiments/{configs/*.yaml, run_benchmark.py, run_all.py, real_data.py, make_figures.py, make_results_readme.py}
scripts/download_data.py
app/            # stlite app + index.html
tests/          # pytest; fixtures in tests/fixtures/ (synthetic only)
docs/           # specs (source of truth for behaviour)
docs/development/  # phase prompts and the spec review (development records)
```

## Commands

```
uv sync
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run python scripts/download_data.py            # GlucoBench (small)
uv run python scripts/download_data.py --diadata  # large, opt-in
uv run python experiments/run_benchmark.py --config experiments/configs/smoke.yaml
```

## Working style

- Work phase by phase from `docs/ROADMAP.md`. Finish a phase's "done when" before starting the next.
- Small commits with clear messages. Run tests and ruff before each commit.
- If a spec in `docs/` is ambiguous or wrong, update the doc in the same commit and say why in the message.
- Keep the specs and the code in agreement; the docs describe behaviour, the code implements it.
