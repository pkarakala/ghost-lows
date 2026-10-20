# Changelog

## Unreleased

Post-hoc amendments A10–A13 (DECISIONS.md; each logged before anything was computed). The v0.1.0 numbers stay in the tag `v0.1.0`.

- **A10: warning-time CIs resample patients.** Each patient is reduced to one value before the bootstrap (hard rule 5). Every `warning.csv` and the warning columns of `results/README.md` changed; old and new side by side in `results/tables/amendments/A10__warning_old_vs_new.csv`. Nothing else changed.
- **A11: trade-off curves** (secondary, post hoc), as D5 and BENCHMARK.md §4 require: `experiments/run_curves.py`, `results/tables/curves__*.csv`, `results/figures/curves__*.png`. The r = 1 point reproduces every v0.1.0 operating point checked.
- **A13: gates versus a retuned trend alarm at matched sensitivity** (secondary, post hoc). The finding is in [`results/README.md`](results/README.md#summary) (Summary, A13). It replaces the point-estimate "Gate or simpler threshold?" paragraph that A11 had added. `gbm` was added to the curves sweep; every existing curve row is unchanged. Outputs: `results/tables/curves__a13.csv` and `results/figures/curves__a13.png`.
- **Docs for contributors.** `AGENTS.md` holds the rules for humans and coding agents, and `CLAUDE.md` imports it. `CONTRIBUTING.md`, a pull request template and three issue templates are new. `CONTRIBUTIONS.md` is folded into the README and `docs/development/README.md`; `ROADMAP.md` (now with the one list of open items) and `decisions_pending.md` moved to `docs/development/`. The README is shorter, and `results/README.md` states each reading once. No number changed.
- **Tests.** The causality test also sets the future to a deep low and to a high, which catches an alarm that reads ahead even when its score is thresholded. The plug-in example has its own causality test, and a test checks every internal link in the docs.
- **README and paper.md** now give results in three tiers: the pre-registered tests, then the post-hoc curves, then the descriptive compression share. Each claim carries its limitations.
- **A12: the upload report never lowers a number with a flag.** The "without possible compression artifacts" column is gone; flags are annotations and a count, with their measured performance in plain words (`results/tables/flag_survey.json`). Awaiting clinical sign-off (CR12) before the next app release.
- **Upload report: Try it with sample data.** A synthetic 14-day Clarity-format export (`app/sample_clarity_export.csv`, from `scripts/make_sample_export.py`). It is one simulated benchmark run with injected compression artifacts and a real nocturnal low. It shows under a banner saying it is synthetic, with what really happened (which flags fall on injected artifacts, and the true glucose), and can be downloaded.
- **How the flags do on simulated data** (PRIVACY_AND_SAFETY.md): 35% of injected PISAs flagged; a median of 4 other flags per 14 days; in 37% of runs a flag overlaps a real low. The README no longer calls the flags "deliberately conservative" without these numbers.

## v0.1.0 (2026-10-18)

The first complete release of the benchmark (`ghostlows-bench v1`). Results: [`results/README.md`](results/README.md).

### What is in it

- **Data I/O and metrics:** loaders for Dexcom Clarity and LibreView exports, GlucoBench and AZT1D into one schema; consensus CGM metrics and the AGP.
- **Simulation:** a minute-by-minute engine on simglucose's 30 virtual patients. Plasma glucose is the truth. An open-loop basal-bolus controller is calibrated per patient. Three scenario mixes vary how much recorded insulin explains. Virtual patients treat lows with the 15-15 rule (amendment A6).
- **Fault suite:** PISA (compression) from the Facchinetti 2016 model, plus dropout, stale readings, drift and spikes. Common random numbers make severity sweeps nested. Faults never touch truth.
- **Alarms:**
  - 30 pre-registered alarms: threshold, trend, the urgent-low floor, three published PISA gates as causal adaptations, learned combiners with and without time of day and insulin/carb context, and gradient boosting.
  - A stretch, multiple-model Kalman filter with a compressed state, with two ablations (RQ3).
  - A plug-in interface for new alarms.
- **Scoring and statistics:** events, matching windows, false alarms by cause, leave-patients-out cross-validation, the pre-registered operating point (D5), patient-bootstrap CIs, and the H1–H3 and RQ3 contrasts. Fold fits run in parallel with identical results.
- **Real-data track:** PISAs injected into real nights (Weinstock 2016, co-primary for RQ1), the H3 context check on AZT1D (Control-IQ users, user-entered context only), and face validity of simulated lows.
- **Upload report:** <https://pkarakala.github.io/ghost-lows/>. It runs in the browser with no server, flags a *possible compression artifact* conservatively, and keeps the file in the tab.
- **Reproducibility:** pinned, checksummed downloads; `make results`; `make reproduce`, which reruns the headline tables in a clean checkout of the commit that produced them. That check reproduced them exactly on 2026-10-18 (`results/README.md`, Reproducibility). A packaged frozen cohort for a dataset release (`scripts/package_cohort.py`).
- **Paper:** a JOSS draft (`paper.md`) that builds in CI.

### Amendments after the pre-registration tag `protocol-v1`

All are logged with dates, evidence and reasons in [`docs/DECISIONS.md`](docs/DECISIONS.md). *Corrected 2026-10-18:* this list first said all were made before any benchmark result on the cohort they affect. That is not true of A1, which was found in a first run of the Weinstock real-data track, or of A5, which was made after that run. A9 records a change to the Kalman filter that was not logged at the time.

- A1: the published gates are tuned by the operating-point rule, as D5 specifies. Before this, two of them never suppressed an alarm.
- A2: finer candidate thresholds in the range where low alarms operate.
- A3: RQ3 is operationalised as exploratory, with a comparator chosen on training patients, and the Kalman filter's development data is disclosed.
- A4: the H3 matching and reading rule.
- A5: the real-data operating point matches level-1 sensitivity, because the floor catches every CGM-referenced level-2 low.
- A6: virtual patients treat their lows. Without treatment the first cohort reached plasma glucose near 0 mg/dL.
- A7: folds with few level-2 lows match level-1 sensitivity and are flagged.
- A8: gradient boosting is included in the H2 contrasts.

### Known limitations and open items

See `docs/RESEARCH.md` §6, and the open items in `docs/development/ROADMAP.md`:
- **Full texts:** Facchinetti 2016 and Lobo 2026 were read as abstracts only.
- **Labelled data:** no public data labels real compression.
- **Clinical review:** items CR1–CR17 are still to be checked by a clinician.
- **DOIs:** the Zenodo DOI and the dataset record need the project lead (`docs/development/REVIEW.md`, Status).
