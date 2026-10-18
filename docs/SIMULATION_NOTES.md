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

### Calibration (D17)

`experiments/configs/calibration_v1.yaml`: standard meals, 14 days, calibration seed 9001 (disjoint from the benchmark seeds), without treatment of lows. Of the 30 patients, 5 kept the stock bolus settings and 6 more kept them while having few lows (TBR <70 under 1% even at the stock scale). 14 needed smaller boluses (every child among them; bolus scale up to 3.5, i.e. boluses 3.5 times smaller). 4 needed larger boluses, and 1 reached the limit of 30% more insulin. 22 of 30 ended inside the target band (TBR <70 of 1–8%) with plasma never below 40 mg/dL. The 8 outside it have fewer lows than the band, not more.

### The first full cohort, without treatment of lows (not used)

The first `sim_full` cohort (cache key b08773c94389) was physiologically impossible in the perturbed mixes. Median time below 54 mg/dL was 0.0% (standard), 5.6% (default) and 20.6% (high). Median run nadirs were 59, 22 and 0.5 mg/dL. 147 of 450 runs went below 10 mg/dL, outside the model's validity. Nobody treated the lows and the 2008 model has no counter-regulation, so lows lasted until the insulin wore off (median level-1 duration 267 min in the default mix). The virtual patients now treat their lows (amendment A6, SIMULATION.md §2). The cohort below is the one the benchmark uses.

### The benchmark cohort (`sim_full`, cache key 8022d1cd7242)

Generated by `experiments/sim_report.py --config experiments/configs/sim_full.yaml`; 2.3 h on 7 processes.

450 patient-runs (30 patients × 5 seeds × 3 mixes), 14 days each.

| Mix | Runs outside model validity | Median TBR <70 (plasma) | Median TBR <54 | Level-1 events | Level-2 events | Nocturnal level-2 | Patients with no level-2 event | Leak AUC (IOB) | Leak AUC (COB) | Night share 70–95 mg/dL | Treatments per day |
|---|---|---|---|---|---|---|---|---|---|---|---|
| standard | 0 | 0.9% | 0.0% | 512 | 32 | 22 | 16 of 30 | 0.69 | 0.57 | 22% | 1.16 |
| default | 0 | 2.6% | 0.3% | 1423 | 249 | 113 | 0 of 30 | 0.65 | 0.58 | 14% | 2.46 |
| high | 0 | 3.9% | 0.6% | 2167 | 511 | 231 | 0 of 30 | 0.63 | 0.57 | 12% | 3.57 |

Level-2 events by age group (all mixes):

| Mix | adolescent | adult | child |
|---|---|---|---|
| default | 75 | 53 | 121 |
| high | 162 | 135 | 214 |
| standard | 9 | 2 | 21 |

Lag from plasma level-1 onset to interstitial glucose <70: median 15 min (IQR 12–18), n = 3881.

What this shows, and what it limits:

- **Plausibility.** No run left the model's validity range. Medians of 2.6% below 70 and 0.3% below 54 in the default mix sit in the range reported for people with type 1 diabetes. The default mix has 1423 level-1 and 249 level-2 lows in 2,100 patient-days (0.68 and 0.12 per day), close to AZT1D's CGM-referenced 0.51 and 0.10. The standard mix has few severe lows (32; 16 of 30 patients have none), so its D5 operating point is coarse, and folds with fewer than 10 level-2 lows fall back to level 1 (A7).
- **Children dominate the level-2 lows** in every mix (121 of 249 in the default mix). Results are reported by age group as well as pooled (D14).
- **The leak axis is narrower than designed.** Leak AUC (IOB at nocturnal low onsets vs. the night) falls only from 0.69 (standard) to 0.65 (default) and 0.63 (high). Insulin still explains most nocturnal lows in every mix, so the three mixes are three modestly different worlds, not a wide sweep. AZT1D's real leak AUC (0.59, user-entered boluses only) is below all three; the matched mix for H3 is therefore `high` (A4).
- **Treatment frequency.** The virtual patients treat 1.2, 2.5 and 3.6 times a day. That is more often than real people do, partly because the smooth simulated sensor error drifts below 70 mg/dL and triggers a treatment that a real person might wait out (CR17).
- **Lag.** CGM lows trail plasma lows by a median of 15 min (IQR 12–18). The longer-than-physiological sensor lag (SIMULATION.md §1) makes warning times pessimistic; the 6-min arm (robust_lag6) bounds this.

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

### Face validity against real CGM (Phase 7, D16)

`experiments/real_data.py` compares nocturnal level-1 lows on the CGM in the default mix with those in Weinstock 2016 (`results/figures/real__face_validity.png`, `results/tables/real__face_validity.csv`). Medians, simulated vs. real:

- **Fall rate** in the 30 min before the low: −0.40 vs. −0.47 mg/dL/min. The two distributions nearly coincide.
- **Nadir:** 57 vs. 47 mg/dL. About a third of the real lows reach the G4's floor of 40 mg/dL, which simulated lows rarely do.
- **Duration:** 45 vs. 65 min. Simulated lows end within 3 h because the virtual patients treat them; real nocturnal lows in these older adults last up to 10 h.
- **Share of the night at 70–95 mg/dL:** 16% vs. 6%.
- **Time below 70:** 2.9% vs. 4.8%.

Reading: simulated lows arrive the way real ones do, but are shallower and shorter. Two things widen that gap and are not simulator flaws. Weinstock is a case–control cohort of older adults selected for severe hypoglycaemia, and the virtual patients' treatment rule cuts lows short. So the comparison bounds, rather than proves, realism. It is also why the semi-synthetic track, which uses real low shapes, is co-primary for RQ1.
