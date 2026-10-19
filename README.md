# Ghost Lows

**An open benchmark for real-time CGM low-glucose alarms under sensor faults, and a measurement of what insulin and carbohydrate context adds.**

> **Not a medical device. Not for treatment decisions.** This is research software. Nothing it produces should be used to decide whether to treat, ignore or silence a low glucose reading. If a reading looks wrong, confirm with a fingerstick and follow your care team's advice.

## The problem

Continuous glucose monitors (CGMs) sometimes report low glucose when blood glucose is not low. The best-documented cause is pressure on the sensor during sleep, known as a **pressure-induced sensor attenuation (PISA)** or **compression low** [Mensh 2013; Facchinetti 2016]. Such readings cause false overnight alarms [Shivers 2013] and, inside automated insulin delivery, needless insulin suspensions [Baysal 2014].

Detectors for compression lows exist. However, each was evaluated on its own data with its own metrics, and mostly retrospectively. Prior work is listed in [`docs/RESEARCH.md`](docs/RESEARCH.md) §4.

## What this project contributes

1. **An open, alarm-level benchmark.** It scores real-time low alarms on *lows caught*, *false alarms per day* (split by cause) and *minutes of warning*, while the severity of a mixed fault suite (compression, dropout, stale readings, drift, spikes) is varied. Faults never touch the reference glucose.
2. **A controlled ablation of insulin and carb context.** The same published detectors (threshold, trend, Baysal rules, matched filter, isolation forest, gradient boosting) are run with and without insulin- and carbs-on-board, at a pre-registered operating point.
3. **A simulation that reduces, and measures, the insulin "leak".** In a standard simulator, insulin causes every low. Here, unannounced exercise, sensitivity changes and meal errors make some lows less predictable from recorded insulin. How much insulin still explains is reported as a leak AUC (0.63–0.69 across the three mixes). Compression is injected from the published PISA model [Facchinetti 2016].
4. **A browser-only upload report** that flags a *possible compression artifact* in Dexcom Clarity or LibreView exports. It implements published methods; the research contribution is the benchmark.

Hypotheses H1–H3 were pre-registered in the git tag `protocol-v1`. Every later change is a dated amendment in [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Key results (`ghostlows-bench v1`)

Simulated cohort: 30 virtual patients (UVA/Padova 2008 via simglucose), 14 days, 5 seeds; default scenario mix unless stated. 95% CIs come from a patient bootstrap and describe this cohort, not a population. "Severe lows" are level 2 lows (below 54 mg/dL for 15 min). Full tables: [`results/README.md`](results/README.md). Each result is followed by the limitations from [`docs/RESEARCH.md`](docs/RESEARCH.md) §6 that bound it.

### Primary: the pre-registered tests

- **Trend alarms degrade faster than threshold alarms (H1, supported), but only slightly.** The slope difference is 0.09 (0.07–0.10) false alarms per day per unit fraction of compressed nights: about one extra false alarm every 11 days with compression every night.
  *Limits:* one smooth sensor-noise model; the PISA model's time constant and the realistic PISA frequency come from abstracts (Facchinetti 2016, Lobo 2026).
- **Context did not meaningfully reduce compression false alarms at the frozen operating point (H2, null).** For all six detectors, the rate ratio with versus without insulin and carb context lies between 0.94 and 1.00. For example, gradient boosting gives 0.96 (0.92–1.00) and the trend combiner 0.94 (0.90–0.96). All are above the pre-registered smallest effect of interest (0.75). At that operating point (no loss of severe-low sensitivity against the trend alarm), the published compression gates suppressed no or almost no alarms. In the pre-registered 5-point-loss arm, the isolation-forest gate gives 1.27 (1.08–1.45) false alarms per day against trend's 1.39, with half of nights compressed.
  *Limits:* one operating point, whose cost asymmetry awaits clinical review (CR9, CR16); thresholds are chosen on in-sample training scores (P6); the three scenario mixes span a narrow range of how much recorded insulin explains nocturnal lows (leak AUC 0.63–0.69).
- **The real-data check is uninformative (H3).** On real AZT1D nights with injected artifacts, all ratios include 1. The matched simulation shows no benefit to shrink.
  *Limits:* AZT1D users are on automated insulin delivery rather than the open-loop target population, and the artifacts are injected, not real.
- **The compressed state adds nothing (RQ3, exploratory).** A Kalman filter with an explicit compressed state raises fewer false alarms than the best discriminative alarm: ratio 0.88 (0.80–0.98). The same filter without the compressed state does as well: 1.05 (0.93–1.18).
  *Limits:* the filter's pressure mode uses the same PISA model that generates the injected artifacts, and its design was tuned with held-out checks on the standard mix (amendments A3, A9).

### Secondary: trade-off curves (post hoc, amendments A11 and A13)

Both analyses were defined after the v0.1.0 results had been seen.

- **Gates remove compression false alarms only by giving up severe lows (A11).** As each gate's threshold is relaxed, compression false alarms first fall with a CI below 1 at these costs:
  - Baysal: 0.89 (0.81–0.96) times as many, for 11 more missed severe lows of 249.
  - Isolation forest: 0.98 (0.96–0.99), for 5 more missed.
  - Matched filter: 0.99 (0.98–1.00), for 8 more missed.

  The H2 reading is unchanged when 1% or 5% of the trend alarm's training sensitivity is given up.
- **No published gate beats simply retuning the trend alarm (A13).** At matched held-out severe-low sensitivity, no gate gives fewer false alarms per day than the trend alarm with its own threshold lowered. This holds at every one of the 18 stable comparison points in the default and high mixes.
  - The isolation-forest gate gives more false alarms in total: at 82% sensitivity, 1.29 against 0.99 per day, ratio 1.30 (1.05–1.51). It lowers compression false alarms at 4 of its 8 stable points (0.80–0.86 times retuned trend's), but its total is still higher.
  - CGM-only gradient boosting shows no detectable difference in the total (ratios 0.81–1.08, every CI includes 1), but it raises fewer compression false alarms (0.50–0.66 times retuned trend's).
  - The matched-filter gate could not be compared, because its curve never reaches far enough below trend's sensitivity.

  *Limits:* post hoc and exploratory, with 60 comparisons and no multiplicity correction. 42 of the 60 points were not estimable or unstable, including the whole standard mix (32 severe lows). Other limits: 30 virtual patients and one smooth noise model; thresholds chosen on in-sample training scores (P6); virtual patients treat lows at the alarms' own cut-offs, which shapes sensitivity; the matched filter shares its PISA model with the injected artifacts.

### Descriptive

- **Compression is about a fifth of false alarms (RQ1).** Even with a PISA every night, compression causes 0.32 (0.30–0.35) of the trend alarm's 1.53 (1.33–1.73) false alarms per day, about 21%. Noise (0.68) and the other faults (0.43) cause more. The trend alarm catches 90% (86–93%) of severe lows.
  *Limits:* the share depends on the assumed PISA frequency and shape and on one smooth noise model. Cause attribution gives an alarm to the first fault active in the 30 min before it, so long drift labels can absorb alarms that noise alone would raise.

## Limitations that apply throughout

- **Simulated lows are the weakest part.** The 2008 model has no counter-regulation. Virtual patients treat lows at the same cut-offs the alarms use (≤55 mg/dL at night, <70 by day), which shapes how deep and how long simulated lows are.
- **The cohort is small and smooth.** It has 30 virtual patients and one smooth sensor-noise model. Results describe this cohort, not people with diabetes.
- **No real compression is labelled.** The real-data tracks inject artifacts into real CGM. Their lows caught is near-circular, because the reference lows come from the same CGM; only the injected-compression false alarms are informative.
- **Some inputs are unverified.** The PISA model's time constant and the realistic PISA frequency come from abstracts (Facchinetti 2016, Lobo 2026). Clinical review of thresholds and wording is in progress.
- **Some checks are still missing.** Thresholds are chosen on in-sample training scores ([`docs/development/REVIEW.md`](docs/development/REVIEW.md) M5; a fix is proposed in DECISIONS.md, P6).

The full list is in [`docs/RESEARCH.md`](docs/RESEARCH.md) §6.

## Run it

Requires [uv](https://docs.astral.sh/uv/); Python 3.11 is installed automatically.

```
uv sync                                                              # install, simulator included
uv run pytest -q                                                     # tests
uv run ghostlows benchmark --config experiments/configs/smoke.yaml   # end to end in a few minutes
```

**Score your own alarm.** Subclass `ghostlows.alarms.BaseAlarm` and return one score per sample from `_score_run`, using only past CGM values. It then runs through the same faults, cross-validation and scoring as the built-in alarms. [`examples/custom_alarm.py`](examples/custom_alarm.py) is tested in CI:

```
uv run ghostlows score --alarm examples/custom_alarm.py:FallingBelow70 --config experiments/configs/smoke.yaml
```

**Reproduce the results.**
- `make data data-azt1d` downloads pinned, checksummed data into `data/`; it is never committed. Licences are in [`docs/DATA.md`](docs/DATA.md).
- `make results` simulates the cohort (about 2 h), runs the real-data track and every benchmark config (hours), and regenerates `results/`.
- `make reproduce` re-runs the headline sweep in a clean checkout of the commit that produced it, from the cached cohort.

[`results/README.md`](results/README.md) says what was reproduced, and from which commits.

## Upload report

**[pkarakala.github.io/ghost-lows](https://pkarakala.github.io/ghost-lows/)** reads a Dexcom Clarity or LibreView CSV inside your browser tab. It shows the consensus metrics [Battelino 2019], the ambulatory glucose profile, daily traces, and nights with a *possible compression artifact*, with the reasons for each flag.
- **Privacy.** There is no server and no analytics; the file never leaves the tab ([`docs/PRIVACY_AND_SAFETY.md`](docs/PRIVACY_AND_SAFETY.md)).
- **How a flag is made.** A flag needs two published methods to agree and must start at night.
- **How often flags are wrong.** On simulated data, the flags catch about a third of injected artifacts and also fall on other dips, including some real lows.
- **What to do.** If you are unsure whether a low is real, check with a fingerstick and treat according to your care plan.
- **Sample data.** *Try it with sample data* shows the report for a synthetic 14-day export.

## Repository

```
src/ghostlows/  io (export and dataset loaders), metrics (consensus CGM metrics), sim (simglucose engine),
                faults (PISA, dropout, stale, drift, spikes), alarms, bench (events, scoring, CV, CIs),
                retro (upload-report flags)
experiments/    configs and scripts behind every table and figure
results/        README with every headline table; committed aggregate tables and figures
app/            the browser report (stlite / Pyodide), no server
docs/           specifications: RESEARCH, SIMULATION, BENCHMARK, DATA, PRIVACY_AND_SAFETY, CITATIONS,
                CLINICAL_REVIEW, DECISIONS; development records in docs/development/
paper.md        Journal of Open Source Software draft
```

## Cite

See [`CITATION.cff`](CITATION.cff). Results should name the benchmark version (`ghostlows-bench v1`); every run records it in `benchmark_version.txt`. A DOI per release through Zenodo is pending. Sources are in [`docs/CITATIONS.md`](docs/CITATIONS.md) and [`docs/references.bib`](docs/references.bib).

## Licence

Code: MIT (`LICENSE`). Datasets keep their own licences ([`docs/DATA.md`](docs/DATA.md)); none is redistributed here.

## How this was made

Research question: Pranav Karakala Reddy. Study design: the design decisions and amendments in `docs/DECISIONS.md` were drafted and recorded by AI agents (Claude, Anthropic) acting in a reviewer role under authority the author delegated, and were accepted by the author. Software, documentation and results text were written with AI coding agents under the author's direction: every commit carries a `Co-Authored-By: Claude` trailer, and three early commits are authored by Claude. The author reviewed the code and results, but not every line. Clinical review: Cohen Ferrari, in progress; no item in `docs/CLINICAL_REVIEW.md` has been signed off yet. See [`CONTRIBUTIONS.md`](CONTRIBUTIONS.md).
