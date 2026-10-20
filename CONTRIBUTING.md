# Contributing

How to set up, test and extend Ghost Lows, and how clinicians can review its clinical claims. Every change must follow the rules in [AGENTS.md](AGENTS.md).

## Setup

[uv](https://docs.astral.sh/uv/) installs Python 3.11 and every dependency, the simulator included:

```
git clone https://github.com/pkarakala/ghost-lows.git && cd ghost-lows
uv sync
uv run pytest -q
```

## Tests and lint

CI runs these on every push and pull request to `main`:

```
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

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
| Registration | `stretch_alarms()` in `src/ghostlows/alarms/__init__.py`. Adding to `benchmark_alarms()` or `DETECTORS` changes the pre-registered set, so it needs an amendment first ([below](#change-a-result-a-metric-or-the-operating-point)). |
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

## Change a result, a metric or the operating point

Hard rule 11: amend before computing.

1. Add a dated entry under Amendments in `docs/reference/DECISIONS.md`. Give the date, whether any result existed yet, the change, the reason and what is expected to change. Commit it on its own.
2. Implement the change and its tests.
3. Recompute, then regenerate `results/README.md` with `uv run python experiments/make_results_readme.py`. Never edit it by hand.
4. Name the amendment in the pull request.

## Review a clinical claim

For clinicians; no code needed. [`docs/CLINICAL_REVIEW.md`](docs/CLINICAL_REVIEW.md) lists each clinical claim the code depends on (CR1–CR17), with its source.

1. Pick an item. Check it against the cited source or your clinical experience.
2. Open a **Clinical correction** issue. Give the CR id, your verdict (agree, disagree or unsure), your evidence and, if you disagree, the value or wording you would use.
3. A maintainer ticks the item with your name and the date, or changes the spec and the code. `grep -rn "CLINICAL-REVIEW: CR<n>" src app scripts experiments` shows the code affected. A change that moves a number goes through an amendment first.

## Pull requests

Fill in the template. A push to `main` that touches `app/`, `src/ghostlows/` or `pyproject.toml` redeploys the upload report.
