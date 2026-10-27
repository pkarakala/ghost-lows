# Contributing

How to set up, test and extend Ghost Lows. Every change follows the [hard rules](AGENTS.md#hard-rules). Details are in [ENGINEERING.md](docs/reference/ENGINEERING.md).

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

After a docs edit, `uv run python scripts/check_docs_preserved.py --before origin/main` checks that no number, citation or safety sentence was lost.

Run the browser tests when you change `app/`, `ghostlows.io`, `ghostlows.metrics` or `ghostlows.retro`. They load the upload report in Chromium:

```
uv sync --group browser
uv run playwright install chromium
uv run python scripts/build_app.py
uv run pytest -q -m browser tests/test_app_browser.py
```

Run `uv run pytest -q -m network` when you change `scripts/download_data.py`. It checks the pinned dataset URLs.

## Add an alarm

A plug-in alarm changes no published number. Subclass `ghostlows.alarms.BaseAlarm` and return one score per sample from `_score_run`, using only past values. Score it like the built-in alarms ([example](examples/custom_alarm.py)):

```
uv run ghostlows score --alarm examples/custom_alarm.py:FallingBelow70 --config experiments/configs/smoke.yaml
```

It needs a causality test (hard rule 4), a known-answer test and a marker on every value. To make it a benchmark alarm, see [ENGINEERING.md](docs/reference/ENGINEERING.md#add-an-alarm).

## Add a fault

A fault changes only the observed glucose, never the truth (hard rule 6). Leave it out of the default `FaultConfig.enabled` unless an amendment adds it: enabling it changes every number. Where the code goes, and the four required tests: [ENGINEERING.md](docs/reference/ENGINEERING.md#add-a-fault).

## Change a result, a metric or the operating point

Hard rule 11: amend before computing.

1. Add a dated entry under Amendments in `docs/reference/DECISIONS.md`. Give the date, whether any result existed yet, the change, the reason and what is expected to change. Commit it on its own.
2. Implement the change and its tests.
3. Recompute, then regenerate `results/README.md` with `uv run python experiments/make_results_readme.py`. Never edit it by hand.
4. Name the amendment in the pull request.

## Review a clinical claim

For literature checkers and clinicians; no code needed. [`docs/CLINICAL_REVIEW.md`](docs/CLINICAL_REVIEW.md) lists each clinical claim the code depends on (CR1–CR17), with its source.

1. Pick an item. Check it against the cited source or your clinical experience (items marked **Needs a clinician** need both).
2. Open a [**Clinical correction** issue](https://github.com/pkarakala/ghost-lows/issues/new/choose). Give the CR id, whether you checked the literature or reviewed as a clinician (with your role), your verdict (agree, disagree or unsure), your evidence and, if you disagree, the value or wording you would use.
3. A maintainer records your sign-off with the date, or changes the spec and the code. `grep -rn "CLINICAL-REVIEW: CR<n>" src app scripts experiments` shows the code affected. A change that moves a number goes through an amendment first.

## Pull requests

Fill in the template. A push to `main` that touches `app/`, `src/ghostlows/` or `pyproject.toml` redeploys the upload report.
