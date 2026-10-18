# Roadmap

Each phase ends with passing tests and a commit. Prompts for each phase are in [`../prompts/`](../prompts/). Phases 0 to 8 are the end-to-end core; phase 9 is a stretch.

Before starting a phase, resolve the open items in [`SPEC_REVIEW.md`](SPEC_REVIEW.md) tagged with that phase number.

| Phase | Goal | Done when |
|---|---|---|
| **0. Scaffold** ✅ done 2026-10-18 | `pyproject.toml` (Python 3.11, uv), `src/ghostlows/`, ruff, pytest, GitHub Actions CI, `scripts/download_data.py`, `.gitignore` | `uv run pytest` passes on an empty test; CI green; GlucoBench data downloads with a manifest |
| **1. Data I/O and metrics** ✅ done 2026-10-18 | Loaders for GlucoBench CSVs, Dexcom Clarity, LibreView into the common schema (DATA.md §3). Consensus metrics: mean, SD, CV, GMI, TIR 70–180, TBR <70 and <54, TAR >180 and >250, wear %, AGP percentiles [Battelino 2019] | Hand-made Clarity and LibreView fixtures parse; metrics match hand-computed values on a fixture; GlucoBench files load with row counts logged |
| **2. Simulation** ✅ done 2026-10-18 | simglucose wrapper: plasma truth + interstitial + 5-min CGM (D1), 30 patients, rewritten open-loop basal-bolus controller with per-patient calibration (D17), scenario families and the three mixes (SIMULATION.md §3, D3), IOB/COB from recorded events, Parquet cache | `python -m ghostlows.sim --config experiments/configs/sim_smoke.yaml` produces 2 patients × 2 days; full config runs 30 patients × 14 days; calibrated cohort within the TBR band; leak AUC reported per mix; `docs/SIMULATION_NOTES.md` written |
| **3. Fault suite** ✅ done 2026-10-18 | PISA (Facchinetti model, realised-size parametrisation, two-piece log-normal), dropout, stale, drift, spikes; `FaultSuite` with severity; labels per sample; mismatch-arm generator (D8) | Test: depth/duration quantiles *measured on generated traces* match the paper's medians and 5th/95th percentiles within tolerance; faults never change `truth_glucose`; plot of example faults saved |
| **4. Alarms** ✅ done 2026-10-18 | `threshold`, `trend`, `baysal_gate`, `matched_filter_causal_gate`, `iforest_causal_gate`, `gbm`, the urgent-low floor (D4) and the four context arms through one combiner (D2) (BENCHMARK.md §1–2) | Causality test (future data cannot change past scores) passes for every alarm; each alarm has a unit test on a synthetic trace; the floor is never suppressed |
| **5. Scoring** ✅ done 2026-10-18 | Event detection (D11), matching (D12), metrics incl. false alarms split by cause (D10), leak AUC, FDA-style rates, flicker; leave-patients-out CV; operating-point rule (D5); patient-level bootstrap CIs; `ghostlows` CLI and a tested plug-in alarm example (D18) | Scoring tests on hand-built traces with known answers; `run_benchmark.py` runs end to end on the smoke config; the example alarm scores in CI |
| **6. Experiments (RQ1, RQ2)** | Tag `protocol-v1` before the full run; severity sweeps; factorial context ablation at the pre-registered operating point on the three mixes; robustness arms (lag, generator mismatch, windows, δ); figures and `results/README.md`; frozen cohort `ghostlows-bench v1` packaged for Zenodo | All tables/figures regenerate from one command; assumptions file auto-generated |
| **7. Real-data track** ✅ done 2026-10-18 | Co-primary semi-synthetic track: PISAs injected into real nights (Weinstock; DiaData raw, deduplicated) (D16); face validity of simulated lows vs. real CGM; real-data context check on AZT1D with user-entered boluses/carbs (H3) | Real-data results table with dataset citations; face-validity figure; clear statement of what is and is not labelled |
| **8. Upload dashboard** ✅ done 2026-10-18 ([live](https://pkarakala.github.io/ghost-lows/)) | `ghostlows.retro` (possible compression artifact flags using published CGM-only methods) + stlite app in `app/`, deployed to GitHub Pages | Uploading a fixture Clarity CSV in a browser shows metrics, AGP, daily traces, flags with reasons, TBR with and without flags, and the disclaimers in PRIVACY_AND_SAFETY.md; no network requests carry user data |
| **9. Stretch: RQ3** | `kalman_pisa`: Kalman/HMM with explicit compressed state + insulin/meal inputs | Benchmarked like every other alarm |
| **10. Wrap-up** | Results summary in `results/README.md`, reproducibility check from a clean clone, tag `v0.1.0` with a Zenodo DOI, JOSS paper draft (`paper.md`), docs quickstart (PUBLICATION.md) | Clean clone + `make all` reproduces the headline tables |

## Deferred (later days)

The Padova request below should start now because of its lead time (PUBLICATION.md).

- Literature preparation and fact-checking (`docs/CLINICAL_REVIEW.md`).
- Dexcom API sign-in (sandbox first).
- Any data donation or labelling study (needs IRB).
- Contact with Padova / UVA groups about the labelled dual-sensor set.
