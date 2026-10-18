# Review of the repository (2026-10-18)

A hostile-but-fair review of the kind an EMBC or Diabetes Technology Meeting referee would write, made before any Phase 2 fix. Findings are ranked blocker / major / minor; each gives the location, why it matters and the proposed fix. What was fixed afterwards, and what is left, is recorded under [Status](#status) at the end.

**Method.**
- Read the specs, results, paper and disclosures.
- Diffed every spec, config and scoring file against the tag `protocol-v1`.
- Read the per-fold `thresholds.csv` and `contrasts_h2.csv`.
- Ran the test suite: 175 passed, 3 deselected (browser, network); ruff is clean.
- Audited the code for causality, leakage, statistics, faults, units, citations, markers, app wording, reproducibility and disclosure.
- Line numbers refer to commit `fe3cd62`.

## Verdict: **major revision**
The engineering is unusually careful:
- Causality is tested over the whole alarm registry (`tests/test_alarms.py:71-92`).
- Folds are leave-patients-out, with seeds kept on the same side (`bench/stats.py:25-35`).
- Faults copy rather than mutate, and truth is tested as unchanged (`tests/test_faults.py:96-100`).
- The amendments are logged.

The main scientific claims, though, rest on one operating point with no trade-off curves. Several numbers do not mean what the prose says. The real-data track is partly circular. One CI breaks hard rule 5. The disclosure contradicts the decision log. A reviewer would also note that the whole study, from protocol tag to results, ran in about 8 hours (`git log` from 2d747dc to 028b837), and would press hard on how much was checked.

## BLOCKERS

**B1. The "threshold-free curves" required by D5 and BENCHMARK §4 are missing, so "gates switch off" and the H2 null are tied to the operating point.**
- **Where:**
  - `results/README.md:41,261` say "D5 switched the gates off or nearly off".
  - `results/figures/rq1_pisa_sweep__sensitivity_vs_false_alarms.png` draws one point per alarm, not a curve.
  - `DECISIONS.md:30` (D5) and `BENCHMARK.md:72` require threshold-free curves.
- **Evidence:**
  - At δ=0 the Baysal gate is at "no suppression" in all 5 folds, both in `thresholds.csv` and at δ=0.05.
  - The matched-filter and iForest gates match the trend reference sensitivity exactly.
  - Each lost training level-2 catch costs 1/n, so δ=0 forbids any suppression that costs even one event.
- **Why a reviewer cares:** this pre-registered output was never delivered. Without it, "the gates do nothing" and "context adds nothing" cannot be told apart from "the zero-loss constraint forbids them from doing anything".
- **Fix:**
  - Add test-fold FA/day vs level-2 sensitivity curves across thresholds for the gates and the H2 arms, with patient-bootstrap bands.
  - Add FA/day at fixed sensitivities (e.g. 0.80, 0.85, 0.90) as a threshold-free secondary estimand, labelled exploratory because it was not pre-registered as a reading rule.
  - Reword now: "at the D5 δ=0 operating point the gates were not used (thresholds.csv); see δ=0.05".
  - Needs a re-run, but changes no existing number. **Needs your OK.**

**B2. Warning-time CIs resample patient-runs, not patients (hard rule 5).**
- **Where:** `bench/analysis.py:258` passes per-run rows to `bootstrap_ci` (`stats.py:94-102`), which treats each row as a patient.
- **Effect:** 5 seeds per patient count as independent, so the CIs are too narrow. They feed the "Warning before caught level 2 lows" column (`results/README.md:45-52`) and the all-faults table.
- **Fix:** aggregate to one value per patient (the median of run medians) before bootstrapping, and re-run the aggregation only. **Changes numbers in results/, so needs your OK.**

**B3. The real-data (Weinstock) track is near-circular and presented without warning.**
- **Where:** `results/README.md:227-261`; `experiments/real_data.py:101-119,143`.
- **The circularity:**
  - The reference lows are CGM<70 or <54 for 15 min on the same CGM the alarms read.
  - Outside injected windows the two signals are identical (`faults/suite.py:286-311`).
  - So `threshold` catches 100% of level-1 lows, every alarm catches 100% of level-2 lows (CI 100–100), and `gbm` (96% L1 at 0.17 FA/day vs `trend` 89% at 0.67) is learning to predict its own input crossing 70.
- **What the track can measure validly:** only the false alarms caused by the *injected* PISAs (the compression column) and their change with PISA fraction.
- **Fix:**
  - State the circularity above the table.
  - Drop or grey out the L1/L2 "caught" columns and any ranking of alarms on real data.
  - Present the compression false alarms/day per PISA level as the only valid estimand.
  - Call it "semi-synthetic injected-artifact track", not "co-primary for RQ1", or justify co-primary for the compression column only.
  - Text-only fix; no number changes.

**B4. Upload tool: "time below range without possible compression artifacts" can drop real lows.**
- **Where:** `app/streamlit_app.py:188-205`; `retro/flags.py:191-196`; `PRIVACY_AND_SAFETY.md:24`. In simulation, a flag overlaps a real low in 37% of runs.
- **Why it blocks:** the second column is a lower, "corrected" TBR that can hide real hypoglycaemia. CR12 is unticked while the app is live.
- **Options** (the flag logic stays unchanged in every one):
  - **(a, recommended)** Replace subtraction with attribution: "Time below 70: X% (of which Y% falls inside possible compression artifacts)". This never presents a lower total and keeps the spirit of PRIVACY rule 3, but rule 3 must be reworded.
  - **(b)** Keep both columns, but never exclude readings <54 from the "without" column, and show the 37% simulation caveat next to the table.
  - **(c)** Remove the "without" column and keep flags as annotations. This needs rule 3 changed and CR12.
  - **(d)** Keep as-is behind an explicit expander with the caveat.
- All options need clinical sign-off (CR12, Cohen) before release.

**B5. The disclosure is not literally true.**
- **Where:** `README.md:124`, `CONTRIBUTIONS.md:3` and `paper.md:49` say "Research question, study design and interpretation: Pranav… Decisions: many were proposed by AI agents and accepted… the author specified, reviewed and tested all code".
- **The record says otherwise:**
  - `DECISIONS.md:3` says decisions were *made* by the "PI-role reviewer" (the AI persona, `CLAUDE.md:7`) under delegated authority.
  - The research plan, specs and citations were first committed with Claude as author (`d75fe42`, also `73f24f9`, `c4f71c7`).
  - All 47 commits carry `Co-Authored-By: Claude`, whereas `CONTRIBUTIONS.md:11` implies only some do.
  - `paper.md:53` says "much of the code".
  - Author confirmed (2026-10-18): research question by the author; study design drafted by AI agents under delegation and accepted by the author; code and results reviewed, not line by line.
- **Fix:** one accurate disclosure paragraph, used everywhere, consistent with DECISIONS.md:3. Fix the trailer sentence and paper.md:53.

## MAJOR

**M1. The A3 disclosure is inaccurate, and there is a post-A3 design change with no amendment.**
- A3 (`DECISIONS.md:52`) says the Kalman design used "the standard mix of the final cohort, including held-out results on one fold".
- In fact commit `795752b` (23:30, after A3 at 23:13) widened the Kalman noise grid after a **five-fold** held-out check. That check also computed the RQ3 comparators (gbm, gbm_ctx).
- It ran on the **pre-A6 untreated cohort** (A6 = db03c29, 00:09), not the final cohort.
- `paper.md:38` ("every later change is logged") and `CHANGELOG.md:29` ("All were made before any benchmark result on the cohort they affect") are therefore false. CHANGELOG:29 is also false for A5, which was made after a first Weinstock result showed 100% L2 catch, and for A1, which was found in a Weinstock run.
- **Fix:** add a dated correction amendment, A9, stating these facts. Correct CHANGELOG:29 and paper.md:38. RQ3 stays exploratory.

**M2. H1 is "supported" but tiny, and RQ1's real finding is unreported.**
- **H1:** the slope difference of 0.09 (0.07–0.10) FA/day per unit PISA fraction means that going from no compression to compression on *every* night adds about one extra false alarm per ~11 days for trend over threshold.
- **RQ1:** at 100% PISA nights, compression causes 0.32 (0.30–0.35) of trend's 1.53 (1.33–1.73) FA/day. Noise (0.68) and other faults (0.43) dominate. This is the most quotable result and it appears nowhere in prose.
- **Fix:** report the magnitudes in plain words, with CIs, in results/README and the README. Text only.

**M3. The treatment rule is endogenous to the alarms.**
- **Where:** `sim/engine.py:46-65`. Night treatment fires at fault-free CGM ≤55 and day treatment at <70, the same cut-offs as the floor and trend target (55) and the threshold alarm and L1 (70).
- **Effect:** true lows are truncated exactly where the alarms fire. Level-2 depth and duration, sensitivity and warning time all depend on it. Face validity agrees: simulated nadir 57 vs 47 and duration 45 vs 65 min (`results/README.md:269-270`). The rule fires about 2.5 times a day in the default mix.
- **Fix now:** add a limitation sentence.
- **Proposed amendment (needs OK):** a robustness arm with a treatment threshold decoupled from the alarm thresholds (e.g. night ≤50 or a 15-min delay).

**M4. H3 is uninformative and has a population mismatch.**
- AZT1D users are on Control-IQ (AID), but D9 defines the RQ2 target as open-loop. On the matched mix the simulation shows no benefit (`results/README.md:15,289`).
- `results/README.md:289` claims "recorded, user-entered context did not reduce compression false alarms on real nights". The artifacts were injected, not real, and gbm's CI of 0.84–1.21 cannot show "did not reduce".
- **Fix:** "On AZT1D (AID users, injected artifacts), the CIs include 1 for every detector; for gbm the CI (0.84–1.21) is too wide to exclude a modest benefit." Name the population mismatch as an H3 limitation.

**M5. Thresholds are chosen on in-sample (resubstitution) training scores.**
- **Where:** `bench/pipeline.py:142` after `:209`. GBM and the combiners are scored on the data they were fitted on.
- **Effect:** this makes the selected θ\* optimistic, which fits the test sensitivities of gbm_ctx (88%) and gbm_time_ctx (86–88%) sitting just below trend's 90%. The RQ3 "best discriminative" pick (`analysis.py:141-153`) also uses resubstitution FA/day.
- **Proposed amendment (needs OK):** out-of-fold scores (inner CV) for threshold selection. **Fix now:** state it as a limitation.

**M6. The detectors and filter know the generator.**
- The matched-filter template (`alarms/detectors.py:31-33`) and the Kalman pressure priors (`kalman_pisa.py:46-50,76-89`) come from the same PISA generator used for injection.
- The τ-mismatch arms (`robust_tau*.yaml`) exclude the Kalman alarms, and the robustness configs omit the `threshold_combined_*` and `iforest_causal_combined_*` H2 arms.
- **Proposed amendment (needs OK):** add the Kalman alarms and all H2 arms to the τ arms. **Fix now:** state the "home advantage" in the RQ3 text.

**M7. The label horizon disagrees with the code in the window robustness arms.**
- The ASSUMPTION at `bench/events.py:104` says the label horizon equals the early window. But `pipeline.py:309` and `real_data.py:143` always use 30 min, so `robust_early20`/`robust_early45` train on 30.
- **Decision needed:** either keep the training target fixed (it is a scoring-window sensitivity analysis; fix the comment, no number change) or tie it to `early_min` (re-run).
- **Recommend:** keep it fixed and fix the comment.

**M8. The reference list is not publishable.**
- `docs/references.bib` is 57 of 61 placeholder `@misc` entries (header lines 1–2: "descriptive placeholders").
- paper.bib conflicts with it:
  - Lobo2026: a different title.
  - Idi2024: year 2025.
  - Mensh2013: title.
  - Weinstock/Kovatchev: DOIs in paper.bib only.
  - AZT1Ddata: in paper.bib only.
- Code relies on sources read as abstract only (Facchinetti 2016, Lobo 2026) or marked "verify" (Battelino 2019, IHSG 2017, 21 CFR).
- **Fix:** repair from Crossref by DOI (approved). Mark DOI-less entries "verify from DOI". Never type a field from memory.

**M9. Reproducibility is overstated.**
- **Claims:** `paper.md:39` says "One command regenerates every table and figure", and ROADMAP phase 10 (`ROADMAP.md:19`) is ticked "Clean clone + make all reproduces".
- **What actually happened:**
  - PUBLICATION.md:35 admits a full clean run was never done.
  - The headline tables come from **three** commits (`4725089`, `49895a2`, `cb3d87a`), none of them v0.1.0.
  - `rq1_pisa_sweep__warning.csv` was produced by code (cb3d87a) later than its stamped commit.
  - The real-data tables carry no commit.
  - `make reproduce` needs this machine's cached cohort (`scripts/check_reproducible.py:68,126-129`).
  - The sim cache key includes the package version (`sim/run.py:65-67`): the cohort was built at 0.0.1, HEAD is 0.1.0, so a clean clone at HEAD makes a different cache key (`SIMULATION_NOTES.md:37`).
- **Fix (docs):** say exactly what was reproduced, list the per-table commits, untick or qualify phase 10's "done when", and document that `make reproduce` needs the cohort (via `make results` or the dataset release).
- **Proposed:** stamp the analysis commit and benchmark version into every table, including real-data.

**M10. The README does not meet the 2-minute bar.** It has no key results and no CIs. Limitations only appear via a link. The novelty section is long and "What this project does that is new" item 3 overclaims ("does not leak the answer"; leak AUC is still 0.63–0.69). **Fix:** restructure (Part B, C3).

**M11. Hard-coded 5-min sampling, and no DST handling, in the upload path.**
- The trend alarm needs 3 points in 15.5 min (`alarms/base.py:133,152`), so 15-min Libre 1/2 exports produce no trend alarm.
- The `retro` matched filter is also sample-indexed.
- At the DST fall-back, duplicate local times are dropped or interleaved (`metrics/consensus.py:32`, `retro/flags.py:45`).
- **Fix now:** state the limits in the app and DATA.md. Proper resampling is a follow-up.

## MINOR

- **m1. Stale cross-references:**
  - "D1–D18" though D19 exists: `RESEARCH.md:3`, `BENCHMARK.md:3`, `SIMULATION.md:3`, `SPEC_REVIEW.md:7`.
  - `ROADMAP.md:5`: "resolve open items" with every phase done.
  - `SIMULATION_NOTES.md:79`: "CR1–CR16" (CR17 exists).
  - `SIMULATION_NOTES.md:61`: says A7's level-1 fallback happens, but every fold is estimable at level 2 in all mixes (`thresholds.csv`).
  - `CLAUDE.md:36`: `experiments/run_sim.py` does not exist.
  - `BENCHMARK.md:104`: the config list omits `rq3_kalman`.
- **m2. Lobo rate inconsistent:** "1 per 73 h" (`CITATIONS.md:24`, `CLINICAL_REVIEW.md:7`) vs 74.8 h computed from the abstract (`SIMULATION.md:78`, code).
- **m3. DiaData written as used:** `ROADMAP.md:16`, `RESEARCH.md:81-82`, `SIMULATION.md:26`, `DECISIONS.md:42` (D17's TBR comparison never done). It is not used.
- **m4. `make all` vs `make results` inconsistent:** `results/README.md:3`, `PUBLICATION.md`, `BENCHMARK.md:104`, `ROADMAP.md:19` vs `README.md:69`. Also `download_data.py:14` usage omits `--azt1d`.
- **m5. Markers missing:**
  - **No `CLINICAL-REVIEW` marker at all:** 70/54 thresholds (CR6: `alarms/rules.py:10-11`, `bench/events.py:8-11`, `metrics/consensus.py:13-16`, `bench/scoring.py:204`, `sim/run.py:137-138`); CR2 (`faults/pisa.py:17-19`); CR3 (`faults/calibrate.py:16`, `kalman_pisa.py:86`); CR8 (`robust_lag6.yaml`, `pipeline.py:64`).
  - **Informal mention only:** CR9/CR16 (`bench/analysis.py:18`); CR13 (`sim/scenario.py`).
  - **Not marked at all:** CR12 in the app (`streamlit_app.py:22-26,191-193,252-254`); CR17 (`engine.py:43-46`).
  - **Docstring-only ASSUMPTIONs that the collector misses:** `learned.py:236`, `scoring.py:20`, `pisa.py:34`, `detectors.py:62`, `azt1d.py:31`.
  - **The collector lists its own docstring** (`results/tables/assumptions.md:24`).
  - **Unmarked numbers:** night window (`faults/suite.py:247`, app 20:00–08:00); `dia_h`/`cob_h` defaults (`sim/engine.py:117-118`, `sim/run.py:38-39`).
- **m6. Hard-coded assumptions** (rule 2 says they must be configurable): SESOI (`analysis.py:18,70`), refractory/flicker (`alarms/base.py:21-22,120`), `HypoTreatment` (`sim/run.py:98`), flag-rule constants (`retro/flags.py:34-39`), `LABEL_HORIZON_MIN`, `NIGHT_HOURS`, `MIN_L2_EVENTS`, `TAIL_FRACTIONS`, and the `Windows` cause/near-event bands.
- **m7. Clinical claims not mapped to a CR item:**
  - "occur mostly overnight" (`README.md:11`; app :252); "high morning glucose" (README:11); "wake people and erode trust" (`paper.md:22`, uncited in paper.bib).
  - "[clinical review]" with no ID: `RESEARCH.md:11,12`, `PRIVACY_AND_SAFETY.md:8`.
  - Regulatory claims without citation keys: `PRIVACY_AND_SAFETY.md:32-33`.
- **m8. App wording:**
  - "if a low felt real, it was worth treating" (`streamlit_app.py:192`, `README.md:45`) can be read as "a low you didn't feel can be skipped". Use the mandated fingerstick sentence instead.
  - "ghost low" in the sample answer table (`:141`) is undefined for users.
  - "readings inside the flagged nights" (`:191`) is wrong: flag *episodes* are removed (`flags.py:191-196`).
  - The fingerstick sentence appears only when flags exist (`:247-250`).
  - `README.md:9` "low glucose that is not real" (rule 7).
  - `tests/test_app_browser.py:28` does not check the "ghost" or "ignore" wording.
- **m9. Undocumented or never run:**
  - The flag survey numbers (35%/4/37%) exist only as console output (`scripts/make_sample_export.py:252-259`) and are not saved in results/.
  - The FDA-style rates are computed but never reported (`pipeline.py:251`) although BENCHMARK §4 lists them.
  - Flicker is computed and never read (`alarms/base.py:83`).
  - The Baysal parameter-set sensitivity analysis promised in BENCHMARK §2 is never run.
- **m10. Training-level leak, two smaller statistical points, and an attribution caveat:**
  - **Small cohort-level leak:** the realistic training PISA fraction is calibrated on all patients, test folds included (`pipeline.py:302-306`). It is a scalar fault-generator setting, not outcome information. Disclose it.
  - **H2 secondary has no uncertainty:** "6 of 6 detectors" (`results/README.md:14`) compares point estimates. Say so.
  - **H2's PISA level was never stated in the estimand:** the 100% comes from display code that was already there at the tag. Readings are identical at every level from 0.1 to 1.0 (`contrasts_h2.csv`). Say so in RESEARCH §3.
  - **Drift can absorb noise alarms:** long drift labels can take alarms that would otherwise be counted as noise (`faults/suite.py:139`). State the cause-attribution caveat.
- **m11. Dead code:** `VIEW_COLUMNS` and `SAMPLE_MIN` (`alarms/base.py:16-17`). Orphan scripts not reachable from the Makefile: `make_fault_figure.py`, `sim_report.py`, `package_cohort.py`. `docs/figures/faults_examples.png` is unreferenced. `experiments/pilot` needs `data/pilot`, which a clone lacks.
- **m12. Duplication:** the disclosure paragraph appears 3 times word for word; the limitations appear 3 times (one copy is auto-copied, fine); and SIMULATION.md overlaps SIMULATION_NOTES.md (spec vs as-built; keep both, but cross-link and stop restating the noise model).
- **m13. `docs/PUBLICATION.md` does not belong in a public repo.** It sets out venue strategy (JDST, JOSS) and personal action items, and promises things that don't exist (`pip install "ghostlows[bench]"`, a results page, a "four-method Alarm protocol"). Keep the citation and reproducibility-check facts, move them, and delete the file. D18 (`DECISIONS.md:43`) references it.
- **m14. Names and attribution:**
  - Git author "Pranav Reddy" vs "Pranav Karakala Reddy" elsewhere.
  - `CITATION.cff` has no clinical reviewer or ORCID.
  - Cohen Ferrari is named only in the disclosures; "clinical co-lead" is unnamed elsewhere (`README.md:116`).

## Pre-registration integrity summary
| Item | At tag | Now | Status |
|---|---|---|---|
| H1–H3 text, SESOI, D5 rule, D19, configs | fixed | unchanged except A-amendments | OK |
| A1–A8 | — | dated, reasoned | OK, but CHANGELOG:29 is false for A1/A5 |
| Kalman grid widening (795752b) | — | not logged | **silent deviation** (M1) |
| A3 "one fold, final cohort" | — | five folds, pre-A6 cohort | **inaccurate** (M1) |
| Threshold-free curves (D5, BENCH §4) | required | not produced | **undelivered** (B1) |
| FDA-style rates, Baysal parameter sets, flicker | required | computed or not run, unreported | **undelivered** (m9) |
| H2 PISA level | implicit in display code | 100% | unstated in estimand (m10) |
| Warning time | median with CI across patients | CI across runs | **deviation** (B2) |

## The five changes that most improve acceptance odds
1. **Trade-off curves and FA/day at fixed sensitivity** (B1). This turns "switch off" and the H2 null from operating-point artifacts into findings.
2. **Fix the CI unit (B2) and correct the amendment record (M1, CHANGELOG, paper).** Pre-registration credibility is the paper's selling point.
3. **Reframe the real-data track honestly (B3, M4):** only the injected-compression column is valid. State the AID population mismatch for H3.
4. **Lead with the real RQ1 result and magnitudes (M2, M10):** compression is a minor share of false alarms under this simulator, and H1's effect is tiny. Plus the treatment-rule coupling (M3) as a stated limitation, with an arm.
5. **Safety and disclosure (B4, B5):** resolve the TBR "without" column with Cohen, and make the AI disclosure match the record.

## Status

Phase 2 ran on 2026-10-18 (commits `cfd80b8`..HEAD).

**Results.**
- No number in `results/tables/` changed.
- `results/README.md` was regenerated from the committed tables. Every number in it is unchanged; only prose and derived wording were added.
- `results/tables/assumptions.md` is now regenerated from the current code.

**Tests.**
- 178 passed: 175 before, plus three new rule and default tests.
- The browser tests pass locally (`pytest -m browser`, 2 passed).
- ruff is clean.

The project lead was away for part of Phase 2. Choices made in that time are logged in [`../decisions_pending.md`](../decisions_pending.md).

### Fixed

| Finding | What changed | Commit |
|---|---|---|
| B3 | The real-data section says lows caught is near-circular and that only the compression column is informative. The column headers are marked †. | `7448bc8` |
| B5 | One accurate disclosure in the README, CONTRIBUTIONS.md and paper.md, consistent with `DECISIONS.md:3`, which was reworded. The trailer sentence now says "every commit". | `b2b9d06` |
| M1 | Amendment A9 records the post-A3 Kalman change, the five-fold check and the pre-A6 cohort. CHANGELOG and paper.md no longer claim that every change was logged beforehand. | `59f44a5`, `b2b9d06` |
| M2, M10 | The README is restructured: problem, contribution, key results with CIs, limitations, how to run. The results README gives compression's share of false alarms and the H1 effect size in plain words. | `7448bc8`, `3632757` |
| M4 | H3 text: AZT1D users are on automated insulin delivery (AID); the widest CI is named; "did not reduce" is removed. | `7448bc8` |
| M8 | All 31 DOI entries in `references.bib` now hold their registry record. Every DOI resolved to the intended paper. `paper.bib` already matched the registry. `AZT1D data 2025` was added. The other 31 entries are marked "verify before citing". | `fb543d4` |
| M9 | The generated Reproducibility section in `results/README.md` covers which commit produced which table, what `make reproduce` covers, and the cache-key caveat. ROADMAP phase 10 is qualified, and paper.md no longer says "one command". | `498ae63`, `b2b9d06` |
| M11 | DATA.md states the limits for 15-min sampling and daylight saving. The app warns on exports sampled less often than every 5 min. | `498ae63`, `47f2b67` |
| B1, B2, M3, M5, M6, M7 (text) | Each is stated where readers meet it: results README notes, and new RESEARCH.md §6 limitations. Fixes are proposed as P1–P7 (see below). | `7448bc8`, `498ae63` |
| m1–m4 | Stale cross-references fixed; the Lobo rate is 74.8 h everywhere; DiaData is described as not used; `make results` is used consistently. | `498ae63`, `fb543d4` |
| m5 | CLINICAL-REVIEW markers added for CR2, CR3, CR6/7, CR8, CR9/16, CR12, CR13 and CR17. Missing SOURCE and ASSUMPTION markers added. The collector bug is fixed. A test now checks CR ids. | `9b75f11` |
| m6 (part) | SESOI, label horizon, D10 windows and the refractory period are configurable. The defaults are pinned by a test, and a smoke run is byte-identical before and after. | `b1fc821` |
| m7 | Clinical claims in the README moved to RESEARCH.md §4, tagged CR5. Untagged "[clinical review]" markers now carry ids. The "wake people" claim in paper.md is replaced by a cited one [Shivers 2013]. | `3632757`, this commit |
| m8 | App wording: the fingerstick sentence replaces "felt real" and is shown on every report; "flagged episodes"; no "ghost low" in the sample table; the browser test forbids these phrases. | `47f2b67` |
| m11 | Unused constants removed. Makefile targets added for the orphan scripts. The faults figure is referenced from SIMULATION.md. | `5f5cec4`, `498ae63` |
| m13 | `docs/PUBLICATION.md` deleted. Its facts were moved to the README, `results/README.md` and this file. | `498ae63` |

**Correction to this review.** m10 said the H2 readings are identical at every PISA level. That holds on the default mix only. On the standard mix, `gbm`'s reading changes across levels. The generated note in `results/README.md` says so.

### Left for the project lead

**Decisions.** Proposed amendments P1–P9 in [`../DECISIONS.md`](../DECISIONS.md):

| Proposal | Changes results? |
|---|---|
| P1 patient-level warning-time CIs | yes |
| P2 threshold-free curves | yes |
| P3 the upload report's "without" column | yes |
| P4 label horizon in the window arms | — |
| P5 treatment-rule arm | yes |
| P6 out-of-fold thresholds | yes |
| P7 fuller robustness arms | yes |
| P8 per-fold training PISA level | yes |
| P9 unreported specified outputs | yes |

**Configurability not done.** `HypoTreatment` is not exposed, because exposing it would change the cohort cache key. `MIN_L2_EVENTS`, `TAIL_FRACTIONS` and the retro flag constants stay module constants (decisions_pending.md #1–2).

**Citations.**
- Unused keys: Del Favero 2014, Baysal ACC 2013, MetaboNet 2026, Glucose-ML 2025, Tidepool, Eichenlaub 2024, Kaylor 2022, US 2026/0096748. Keep or drop them.
- The 31 bib placeholders without a DOI: patents, CFR, CDC, web pages, arXiv-only benchmarks.
- The full texts of Facchinetti 2016 and Lobo 2026; the code relies on their abstracts.

**Names.** The git author is "Pranav Reddy"; elsewhere the name is "Pranav Karakala Reddy". `CITATION.cff` has no ORCID or co-authors (m14).

**Outside the repository** (moved from the deleted PUBLICATION.md):
1. Turn on the Zenodo–GitHub integration and publish a GitHub release from `v0.1.0`. Add the DOI to `CITATION.cff` and the README.
2. Confirm the CC BY 4.0 licence for `dist/ghostlows-bench-v1.zip` (`make package`). Upload it as a Zenodo dataset and add its DOI to `docs/DATA.md` and `CITATION.cff`.
3. Complete the affiliation in `paper.md`. JOSS reviews a tagged release with a DOI.
4. Request the Padova dual-sensor dataset with PISA labels [Idi 2024]. It is the only labelled real data, and the request has a long lead time.
5. Optional: mirror `protocol-v1` on OSF.

### Needs the clinical co-lead (Cohen Ferrari)

- **CR12, B4/P3:** the upload report's "without possible compression artifacts" column and the flag wording, before the next app release.
- **CR9/CR16:** the SESOI and the zero-loss cost asymmetry. Every headline result depends on that operating point.
- **CR17, M3/P5:** the treatment rule and its coupling to the alarm thresholds.
- **CR14:** whether the device's urgent-low alarm behaves like the ungated floor.
- **CR6, CR2, CR3:** thresholds and the event rule; PISA size on G6/G7; PISA frequency.
- **CR5:** the new tag on the AID rebound claim in RESEARCH.md §4.
