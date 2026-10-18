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

Simulated cohort: 30 virtual patients (UVA/Padova 2008 via simglucose), 14 days, 5 seeds, default scenario mix. 95% CIs come from a patient bootstrap and describe this cohort, not a population. Full tables: [`results/README.md`](results/README.md).

- **Compression is a minor share of false alarms (RQ1).** Even with a PISA every night, compression causes 0.32 (0.30–0.35) of the trend alarm's 1.53 (1.33–1.73) false alarms per day. Noise (0.68) and the other faults (0.43) cause more. The trend alarm catches 90% (86–93%) of level 2 lows.
- **Trend alarms degrade faster than threshold alarms (H1, supported), but only slightly.** The slope difference is 0.09 (0.07–0.10) false alarms per day per unit fraction of compressed nights: about one extra false alarm every 11 days with compression every night.
- **Context did not meaningfully reduce compression false alarms (H2).** For all six detectors, the rate ratio with versus without insulin and carb context lies between 0.94 and 1.00. For example, gradient boosting gives 0.96 (0.92–1.00) and the trend combiner 0.94 (0.90–0.96), all above the pre-registered smallest effect of interest (0.75).
- **Both findings hold at one operating point.** At the pre-registered operating point (no loss of level 2 sensitivity against the trend alarm), the published compression gates suppressed no or almost no alarms. Allowing a 5-point loss, the isolation-forest gate gives 1.27 (1.08–1.45) false alarms per day against trend's 1.39 at half of nights compressed. Curves across thresholds are not yet produced, so these results are tied to that operating point.
- **The real-data check is uninformative (H3).** On real AZT1D nights with injected artifacts, all ratios include 1. The matched simulation shows no benefit to shrink, and AZT1D users are on automated insulin delivery rather than the open-loop target population.
- **The compressed state adds nothing (RQ3, exploratory).** A Kalman filter with an explicit compressed state raises fewer false alarms than the best discriminative alarm: ratio 0.88 (0.80–0.98). The same filter without the compressed state does as well: 1.05 (0.93–1.18).

## Limitations

- **Simulated lows are the weakest part.** The 2008 model has no counter-regulation. Virtual patients treat lows at the same cut-offs the alarms use (≤55 mg/dL at night, <70 by day), which shapes how deep and how long simulated lows are.
- **The cohort is small and smooth.** It has 30 virtual patients and one smooth sensor-noise model. Results describe this cohort, not people with diabetes.
- **No real compression is labelled.** The real-data tracks inject artifacts into real CGM. Their lows caught is near-circular, because the reference lows come from the same CGM; only the injected-compression false alarms are informative.
- **Some inputs are unverified.** The PISA model's time constant and the realistic PISA frequency come from abstracts (Facchinetti 2016, Lobo 2026). Clinical review of thresholds and wording is in progress.
- **Some checks are still missing.** Thresholds are chosen on in-sample training scores, and warning-time CIs resample runs rather than patients ([`docs/development/REVIEW.md`](docs/development/REVIEW.md); fixes proposed in DECISIONS.md).

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
