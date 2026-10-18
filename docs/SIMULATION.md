# Simulation and fault-suite specification

Every number here comes from a cited source or is marked **[assumption]**. Assumptions are configurable and must be listed in the results. Decisions D1–D18 are explained in [`DECISIONS.md`](DECISIONS.md).

## 1. Simulator

- **simglucose 0.2.11** (Python implementation of the UVA/Padova T1D simulator, 2008 version) [simglucose; Kovatchev 2009]. 30 virtual patients: 10 children, 10 adolescents, 10 adults. The 2008 model has no glucagon counter-regulation and no hypoglycaemia-dependent insulin action [Dalla Man 2014]; see RESEARCH.md §6–7.
- **Install gotcha (verified 2026-10-18):** use Python 3.11. simglucose imports `gym`, which needs `pkg_resources`, so pin `setuptools<70`. On Python 3.13 `gym` fails to build. `uv sync` installs it through the `sim` extra; it runs under pandas 3, but the patient state becomes an `object`-dtype array (check ODE speed).
- **Truth signal (D1, verified in the source).** simglucose's `BG` output is `observation.Gsub`, the subcutaneous state x[12]/Vg, which is the same signal its CGM adds noise to. The model already lags it behind plasma: `dx12/dt = ksc·(x3 − x12)`, τ = 1/ksc = 6.6–19.9 min across the 30 patients (median about 11). The benchmark therefore uses:
  - `truth_glucose` = plasma glucose x[3]/Vg, recorded every minute;
  - `isf_glucose` = Gsub (model-native interstitial glucose);
  - `cgm_clean` = `isf_glucose` sampled every 5 min plus sensor noise. No extra lag filter.
  - **Lag sensitivity arm:** `isf_glucose` recomputed from plasma with a first-order filter of τ = 6 min [Basu 2013] **[clinical review CR8]**. This is valid because x[12] feeds nothing back into the model.
- **Sampling:** the bundled "Dexcom" sensor samples every 3 min, but all three bundled sensors share the same noise parameters and `GuardianRT` already samples every 5 min. The benchmark sensor is a project-local row with those parameters and `sample_time = 5`; site-packages is not edited. Readings are clipped to the device range 40–400 mg/dL and flagged `below_range`/`above_range` **[assumption]** (simglucose clips at 39/600).
- **Noise:** simglucose uses one Johnson-distributed noise model for all sensors [Breton 2008]: AR(1) on a 15-minute grid, cubic-interpolated to the sample times, so it is smooth. State this limitation.
- **Run termination:** simglucose ends an episode when glucose falls below 10 mg/dL. The wrapper does not stop; it records such a patient-run as *outside model validity* and excludes it with a count in the results.
- **Length:** 14 days per patient per scenario **[assumption]**, all 30 patients, at least 5 random seeds for scenarios. Calibration (§2) uses separate seeds.

## 2. Controller (D9, D17)

Open-loop basal-bolus control (the RQ2 target population). The stock `BBController` is not used: it gives the full correction bolus again on every 5-minute step during which the patient eats, and its therapy settings produce implausible hypoglycaemia in several patients (DECISIONS.md, pilot).

- **Basal:** the patient's steady-state basal (u2ss) times a per-patient calibrated factor.
- **Meal bolus:** one bolus at the start of each announced meal, equal to announced carbs ÷ carb ratio (per-patient calibrated scale on the ratio from simglucose's `Quest.csv`).
- **Correction:** at most one per meal, added to the meal bolus when the CGM is above 150 mg/dL, aiming for 140 mg/dL with the patient's correction factor **[assumption, as in the stock controller]**.
- **Calibration:** for each patient, choose the basal factor and carb-ratio scale on the *standard* scenario (calibration seeds only) so that 14-day TBR <70 lies in 1–8% and plasma never falls below 40 mg/dL **[assumption, clinical review CR15]**. Lows deeper than that are outside the 2008 model's credible range. Report the calibrated factors and compare the cohort's TBR distribution with real per-person TBR (DiaData).
- **Records:** every delivered dose and every announced carbohydrate amount, with times.
- **Context features use recorded data only (SR12):** IOB from delivered boluses, with a configurable insulin action curve (default duration 5 h; sensitivity 3 and 7 h) **[assumption]**; COB from *announced* carbs (miscounted, and still present when the meal is skipped), with a configurable absorption curve (default linear over 3 h) **[assumption]**. A test checks that context columns can be recomputed from the logged events alone.

## 3. Scenarios (vary how much insulin explains)

Some lows must not be predictable from insulin. Each scenario family is switchable and seeded.

| Family | What it does | Parameters **[assumption]** unless cited |
|---|---|---|
| Standard meals | 3 meals + optional snacks, random times and sizes | simglucose `RandomScenario` |
| Carb miscounting | Bolus computed from announced carbs = true carbs × (1 + e), e ~ N(0, 0.2) | |
| Missed bolus | Some meals get no bolus | p = 0.05 per meal |
| Skipped meal after bolus | Bolus given, meal not eaten | p = 0.02 per meal |
| Insulin-sensitivity drift | Day-level multiplier on insulin sensitivity, ~ U(0.7, 1.3) | Implement by scaling the patient's insulin-action parameters; document which ones |
| Unannounced exercise | 30 to 60 min sessions, insulin sensitivity raised for several hours afterwards, not visible to the controller or to context features | 2 to 4 sessions/week |

**Mixes (D3).** *Standard*: standard meals only, which gives an upper bound on what context can do. *Default*: all families at the values above. *High*: miscounting SD, missed-bolus and skipped-meal probabilities, the sensitivity range and exercise frequency all doubled **[assumption]**. For each mix, report the realised leak, AUC(IOB at nocturnal true-low onsets vs. random night times) (BENCHMARK.md §4), so readers can see how much recorded insulin explains.

## 4. Fault suite

Faults are applied **after** simulation to the clean CGM trace, so the same physiology can be scored under different faults. Every sample keeps `truth_glucose`, `isf_glucose`, `cgm_clean`, `cgm_observed`, `fault_type` (none / pisa / dropout / stale / drift / spike) and `fault_id`.

### 4.1 Compression (PISA): Facchinetti model

From [Facchinetti 2016] (72 people, Dexcom G4 Platinum, 7 days), as used by [Idi 2024]:

- **Shape:** "the output of a first-order linear dynamic system driven by a rectangular function" [Facchinetti 2016]. The CGM during a PISA is `cgm_clean − A·h(t)`, with h the response of a first-order system with time constant τ to a unit rectangle of length D.
- **Reported size is of the observed artifact:** duration median 45 min (5th–95th percentile 30–70), amplitude median 24 mg/dL (10–48) [Facchinetti 2016]. Each sampled artifact is generated so that its *realised* peak attenuation and duration match the sampled values. Until the full text is read: τ = 10 min **[assumption]**; A = depth / (1 − e^(−D/τ)); realised duration = D + τ·ln 10, the time until attenuation falls to 10% of its peak **[assumption]**. The Phase 3 test checks quantiles measured on the generated traces, not on the parameters.
- **Distribution:** a two-piece log-normal for each of depth and duration, with different log-scale spreads below and above the median, so that the median and both percentiles match exactly **[assumption]**. A single log-normal cannot match depth (log-distances 0.88 below vs. 0.69 above the median). Depth and duration are sampled independently **[assumption]**.
- **Drop rate:** follows from τ (initial fall rate ≈ A/τ). Report the realised drop-rate distribution, because it decides whether rate-based detectors such as Baysal's (entry thresholds −1.9 to −3.1 mg/dL/min [Baysal 2014]) can fire. Do not use cliff-like drops (for example 177 to 74 mg/dL in 5 min).
- **Timing:** mostly at night. Sample onset uniformly within 23:00–07:00 **[assumption]**; the time-of-night distribution "has not been modeled in the literature" [Idi 2024]. Count and report PISAs that overlap a meal bolus (§4.5).
- **Frequency (severity knob, D13):** the fraction of nights with a PISA, swept 0%, 10%, 25%, 50%, 75%, 100%, with one PISA per compressed night **[assumption]**. Severity never changes depth or duration. For a realistic default, calibrate the rate of PISAs whose minimum CGM is below 85 mg/dL per hour of wear to [Lobo 2026] **[clinical review CR3]**. Its abstract implies about 1 per 70–92 h; "1 per 73 h" must be checked against the full text. Facchinetti 2016's own frequency data is a second anchor.

### 4.2 Other faults (each switchable, with a severity knob)

| Fault | Model **[assumption]** unless cited | Why include |
|---|---|---|
| Dropout / signal loss | Facchinetti 2016's three-state Markov model once the full text is read. Until then: exponential gap length with P(gap <20 min) = 0.90 [Facchinetti 2016] (median ≈ 6 min) | Common in practice; alarms must handle gaps |
| Stale readings | Last value repeated for 10 to 30 min | Tests trend logic |
| Drift | Slow multiplicative bias, ±10 to 20% over a sensor's life, reset at sensor change | Sensor ageing |
| Spikes / noise bursts | Short bursts of extra noise | Tests robustness near threshold |

### 4.3 Mixed suite

A single `FaultSuite` config combines all faults with one overall severity `s ∈ [0, 1]` that scales rates and magnitudes, plus per-fault overrides. For PISA, `s` scales only the rate; depth and duration stay at the literature distribution. The default benchmark sweeps the PISA fraction with the other faults at a fixed moderate level, and a second sweep raises all faults together.

### 4.4 Robustness arms

- **Generator mismatch (D8):** test PISAs from perturbed shapes (τ × 0.5 and × 2; depth quantiles × 0.75 and × 1.25) while every detector keeps the nominal model.
- **Lag (D1):** the τ = 6 min interstitial signal of §1.

### 4.5 Validity of post-hoc injection (D9)

Injecting faults after simulation assumes the controller never acted on the faulted signal. That holds for open-loop control at night, but a PISA still running at breakfast (onsets from 05:00) would in reality lower the CGM used for the breakfast correction. Report the share of PISAs overlapping a meal bolus. Do not combine post-hoc injection with automated insulin delivery.

## 5. Real-data semi-synthetic track (co-primary for RQ1, D16)

Inject PISAs from the same model into **real** overnight CGM traces (Weinstock 2016; DiaData raw release, deduplicated against Weinstock and D1NAMO; see `DATA.md`) at stable stretches, and score alarms on the injected events. This tests detectors against real sensor noise and real low shapes, though not against real compression. The un-injected CGM is the reference; real, unlabelled PISAs in it bias sensitivity.

## 6. Reproducibility

- Every run is driven by one YAML config, with seeds, and writes its config, git commit hash and benchmark version (`ghostlows-bench v1`, D18) next to its outputs.
- Calibration seeds and benchmark seeds are disjoint.
- Simulated traces are cached as Parquet under `data/sim/` (gitignored), keyed by a config hash. The frozen benchmark cohort is also released as a versioned dataset (PUBLICATION.md).
