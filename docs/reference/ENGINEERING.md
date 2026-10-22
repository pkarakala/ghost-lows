# Engineering reference

The full rules and engineering detail behind [AGENTS.md](../../AGENTS.md), for anyone changing the code. Step-by-step how-tos are in [CONTRIBUTING.md](../../CONTRIBUTING.md).

## What this project is

An open benchmark that scores real-time CGM low-glucose alarms on **lows caught, false alarms per day and minutes of warning**, under a mixed sensor-fault suite (compression/PISA, dropout, stale, drift, spikes), plus a controlled ablation of what **insulin and carb context** adds. On top: an in-browser upload report for Dexcom Clarity / LibreView exports. **The benchmark is the contribution, not a new detector.** See [`RESEARCH.md`](RESEARCH.md).

## Hard rules

Other files cite these by number ("hard rule 5"); keep the numbering. AGENTS.md lists them in one line each.

1. **Cite everything.** Any number, threshold, model shape or definition taken from the literature gets a comment `# SOURCE: <key>` using a key from `docs/CITATIONS.md`. If a source is not in that file, add it there (and to `docs/references.bib`) in the same commit. Never invent a citation, DOI, author or number.
2. **Mark assumptions.** Any value we chose ourselves gets `# ASSUMPTION: <why>` and must be configurable. Benchmark runs collect these into `assumptions.md`.
3. **Mark clinical dependencies.** Code depending on an item in `docs/CLINICAL_REVIEW.md` gets `# CLINICAL-REVIEW: CRn`.
4. **Causality.** Alarms may only use data up to the current time. Every alarm has a test that perturbing future samples does not change past scores.
5. **No leakage.** Leave-patients-out splits only. Confidence intervals are across patients, not seeds.
6. **Faults never touch truth.** `truth_glucose` is produced by the simulator and never modified by a fault.
7. **Safety wording.** In the app and any user-facing text: "possible compression artifact". Never "not real", "fake", "ignore". Follow `docs/PRIVACY_AND_SAFETY.md`.
8. **No user data leaves the browser.** The app has no backend. No analytics.
9. **No data in git.** `data/` and `results/*/` are gitignored. Never commit real patient data, even de-identified.
10. **Do not overclaim.** Results text reports effect sizes with CIs and states limitations from `docs/reference/RESEARCH.md` §6.
11. **Amend before computing.** Any change to a result, metric or operating point needs a dated amendment in `docs/reference/DECISIONS.md` (Amendments) before anything is computed. The tag `protocol-v1` is never moved.

## Markers

One comment per value, on its line or directly above it:

```python
DROPOUT_RATE_PER_MIN = np.log(10) / 20.0  # SOURCE: Facchinetti 2016 (90% of gaps < 20 min)
night_hours = (23.0, 7.0)  # ASSUMPTION: PISA onset window
# CLINICAL-REVIEW: CR17
```

- `tests/test_repo_rules.py` fails if a `SOURCE` key is not in the first column of `docs/CITATIONS.md`, if a `CLINICAL-REVIEW` id is not a `**CRn.` item in `docs/CLINICAL_REVIEW.md`, or if a CR item's two sign-offs (`Literature checked: <name>, <YYYY-MM-DD>.` and `Clinician reviewed: <name>, <role>, <YYYY-MM-DD>.`) are filled in without a tick or ticked without being filled in, or if an item's tick does not match its sign-offs (the literature check closes a factual item; one marked **Needs a clinician** also needs the clinician's).
- `collect_assumptions()` (`src/ghostlows/bench/pipeline.py`) gathers every `ASSUMPTION` in `src/ghostlows/` into each run's `assumptions.md` and into `results/tables/assumptions.md`.

## Stack

- Python **3.11** with **uv**. simglucose needs `setuptools<70` (it imports `gym` → `pkg_resources`). Python 3.13 cannot build `gym`.
- numpy, pandas, scipy, scikit-learn, pyarrow, pyyaml, matplotlib; pytest, ruff.
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
docs/           human docs; reference/ holds the specifications (source of truth for behaviour);
                development records in docs/development/
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

## Test suites

Two marked suites are skipped by default:

| Suite | When to run it | Commands |
|---|---|---|
| Browser (the upload report in Chromium) | You changed `app/`, `ghostlows.io`, `ghostlows.metrics` or `ghostlows.retro`. The Pages workflow runs it before every deploy. | `uv sync --group browser`<br>`uv run playwright install chromium`<br>`uv run python scripts/build_app.py`<br>`uv run pytest -q -m browser tests/test_app_browser.py` |
| Network (the pinned dataset URLs) | You changed `scripts/download_data.py`. | `uv run pytest -q -m network` |

## Add an alarm

A **plug-in** alarm changes no published number. Subclass `ghostlows.alarms.BaseAlarm`, return one score per sample from `_score_run` using only past values, and score it with the same faults, folds and statistics as the built-in alarms:

```
uv run ghostlows score --alarm examples/custom_alarm.py:FallingBelow70 --config experiments/configs/smoke.yaml
```

To make it a **benchmark** alarm:

| What | Where |
|---|---|
| Rule alarm | `src/ghostlows/alarms/rules.py` |
| Published detector, used as a gate and in the four context arms | a `Detector` subclass in `src/ghostlows/alarms/learned.py`, its scoring function in `detectors.py`, an entry in `DETECTORS` |
| Registration | `stretch_alarms()` in `src/ghostlows/alarms/__init__.py`. Adding to `benchmark_alarms()` or `DETECTORS` changes the pre-registered set, so it needs an amendment first ([CONTRIBUTING.md](../../CONTRIBUTING.md#change-a-result-a-metric-or-the-operating-point)). |
| Specification | `docs/reference/BENCHMARK.md` §2 |
| Runs | select it by name under `alarms:` in `experiments/configs/*.yaml` |

Tests required:

- **Causality** (hard rule 4). A registered alarm joins `test_every_alarm_is_causal` in `tests/test_alarms.py` automatically. A plug-in alarm needs its own test; `test_example_alarm_is_causal` in the same file shows how, with the shared `assert_causal` helper.
- **A known answer** on a short synthetic trace: when it must fire and when it must not.
- **The urgent-low floor still fires** (`test_floor_is_never_suppressed`).
- **Markers.** Every literature value carries `# SOURCE:`, every value of ours `# ASSUMPTION:` (hard rules 1–2).

## Add a fault

| What | Where |
|---|---|
| Knobs | a field per rate or size in `FaultConfig` (`src/ghostlows/faults/suite.py`), each with a `SOURCE` or `ASSUMPTION` marker |
| Injection | a block in `apply_run` that changes only the observed CGM, draws from its own `stream(seed, "<kind>")` so existing faults stay identical, and labels its samples with `mark()` |
| Label priority | `LABEL_PRIORITY` in `suite.py`. Cause attribution (`src/ghostlows/bench/scoring.py`) then counts its false alarms as "other fault". |
| Specification | `docs/reference/SIMULATION.md` §4.2 |

Leave the new kind out of the default `FaultConfig.enabled` unless an amendment adds it: enabling it changes every number.

Tests required, in `tests/test_faults.py`:

- truth and the clean signals untouched (`test_faults_never_touch_truth_or_clean_signals`, hard rule 6);
- nothing injected at severity 0 (`test_no_faults_at_zero_severity`);
- nested severity sweeps and independent fault types (`test_sweeps_are_nested_and_fault_types_are_independent`);
- the same faults for the same seed and run (`test_run_faults_depend_only_on_seed_and_run_identity`).

## Working style

- Small commits with clear messages. Run tests and ruff before each commit.
- If a spec in `docs/` is ambiguous or wrong, update the doc in the same commit and say why in the message.
- Keep the specs and the code in agreement; the docs describe behaviour, the code implements it.
- `results/README.md` and `results/tables/assumptions.md` are generated by `experiments/make_results_readme.py`. Change the generator and regenerate; never edit them by hand.
- A push to `main` that touches `app/`, `src/ghostlows/` or `pyproject.toml` redeploys the upload report once its browser tests pass (`.github/workflows/pages.yml`).
