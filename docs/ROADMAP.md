# Roadmap

Each phase ends with passing tests and a commit. Prompts for each phase are in [`../prompts/`](../prompts/). Phases 0 to 8 are the end-to-end core; phase 9 is a stretch.

| Phase | Goal | Done when |
|---|---|---|
| **0. Scaffold** | `pyproject.toml` (Python 3.11, uv), `src/ghostlows/`, ruff, pytest, GitHub Actions CI, `scripts/download_data.py`, `.gitignore` | `uv run pytest` passes on an empty test; CI green; GlucoBench data downloads with a manifest |
| **1. Data I/O and metrics** | Loaders for GlucoBench CSVs, Dexcom Clarity, LibreView into the common schema (DATA.md §3). Consensus metrics: mean, SD, CV, GMI, TIR 70–180, TBR <70 and <54, TAR >180 and >250, wear %, AGP percentiles [Battelino 2019] | Hand-made Clarity and LibreView fixtures parse; metrics match hand-computed values on a fixture; GlucoBench files load with row counts logged |
| **2. Simulation** | simglucose wrapper: 5-min sensor, 30 patients, basal-bolus controller, scenario families (SIMULATION.md §3), IOB/COB, truth vs. CGM documented, Parquet cache | `python -m ghostlows.sim --config experiments/configs/sim_smoke.yaml` produces 2 patients × 2 days; full config runs 30 patients × 14 days; `docs/SIMULATION_NOTES.md` written |
| **3. Fault suite** | PISA (Facchinetti model), dropout, stale, drift, spikes; `FaultSuite` with severity; labels per sample | Test: sampled PISA depth/duration quantiles match the paper's medians and 5th/95th percentiles within tolerance; faults never change `truth_glucose`; plot of example faults saved |
| **4. Alarms** | `threshold`, `trend`, `baysal_gate`, `matched_filter_gate`, `iforest_gate`, `gbm`, and `_ctx` variants (BENCHMARK.md §2) | Causality test (future data cannot change past scores) passes for every alarm; each alarm has a unit test on a synthetic trace |
| **5. Scoring** | Event detection, matching, metrics incl. false alarms split by cause, FDA-style rates, flicker; leave-patients-out CV; operating-point rule; patient-level bootstrap CIs | Scoring tests on hand-built traces with known answers; `run_benchmark.py` runs end to end on the smoke config |
| **6. Experiments (RQ1, RQ2)** | Severity sweeps; with/without context ablation at fixed level 2 sensitivity; standard vs. full scenario mix; figures and `results/README.md` | All tables/figures regenerate from one command; assumptions file auto-generated |
| **7. Real-data track** | Run alarms on Weinstock (and DiaData/AZT1D if downloaded); semi-synthetic PISA injection into real nights; real-data context check where insulin/carbs exist | Real-data results table with dataset citations; clear statement of what is and is not labelled |
| **8. Upload dashboard** | `ghostlows.retro` (possible compression artifact flags using published CGM-only methods) + stlite app in `app/`, deployed to GitHub Pages | Uploading a fixture Clarity CSV in a browser shows metrics, AGP, daily traces, flags with reasons, TBR with and without flags, and the disclaimers in PRIVACY_AND_SAFETY.md; no network requests carry user data |
| **9. Stretch: RQ3** | `kalman_pisa`: Kalman/HMM with explicit compressed state + insulin/meal inputs | Benchmarked like every other alarm |
| **10. Wrap-up** | Results summary in `results/README.md`, reproducibility check from a clean clone, tag `v0.1.0` | Clean clone + `make all` reproduces the headline tables |

## Deferred (later days)

- Literature preparation and fact-checking (`docs/CLINICAL_REVIEW.md`).
- Dexcom API sign-in (sandbox first).
- Any data donation or labelling study (needs IRB).
- Contact with Padova / UVA groups about the labelled dual-sensor set.
