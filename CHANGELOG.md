# Changelog

## v0.4.0 (2026-10-28)

An audit, publication figures, shorter docs in two layers, more precise archive metadata and a release workflow. No number in `results/` changes, and the benchmark is still `ghostlows-bench v1`.

- **Audit** (`docs/development/AUDIT_2026-10.md`). A second hostile review of the code, tests and statistics, with 18 findings ranked by severity. Seven fixes, each with a regression test and none changing a result:
  - learned alarms with no lows in training no longer fire;
  - `low_events` no longer joins readings across a gap;
  - an interrupted simulation is no longer reused without its event logs, nor packaged;
  - an alarm that never fires keeps its lows in the sensitivity denominator;
  - the D5 reference alarm uses the configured refractory period;
  - provenance records uncommitted changes;
  - a docstring states the right redraw share.

  Draft amendments P10–P13 report the findings that would change numbers, for the project lead to accept or reject.
- **Figures.** `make figures` draws five publication figures from the committed tables into `results/figures/` (SVG, PDF and PNG, one shared style), plus a 1280 x 640 social preview in `docs/figures/`. Each figure gets a one-sentence caption in `results/README.md`, generated from the same tables. The robustness figures move to `results/figures/appendix/`. Tests check that every listed figure exists and that `results/README.md` is exactly what its generator writes.
- **Docs in two layers.**
  - For people: the README is 350 words and gains a Cite section. `docs/SUMMARY.md` corrects a caption, since `floor_only` gets more false alarms from compression than from any other cause, and gives the A13 caveats. CONTRIBUTING adds the docs-preservation check and stays under 500 words.
  - For AI agents: `AGENTS.md` is the one agent-neutral source of rules, and `CLAUDE.md`, `GEMINI.md` and `.github/copilot-instructions.md` point to it.
  - A test checks that the AI usage disclosure is one text in its three places.
- **Archive metadata.**
  - `.zenodo.json` and `CITATION.cff` lead with the problem and the finding.
  - Keywords give US and UK spellings.
  - Both link the upload report, the specifications and the results.
  - The Zenodo record's language is English. Python is a keyword, since Zenodo's language field takes only a natural language.
  - [`docs/development/RELEASE_CHECKLIST.md`](docs/development/RELEASE_CHECKLIST.md) lists the release steps done by hand.
- **Release workflow.** Pushing a `vX.Y.Z` tag, or running `.github/workflows/release.yml` by hand on `main` with the version, publishes the GitHub Release with its CHANGELOG entry as the notes. It refuses a version that does not match `src/ghostlows/__init__.py` and `CITATION.cff`, or that has no CHANGELOG entry.

## v0.3.0 (2026-10-27)

An installable package with a small public API. No benchmark definition or number in `results/` changes.

- **Public API.** `import ghostlows` exposes what a user needs, listed in `ghostlows.__all__`: `load_clarity`, `load_libreview`, `load_export` and `sample_export`; `apply_faults` and `FaultConfig`; `Alarm`, `BaseAlarm`, `FloorOnlyAlarm`, `ThresholdAlarm`, `TrendAlarm` and `benchmark_alarms`; `low_events`, `score_alarm` and `Windows`; `summary` and `agp`. `score_alarm` is the benchmark's own scoring (`fire_and_score` moved unchanged from `bench/pipeline.py` to `bench/scoring.py`). Each public name has a docstring with inputs, units and returns; the package ships `py.typed`.
- **Core install works on its own.** `ghostlows.alarms` imported scipy at module level, so the numpy/pandas wheel could not import `TrendAlarm`; scipy is now imported where it is used. A test fails if `import ghostlows` loads an optional extra. The wheel includes the synthetic sample export.
- **Quick start.** [`examples/quickstart.py`](examples/quickstart.py) loads the sample, adds compression artifacts, runs the trend alarm and prints lows caught, false alarms per day and warning time. CI runs it from the repository and from fresh installs of the core wheel and of `[bench,sim]`. The README has a "Use as a library" section.
- **One version source.** The version lives in `src/ghostlows/__init__.py` (hatch dynamic version); a test checks `CITATION.cff` matches.
- **Cohort cache key.** It covers the simulation inputs only (config, calibration file, simglucose version, `SIM_CODE`), not the ghostlows version. The key changes once now, so the next `make results` simulates the cohort again (about 2.3 h); after that, releases reuse it.
- **Packaging.** `ghostlows --help` says what the commands need, and they stop with one line when an extra is missing. The sdist holds only what builds the wheel; `twine check --strict` passes. A PyPI workflow with trusted publishing is in place but disabled (steps in `docs/reference/ENGINEERING.md`, Package).
- **Hygiene.** `plotly` (declared, never imported) and `ratio_of_sums` (used only by a test) are removed; `uvx deptry .` passes.
- **Authors, affiliation and licence notice.** Authors are Pranav Reddy and Cohen Ferrari, co-authors with equal contribution (University of California, Santa Barbara), in `CITATION.cff`, `.zenodo.json`, `pyproject.toml`, `paper.md` (`equal-contrib`), `paper.bib` and the disclosure. The README and `paper.md` add: "Independent project by UCSB students; not funded or endorsed by UCSB." The licence is still MIT. Its copyright line names both authors, and the medical-device warning moved out of `LICENSE` (it stays in the README) so GitHub detects the licence as MIT. New `.zenodo.json` sets the Zenodo record's metadata; a test keeps it in line with `CITATION.cff`.
- **Known staleness.** `results/tables/assumptions.md` lists source line numbers, which moved by a few lines in four files. It was not regenerated, so that no number in `results/` changes. It refreshes the next time results are regenerated.

## v0.2.3 (2026-10-22)

v0.2.3: first Zenodo-archived release; includes any changes since v0.2.2. There are none besides the version: no code behaviour, documentation, number in `results/` or benchmark definition changes. Earlier releases were not archived on Zenodo.

- **New cohort cache key.** The key includes the package version, so at 0.2.3 `make results` simulates the cohort afresh (about 2.3 h).

## v0.2.2 (2026-10-22)

Who reviews the clinical claims, stated correctly. No code behaviour, number in `results/` or benchmark definition changes.

- **Reviewer role corrected.** Cohen Ferrari is a pre-med student, not a clinician. The disclosure in the README, `paper.md` and `docs/development/README.md` now reads "Literature fact-check: Cohen Ferrari (in progress). Clinical review: none yet." The roadmap's owner for clinical review is "a clinician (unassigned)". Amendment A12 in [`docs/reference/DECISIONS.md`](docs/reference/DECISIONS.md) carries a dated correction: CR12 needs a clinician's sign-off.
- **Two sign-offs per clinical claim.** Each item in [`docs/CLINICAL_REVIEW.md`](docs/CLINICAL_REVIEW.md) has "Literature checked (name, date)" and "Clinician reviewed (name, role, date)". A factual item closes on the literature check; CR9, CR12, CR16 and CR17 are clinical judgments and need both. `tests/test_repo_rules.py` checks the format, the closing rule and which items need a clinician; [`CONTRIBUTING.md`](CONTRIBUTING.md) and the Clinical correction issue template ask which kind of review it is.
- **Docs check.** `scripts/check_docs_preserved.py` lists reviewed changes (`INTENDED`) and reports them as changed on purpose instead of lost; the first is the CR12 text, which no longer names Cohen Ferrari as its reviewer.
- **New cohort cache key.** The key includes the package version, so at 0.2.2 `make results` simulates the cohort afresh (about 2.3 h).

## v0.2.1 (2026-10-22)

Documentation in two layers, a corrected H2 line and rewritten contributor files. No result changed: no code behaviour, number in `results/` or benchmark definition changes, and the benchmark is still `ghostlows-bench v1`.

- **For people.** [`README.md`](README.md) is under 330 words (299 before the H2 wording fix added a finding and a limitation). [`docs/SUMMARY.md`](docs/SUMMARY.md) gives the results on one page for clinicians. [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`docs/PRIVACY_AND_SAFETY.md`](docs/PRIVACY_AND_SAFETY.md) are under 500 words. [`docs/CLINICAL_REVIEW.md`](docs/CLINICAL_REVIEW.md) keeps every CR item word for word.
- **H2 wording fix.** The README and SUMMARY gave the best H2 ratio as 0.94 (0.90–0.96), which is the trend alarm on the default mix. They now say that none met the 25% bar; the best was gradient boosting on the standard mix, 0.82 (0.74–0.89), inconclusive, as [`results/README.md`](results/README.md) always had it. Both also state the post-hoc A11/A13 finding (published compression detectors cut compression false alarms only by missing severe lows, and none beat a less sensitive trend alarm), and the README lists the near-circular real-data checks as a limitation.
- **Reference.** The six specifications move to [`docs/reference/`](docs/reference/), unchanged. New there: `ENGINEERING.md` (the full rules and engineering detail from AGENTS.md and CONTRIBUTING.md) and `UPLOAD_REPORT.md` (the upload report as implemented, from PRIVACY_AND_SAFETY.md).
- **AGENTS.md** is a map for a researcher's AI assistant: folders, reading order, which table answers which question, the 11 hard rules (same numbers) and the commands.
- **AI usage disclosure**, the same text in the README, `paper.md` and `docs/development/README.md`. New commits carry no `Co-Authored-By` trailer (`.claude/settings.json`); history is not rewritten.
- `scripts/check_docs_preserved.py` checks that no number, citation key, CR item, limitation or safety sentence was lost against a git ref.
- `CITATION.cff` gives the author's ORCID.
- **New cohort cache key.** The key includes the package version, so at 0.2.1 `make results` simulates the cohort afresh (about 2.3 h).

## v0.2.0 (2026-10-19)

Amendments A9–A13, an upload report that never lowers a number with a flag, and documentation for contributors. The benchmark is still `ghostlows-bench v1`. The H1–H3 and RQ3 results are unchanged: A10 changed the warning-time estimates and CIs, and A11 and A13 add secondary results. The v0.1.0 numbers stay in the tag `v0.1.0`.

### Amendments A9–A13

All are post hoc and logged with dates and reasons in [`docs/reference/DECISIONS.md`](docs/reference/DECISIONS.md). A9 corrects a disclosure; A10–A13 were each logged before anything was computed.

- **A9: the Kalman filter's development, disclosed in full** (corrects A3). A five-fold held-out check on the standard mix widened the filter's noise grid and also scored the RQ3 comparators `gbm` and `gbm_ctx`; it was not logged at the time. It ran on the untreated cohort that A6 replaced. RQ3 stays exploratory, and no result changes.
- **A10: warning-time CIs resample patients.** Each patient is reduced to one value before the bootstrap (hard rule 5). Every `warning.csv` and the warning columns of `results/README.md` changed; old and new side by side in `results/tables/amendments/A10__warning_old_vs_new.csv`. Nothing else changed.
- **A11: trade-off curves** (secondary, post hoc), as D5 and BENCHMARK.md §4 require: `experiments/run_curves.py`, `results/tables/curves__*.csv`, `results/figures/curves__*.png`. The r = 1 point reproduces every v0.1.0 operating point checked.
- **A12: the upload report never lowers a number with a flag.** The "without possible compression artifacts" column is gone; flags are annotations and a count, with their measured performance in plain words (`results/tables/flag_survey.json`). Live since 2026-10-19; the CR12 sign-off of its wording by Cohen Ferrari is still open.
- **A13: gates versus a retuned trend alarm at matched sensitivity** (secondary, post hoc). The finding is in [`results/README.md`](results/README.md#summary) (Summary, A13). It replaces the point-estimate "Gate or simpler threshold?" paragraph that A11 had added. `gbm` was added to the curves sweep; every existing curve row is unchanged. Outputs: `results/tables/curves__a13.csv` and `results/figures/curves__a13.png`.

### Other changes

- **Upload report: Try it with sample data.** A synthetic 14-day Clarity-format export (`app/sample_clarity_export.csv`, from `scripts/make_sample_export.py`). It is one simulated benchmark run with injected compression artifacts and a real nocturnal low. It shows under a banner saying it is synthetic, with what really happened (which flags fall on injected artifacts, and the true glucose), and can be downloaded.
- **How the flags do on simulated data** (PRIVACY_AND_SAFETY.md): 35% of injected PISAs flagged; a median of 4 other flags per 14 days; in 37% of runs a flag overlaps a real low. The README no longer calls the flags "deliberately conservative" without these numbers.
- **README and paper.md** now give results in three tiers: the pre-registered tests, then the post-hoc curves, then the descriptive compression share. Each claim carries its limitations.
- **Docs for contributors.** `AGENTS.md` holds the rules for humans and coding agents, and `CLAUDE.md` imports it. `CONTRIBUTING.md`, a pull request template and three issue templates are new. `CONTRIBUTIONS.md` is folded into the README and `docs/development/README.md`; `ROADMAP.md` (now with the one list of open items) and `decisions_pending.md` moved to `docs/development/`. The README is shorter, and `results/README.md` states each reading once. No number changed.
- **Clinical sign-off.** A ticked clinical review item ends with the reviewer's name and the date ([how](CONTRIBUTING.md#review-a-clinical-claim)).
- **Dataset card.** `scripts/package_cohort.py` copies its limitations verbatim from `docs/reference/RESEARCH.md` §6, instead of its own three-bullet summary.
- **Tests.** The causality test also sets the future to a deep low and to a high, which catches an alarm that reads ahead even when its score is thresholded. The plug-in example has its own causality test, and a test checks every internal link in the docs. Tests also check that the dataset card's limitations match `docs/reference/RESEARCH.md` §6 and that every ticked clinical review item is signed off.
- **New cohort cache key.** The key includes the package version, so at 0.2.0 `make results` simulates the cohort afresh (about 2.3 h; [`results/README.md`](results/README.md#reproducibility)), and `make package` needs that new cohort.

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

All are logged with dates, evidence and reasons in [`docs/reference/DECISIONS.md`](docs/reference/DECISIONS.md). *Corrected 2026-10-18:* this list first said all were made before any benchmark result on the cohort they affect. That is not true of A1, which was found in a first run of the Weinstock real-data track, or of A5, which was made after that run. A9 records a change to the Kalman filter that was not logged at the time.

- A1: the published gates are tuned by the operating-point rule, as D5 specifies. Before this, two of them never suppressed an alarm.
- A2: finer candidate thresholds in the range where low alarms operate.
- A3: RQ3 is operationalised as exploratory, with a comparator chosen on training patients, and the Kalman filter's development data is disclosed.
- A4: the H3 matching and reading rule.
- A5: the real-data operating point matches level-1 sensitivity, because the floor catches every CGM-referenced level-2 low.
- A6: virtual patients treat their lows. Without treatment the first cohort reached plasma glucose near 0 mg/dL.
- A7: folds with few level-2 lows match level-1 sensitivity and are flagged.
- A8: gradient boosting is included in the H2 contrasts.

### Known limitations and open items

See `docs/reference/RESEARCH.md` §6, and the open items in `docs/development/ROADMAP.md`:
- **Full texts:** Facchinetti 2016 and Lobo 2026 were read as abstracts only.
- **Labelled data:** no public data labels real compression.
- **Clinical review:** items CR1–CR17 are still to be checked by a clinician.
- **DOIs:** the Zenodo DOI and the dataset record need the project lead (`docs/development/REVIEW.md`, Status).
