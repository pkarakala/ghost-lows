# Simulation notes

What the simglucose source actually does, how `ghostlows.sim` uses it, and what the simulated cohort looks like. The specification is [`SIMULATION.md`](SIMULATION.md); the decisions behind it are in [`DECISIONS.md`](DECISIONS.md).

## Verified in the simglucose 0.2.11 source (2026-10-18)

| Topic | Finding | Consequence |
|---|---|---|
| Truth vs. CGM | `T1DSimEnv.mini_step` sets `BG = patient.observation.Gsub`; `CGMSensor.measure` returns `observation.Gsub + noise`. `Gsub` is state x[12] / Vg. | simglucose's "BG" is interstitial, not blood glucose. The benchmark's truth is plasma glucose, x[3] / Vg (D1). |
| Blood-to-interstitial lag | `dx12/dt = −ksc·x12 + ksc·x3`; τ = 1/ksc ranges 6.6–19.9 min across the 30 patients (median ≈ 11). x[12] appears in no other equation. | The model already lags; no extra filter. The 6-min lag arm can be computed from plasma afterwards without re-simulating. |
| Sensors | `sensor_params.csv`: Dexcom (3 min), GuardianRT (5 min) and Navigator (1 min) share PACF 0.7 and the same Johnson parameters; output clipped to 39–600 mg/dL. | The 5-min sensor is GuardianRT's row, renamed. Readings are clipped to the device range 40–400 with flags (assumption). |
| Noise | `noise_gen.py`: AR(1) with PACF 0.7 on a 15-min grid, Johnson SU transform, cubic interpolation to the sample times. | Noise is smooth, with no sample-level jitter; spikes and noise near 70 mg/dL are gentler than in real sensors. |
| Episode end | `T1DSimEnv.step` sets `done = BG < 10 or BG > 600`. | The engine does not stop; a run whose plasma falls below 10 mg/dL is flagged as outside model validity and excluded with a count. |
| Stock controller | `BBController._bb_policy` adds the full correction `(glucose − 140)/CF` (when glucose > 150) on *every* 5-min step with food intake, and boluses on the true carbs eaten. | Corrections stack during multi-step meals and announced carbs cannot differ from true ones. Replaced by the controller in `engine.py` (D17). |
| Physiology | No glucagon state and no hypoglycaemia-dependent insulin action (2008 model). The 2013 additions are published [Dalla Man 2014], but the values of r1, r2 and the glucagon parameters are not. | Simulated lows are the least trustworthy part of the model (RESEARCH.md §6–7). |
| pandas 3 | A patient parameter row is an `object` Series, so the default initial state is an `object` array. | The engine passes an explicit float initial state. |

## How `ghostlows.sim` runs a patient

- `T1DPatient` is stepped one minute at a time. Plasma and interstitial glucose are recorded every minute. A CGM sample is drawn every 5 min: interstitial glucose plus the next value of simglucose's noise generator, clipped for display.
- Day-level insulin-sensitivity multipliers and post-exercise effects scale the patient's `Vmx` and `kp3` (insulin-dependent utilisation and insulin action on glucose production). During exercise, `Vm0` (insulin-independent utilisation) is scaled. Multipliers switch at 12:00, away from the night window (assumption).
- **Controller:** basal = the patient's steady-state rate. One bolus per announced meal, from announced carbs ÷ (carb ratio × k). At most one correction per meal when the displayed CGM is above 150 mg/dL, towards 140 mg/dL, scaled by the same k. k comes from the per-patient calibration (`experiments/configs/calibration_v1.yaml`).
- **Context:** IOB (exponential action curve, 5 h) and COB (linear, 3 h) are computed from the event log at each sample time, using only events at or before it. A test recomputes them from the logged events.
- **Seeds:** each (seed, patient) pair gives a meal seed, a perturbation seed and a noise seed. Meals and noise do not depend on the scenario mix, so the mixes are paired.
- **Cache:** `data/sim/<name>-<hash>/`, holding `samples.parquet` (5-min), `truth.parquet` (1-min plasma), `events.parquet`, `runs.csv`, `config.yaml` and `meta.json`. The hash covers the config, the calibration file and the package versions.

## Results

Filled in from `experiments/sim_report.py` below.

## Blocked or deferred items (2026-10-18)

Recorded per the working rule "if something is blocked, record it here and move on". None of these blocks a phase's "done when"; each limits a stated claim.

| Item | Why blocked | Consequence until resolved | Who can unblock |
|---|---|---|---|
| Full text of Facchinetti 2016 | Not open access; only the abstract was read | The PISA time constant (τ = 10 min) and the dropout model are assumptions, swept by the τ = 5/20 min robustness arms; the paper's Markov dropout model is not used (SPEC_REVIEW SR2–SR3) | Project lead (library access) |
| Full text of Lobo 2026 | Read as abstract only | The realistic PISA rate comes from the abstract's counts (1,260 PISAs in 94,201 h, minimum < 85 mg/dL) | Project lead |
| Padova/UVA labelled dual-sensor data | Needs contact and an agreement | No real PISA labels: real-data results use injected PISAs, and real artifacts in the reference count as true lows | Project lead (PUBLICATION.md) |
| OhioT1DM | Data use agreement | Not used (optional fingerstick reference) | Project lead |
| CGMacros | Descoped rather than blocked: its labels would be a weak proxy (Libre Pro, mostly T2D, few lows) | Not used | — |
| Zenodo DOI for `v0.1.0` | Needs the GitHub–Zenodo integration switched on by the repository owner | Release can be tagged, but the DOI is minted only after the integration is on | Project lead |
| Clinical review (CR1–CR16) | Needs a clinician | Thresholds, the floor, the SESOI and the flag rule stay marked as assumptions | Clinical co-lead |

AZT1D was listed as a manual download until 2026-10-18. Mendeley Data's public API serves the CC BY 4.0 archive with a published SHA-256, so `scripts/download_data.py --azt1d` now fetches it (DATA.md §2).
