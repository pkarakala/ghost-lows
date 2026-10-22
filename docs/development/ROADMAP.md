# Roadmap

The phase plan the software was built from, and the items still open; for maintainers. Each phase ended with passing tests and a commit. Phases 0 to 8 are the end-to-end core; phase 9 is a stretch.

Every phase is done. The spec review that preceded them is [`SPEC_REVIEW.md`](SPEC_REVIEW.md); the review of the finished repository, with what is still open, is [`REVIEW.md`](REVIEW.md).

| Phase | Goal | Done when |
|---|---|---|
| **0. Scaffold** (done 2026-10-18) | `pyproject.toml` (Python 3.11, uv), `src/ghostlows/`, ruff, pytest, GitHub Actions CI, `scripts/download_data.py`, `.gitignore` | `uv run pytest` passes on an empty test; CI green; GlucoBench data downloads with a manifest |
| **1. Data I/O and metrics** (done 2026-10-18) | Loaders for GlucoBench CSVs, Dexcom Clarity, LibreView into the common schema (DATA.md §3). Consensus metrics: mean, SD, CV, GMI, TIR 70–180, TBR <70 and <54, TAR >180 and >250, wear %, AGP percentiles [Battelino 2019] | Hand-made Clarity and LibreView fixtures parse; metrics match hand-computed values on a fixture; GlucoBench files load with row counts logged |
| **2. Simulation** (done 2026-10-18) | simglucose wrapper: plasma truth + interstitial + 5-min CGM (D1), 30 patients, rewritten open-loop basal-bolus controller with per-patient calibration (D17), scenario families and the three mixes (SIMULATION.md §3, D3), IOB/COB from recorded events, Parquet cache | `python -m ghostlows.sim --config experiments/configs/sim_smoke.yaml` produces 2 patients × 2 days; full config runs 30 patients × 14 days; calibrated cohort within the TBR band; leak AUC reported per mix; `docs/SIMULATION_NOTES.md` written |
| **3. Fault suite** (done 2026-10-18) | PISA (Facchinetti model, realised-size parametrisation, two-piece log-normal), dropout, stale, drift, spikes; `FaultSuite` with severity; labels per sample; mismatch-arm generator (D8) | Test: depth/duration quantiles *measured on generated traces* match the paper's medians and 5th/95th percentiles within tolerance; faults never change `truth_glucose`; plot of example faults saved |
| **4. Alarms** (done 2026-10-18) | `threshold`, `trend`, `baysal_gate`, `matched_filter_causal_gate`, `iforest_causal_gate`, `gbm`, the urgent-low floor (D4) and the four context arms through one combiner (D2) (BENCHMARK.md §1–2) | Causality test (future data cannot change past scores) passes for every alarm; each alarm has a unit test on a synthetic trace; the floor is never suppressed |
| **5. Scoring** (done 2026-10-18) | Event detection (D11), matching (D12), metrics incl. false alarms split by cause (D10), leak AUC, FDA-style rates, flicker; leave-patients-out CV; operating-point rule (D5); patient-level bootstrap CIs; `ghostlows` CLI and a tested plug-in alarm example (D18) | Scoring tests on hand-built traces with known answers; `run_benchmark.py` runs end to end on the smoke config; the example alarm scores in CI |
| **6. Experiments (RQ1, RQ2)** (done 2026-10-18) | Tag `protocol-v1` before the full run; severity sweeps; factorial context ablation at the pre-registered operating point on the three mixes; robustness arms (lag, generator mismatch, windows, δ); figures and `results/README.md`; frozen cohort `ghostlows-bench v1` packaged for Zenodo | All tables/figures regenerate from one command; assumptions file auto-generated |
| **7. Real-data track** (done 2026-10-18) | Co-primary semi-synthetic track: PISAs injected into real nights (Weinstock; DiaData raw, deduplicated, is not used yet) (D16); face validity of simulated lows vs. real CGM; real-data context check on AZT1D with user-entered boluses/carbs (H3) | Real-data results table with dataset citations; face-validity figure; clear statement of what is and is not labelled |
| **8. Upload dashboard** (done 2026-10-18; [live](https://pkarakala.github.io/ghost-lows/)) | `ghostlows.retro` (possible compression artifact flags using published CGM-only methods) + stlite app in `app/`, deployed to GitHub Pages | Uploading a fixture Clarity CSV in a browser shows metrics, AGP, daily traces, flags with reasons, TBR with and without flags (since A12: TBR from all readings, flags as annotations with their measured performance), and the disclaimers in PRIVACY_AND_SAFETY.md; no network requests carry user data |
| **9. Stretch: RQ3** (done 2026-10-18) | `kalman_pisa`: Kalman/HMM with explicit compressed state + insulin/meal inputs | Benchmarked like every other alarm |
| **10. Wrap-up** (done 2026-10-18; tag `v0.1.0`; the Zenodo DOI came later: concept DOI 10.5281/zenodo.23573707, first archived version `v0.2.3`; the clean-clone check covered the headline sweep only, see results/README.md) | Results summary in `results/README.md`, reproducibility check from a clean clone, tag `v0.1.0` with a Zenodo DOI, JOSS paper draft (`paper.md`), docs quickstart (README) | Clean clone + `make results` reproduces the headline tables (checked for `rq1_pisa_sweep` from the cached cohort; the full pipeline has not been re-run from a clean clone) |

## Open items

The one list of what is blocked or deferred (as of 2026-10-18). None blocks a phase's "done when"; each limits a stated claim or a later step.

| Item | Why open | Consequence until resolved | Who can unblock |
|---|---|---|---|
| Full text of Facchinetti 2016 | Not open access; only the abstract was read | The PISA time constant (τ = 10 min) and the dropout model are assumptions, swept by the τ = 5/20 min robustness arms; the paper's Markov dropout model is not used (SPEC_REVIEW SR2–SR3) | Project lead (library access) |
| Full text of Lobo 2026 | Read as abstract only | The realistic PISA rate comes from the abstract's counts (1,260 PISAs in 94,201 h, minimum < 85 mg/dL) | Project lead |
| Padova/UVA labelled dual-sensor data | Needs contact and an agreement; start now, because of the lead time | No real PISA labels: real-data results use injected PISAs, and real artifacts in the reference count as true lows | Project lead |
| OhioT1DM | Data use agreement | Not used (optional fingerstick reference) | Project lead |
| CGMacros | Descoped rather than blocked: its labels would be a weak proxy (Libre Pro, mostly T2D, few lows) | Not used | — |
| Zenodo DOI (done 2026-10-22) | Done: concept DOI [10.5281/zenodo.23573707](https://doi.org/10.5281/zenodo.23573707); first archived version `v0.2.3`. Releases before it were not archived | — | — |
| Clinical review and literature fact-checking (CR1–CR17) | Needs a clinician | Thresholds, the floor, the SESOI and the flag rule stay marked as assumptions | a clinician (unassigned) |
| Dexcom API sign-in | Deferred; sandbox first | The upload report reads exported files only | — |
| Data donation or labelling study | Needs IRB approval | No data is collected (PRIVACY_AND_SAFETY.md, Privacy rule 5) | — |
