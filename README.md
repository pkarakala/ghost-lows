# Ghost Lows

Continuous glucose monitors (CGMs) sometimes report lows that are not there. The best-documented cause is pressure on the sensor during sleep, a **pressure-induced sensor attenuation (PISA)** or compression low [Mensh 2013; Facchinetti 2016], which causes false overnight alarms [Shivers 2013] and, inside automated insulin delivery, needless insulin suspensions [Baysal 2014].
Published compression detectors were each scored on their own data and metrics, mostly retrospectively ([prior work](docs/RESEARCH.md#4-what-is-new-and-why)). Ghost Lows is an open benchmark that scores real-time low alarms on *lows caught*, *false alarms per day* (split by cause) and *minutes of warning* as a mixed fault suite gets worse: compression from the published PISA model [Facchinetti 2016], dropout, stale readings, drift and spikes. Faults never touch the reference glucose.
It also measures what insulin and carb context adds to six published detectors, and ships a browser-only report for Dexcom Clarity and LibreView exports. The benchmark is the contribution, not a new detector.

> **Not a medical device. Not for treatment decisions.** This is research software. Nothing it produces should be used to decide whether to treat, ignore or silence a low glucose reading. If a reading looks wrong, confirm with a fingerstick and follow your care team's advice.

## Key results

`ghostlows-bench v1`, simulated: 30 virtual patients (UVA/Padova 2008 via simglucose), 14 days, 5 seeds; default scenario mix unless stated. 95% CIs come from a patient bootstrap and describe this cohort, not a population. "Severe lows" are level 2 lows (below 54 mg/dL for 15 min). H1–H3 were pre-registered in the git tag `protocol-v1`; every later change is a dated amendment in [`docs/DECISIONS.md`](docs/DECISIONS.md). Full tables: [`results/README.md`](results/README.md).

- **Primary (pre-registered).** **H1, supported but small:** trend alarms degrade faster than threshold alarms by 0.09 (0.07–0.10) false alarms per day per unit fraction of compressed nights, about one extra every 11 days with compression every night. **H2, null:** at the frozen operating point (no loss of severe-low sensitivity against the trend alarm), compression false alarms with versus without insulin and carb context give rate ratios of 0.94–1.00 for all six detectors (gradient boosting 0.96 (0.92–1.00), trend combiner 0.94 (0.90–0.96)), above the pre-registered smallest effect of interest, 0.75; there the published gates suppressed no or almost no alarms. **H3, uninformative:** on real AZT1D nights with injected artifacts every ratio includes 1, and the matched simulation has no benefit to shrink. **RQ3, exploratory:** a Kalman filter with an explicit compressed state raises fewer false alarms than the best discriminative alarm, 0.88 (0.80–0.98), but no fewer than itself without that state, 1.05 (0.93–1.18).
- **Secondary (post hoc, amendments A11 and A13, defined after the v0.1.0 results had been seen).** Along each published gate's curve, compression false alarms fall only once severe lows are given up: the Baysal gate's first clear reduction, to 0.89 (0.81–0.96) times as many, costs 11 more missed severe lows of 249. The H2 reading is unchanged when 1% or 5% of the trend alarm's training sensitivity is given up. No published gate gave fewer total false alarms than the retuned trend alarm at any estimable point; the isolation-forest and Baysal gates gave more at most (6 of 8 and 2 of 3). Comparisons are at matched held-out sensitivity (an oracle, not a deployable operating point), cover 18 of 60 planned points, are uncorrected for multiplicity and say nothing about the standard mix. The matched-filter gate could not be compared (its curve reaches only 3 of its 15 planned points, all unstable). CGM-only gradient boosting shifted false alarms between causes: fewer from compression (0.50–0.66 times the retuned trend alarm's, at 7 of its 7 points) with no detectable change in the total (ratios 0.81–1.08, every CI including 1).
- **Descriptive (RQ1).** Even with a PISA every night, compression causes 0.32 (0.30–0.35) of the trend alarm's 1.53 (1.33–1.73) false alarms per day, about 21%; noise (0.68) and the other faults (0.43) cause more. The trend alarm catches 90% (86–93%) of severe lows.

## Limitations

Each bullet names the results it bounds. The full list is [`docs/RESEARCH.md`](docs/RESEARCH.md) §6.

- **Simulated lows are the weakest part (all).** The 2008 model has no counter-regulation, and virtual patients treat lows at the alarms' own cut-offs (≤55 mg/dL at night, <70 by day). That shapes how deep and how long simulated lows are, and so the alarms' sensitivity.
- **A small, smooth cohort (all).** 30 virtual patients and one smooth sensor-noise model. Results describe this cohort, not people with diabetes.
- **Fault inputs from abstracts (H1, RQ1).** The PISA model's time constant and the realistic PISA frequency come from abstracts (Facchinetti 2016, Lobo 2026). The compression share also depends on the assumed PISA shape.
- **One operating point (H2).** Its cost asymmetry awaits clinical review (CR9, CR16). Thresholds are chosen on in-sample training scores ([review](docs/development/REVIEW.md) M5; proposed fix P6 in DECISIONS.md).
- **A narrow insulin "leak" (H2, H3).** In a standard simulator, insulin causes every low. Here unannounced exercise, sensitivity changes and meal errors make some lows less predictable from recorded insulin, but the three scenario mixes span a leak AUC of only 0.63–0.69.
- **No labelled real compression (H3).** The real-data tracks inject artifacts into real CGM. Lows caught there is near-circular, because the reference lows come from the same CGM; only the injected-compression false alarms are informative. AZT1D users are on automated insulin delivery, not the open-loop target population.
- **Home advantage (RQ3).** The Kalman filter's pressure mode uses the PISA model that generates the injected artifacts, and its design was tuned with held-out checks on the standard mix (amendments A3, A9).
- **Cause attribution (RQ1).** A false alarm goes to the first fault active in the 30 min before it, so long drift labels can absorb alarms that noise alone would raise.
- **Clinical review of thresholds and wording is in progress** ([`docs/CLINICAL_REVIEW.md`](docs/CLINICAL_REVIEW.md)).

## Quick start

Requires [uv](https://docs.astral.sh/uv/); Python 3.11 is installed automatically.

```
uv sync                                                              # install, simulator included
uv run pytest -q                                                     # tests
uv run ghostlows benchmark --config experiments/configs/smoke.yaml   # end to end in a few minutes
```

**Score your own alarm.** A plug-in alarm runs through the same faults, cross-validation and scoring as the built-in ones. [`examples/custom_alarm.py`](examples/custom_alarm.py) is a 20-line example, tested in CI; see [Add an alarm](CONTRIBUTING.md#add-an-alarm).

**Reproduce the results.**
- `make data data-azt1d` downloads pinned, checksummed data into `data/`; it is never committed. Licences are in [`docs/DATA.md`](docs/DATA.md).
- `make results` simulates the cohort (about 2 h), runs the real-data track and every benchmark config (hours), and regenerates `results/`.
- `make reproduce` re-runs the headline sweep in a clean checkout of the commit that produced it, from the cached cohort. [`results/README.md`](results/README.md#reproducibility) says what was reproduced, and from which commits.

**Upload report.** [pkarakala.github.io/ghost-lows](https://pkarakala.github.io/ghost-lows/) reads a Dexcom Clarity or LibreView CSV inside your browser tab. It shows the consensus metrics [Battelino 2019], the ambulatory glucose profile, daily traces, and nights with a *possible compression artifact*, with the reasons for each flag. *Try it with sample data* uses a synthetic 14-day export.
- **Privacy.** No server and no analytics; the file never leaves the tab ([`docs/PRIVACY_AND_SAFETY.md`](docs/PRIVACY_AND_SAFETY.md)).
- **How a flag is made.** Two published methods must agree, and the flag must start at night.
- **How often flags are wrong.** On simulated data, the flags catch about a third of injected artifacts and also fall on other dips, including some real lows.
- **What to do.** If you are unsure whether a low is real, check with a fingerstick and treat according to your care plan.

## Where to look

| You are | Start with | Then |
|---|---|---|
| An engineer adding an alarm or a fault | [CONTRIBUTING.md](CONTRIBUTING.md) | [AGENTS.md](AGENTS.md) (rules, layout), [BENCHMARK.md](docs/BENCHMARK.md) (alarms, metrics, statistics), [SIMULATION.md](docs/SIMULATION.md) (simulator, faults) |
| A researcher checking a claim | [results/README.md](results/README.md) | [RESEARCH.md](docs/RESEARCH.md) (questions, hypotheses, limitations), [DECISIONS.md](docs/DECISIONS.md) (decisions, amendments), [DATA.md](docs/DATA.md) |
| A clinician | [CLINICAL_REVIEW.md](docs/CLINICAL_REVIEW.md) (the claims to check) | [How to review one](CONTRIBUTING.md#review-a-clinical-claim), [PRIVACY_AND_SAFETY.md](docs/PRIVACY_AND_SAFETY.md) (the upload report's rules) |
| A coding agent | [AGENTS.md](AGENTS.md) | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Citing the work | [CITATION.cff](CITATION.cff) | [CITATIONS.md](docs/CITATIONS.md) (sources), [DATA.md](docs/DATA.md) (dataset licences) |

## How this was made

Research question: Pranav Karakala Reddy. Study design: the design decisions and amendments in `docs/DECISIONS.md` were drafted and recorded by AI agents (Claude, Anthropic) acting in a reviewer role under authority the author delegated, and were accepted by the author. Software, documentation and results text were written with AI coding agents under the author's direction: every commit carries a `Co-Authored-By: Claude` trailer, and three early commits are authored by Claude. The author reviewed the code and results, but not every line. Clinical review: Cohen Ferrari, in progress; no item in `docs/CLINICAL_REVIEW.md` has been signed off yet. Development records: [`docs/development/`](docs/development/).

## Licence and citation

Code: MIT ([`LICENSE`](LICENSE)). Datasets keep their own licences ([`docs/DATA.md`](docs/DATA.md)); none is redistributed here. Cite the software with [`CITATION.cff`](CITATION.cff). Results should name the benchmark version (`ghostlows-bench v1`); every run records it in `benchmark_version.txt`. A DOI per release through Zenodo is pending. Sources are in [`docs/CITATIONS.md`](docs/CITATIONS.md) and [`docs/references.bib`](docs/references.bib).
