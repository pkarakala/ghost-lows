# Simulation and fault-suite specification

Every number here comes from a cited source or is marked **[assumption]**. Assumptions are configurable and must be listed in the results.

## 1. Simulator

- **simglucose 0.2.11** (Python implementation of the UVA/Padova T1D simulator, 2008 version) [simglucose; Kovatchev 2009]. 30 virtual patients: 10 children, 10 adolescents, 10 adults.
- **Install gotcha (verified 2026-10-18):** use Python 3.11. simglucose imports `gym`, which needs `pkg_resources`, so pin `setuptools<70`. On Python 3.13 `gym` fails to build.
  ```
  uv venv -p 3.11 && uv pip install simglucose "setuptools<70"
  ```
- **Sampling:** the bundled "Dexcom" sensor samples every 3 min. G6/G7 sample every 5 min. Add a custom sensor row (copy the Dexcom noise parameters, `sample_time = 5`) by writing a project-local `sensor_params.csv` or subclassing `CGMSensor`. Do not edit site-packages.
- **Noise:** simglucose uses one Johnson-distributed noise model for all sensors [Breton 2008]. State this limitation.
- **Truth signal:** check in the simglucose source which glucose state the `BG` output is, and which state the CGM reads. If both derive from the same compartment, add a blood-to-interstitial lag as a first-order filter with tau of 5 to 10 min [Basu 2013] **[assumption, clinical review]**, so that warning-time numbers are meaningful. Document what you find in `docs/SIMULATION_NOTES.md`.
- **Length:** 14 days per patient per scenario **[assumption]**, all 30 patients, at least 5 random seeds for scenarios.

## 2. Controller

Basal-bolus controller with carb-ratio boluses and correction boluses, with realistic errors (see scenarios). Optionally a simple AID-like controller later. Record every insulin dose and carb intake so IOB and COB can be computed the same way a pump would (IOB with a standard insulin action curve, e.g. 4 to 5 h duration **[assumption]**).

## 3. Scenarios (break the insulin leak)

The point: some lows must not be predictable from insulin. Each scenario family is switchable and seeded.

| Family | What it does | Parameters **[assumption]** unless cited |
|---|---|---|
| Standard meals | 3 meals + optional snacks, random times and sizes | simglucose `RandomScenario` |
| Carb miscounting | Bolus computed from announced carbs = true carbs × (1 + e), e ~ N(0, 0.2) | |
| Missed bolus | Some meals get no bolus | p = 0.05 per meal |
| Skipped meal after bolus | Bolus given, meal not eaten | p = 0.02 per meal |
| Insulin-sensitivity drift | Day-level multiplier on insulin sensitivity, ~ U(0.7, 1.3) | Implement by scaling the patient's insulin-action parameters; document which ones |
| Unannounced exercise | 30 to 60 min sessions, insulin sensitivity raised for several hours afterwards, not visible to the controller or to context features | 2 to 4 sessions/week |

Report results on (a) standard scenarios only and (b) the full mix, so the size of the leak is visible.

## 4. Fault suite

Faults are applied **after** simulation to the clean CGM trace, so the same physiology can be scored under different faults. Every sample keeps: `truth_glucose`, `cgm_clean`, `cgm_observed`, `fault_type` (none / pisa / dropout / stale / drift / spike), `fault_id`.

### 4.1 Compression (PISA) — Facchinetti model

From [Facchinetti 2016] (72 people, Dexcom G4, 7 days), as used by [Idi 2024]:

- **Shape:** a rectangular "pressure" input passed through a first-order system, giving a fast asymmetric drop and recovery. The CGM signal during a PISA is `cgm_clean - depth * h(t)`, where `h` is the first-order response to a rectangular input of length `duration`. Read the paper's exact equations before finalising; until then this is the working form **[assumption until full text is read]**.
- **Duration:** median 45 min, 5th to 95th percentile 30 to 70 min.
- **Depth:** median 24 mg/dL, 5th to 95th percentile 10 to 48 mg/dL.
- **Distribution:** fit a log-normal (or the paper's own distribution, if given) to these medians and percentiles. Write the fitted parameters into the config and plot sampled vs. reported quantiles in a test.
- **Timing:** mostly at night. Sample onset within a sleep window (e.g. 23:00 to 07:00) **[assumption]**; the time-of-night distribution "has not been modeled in the literature" [Idi 2024].
- **Frequency (severity knob):** fraction of nights with at least one PISA, swept 0%, 10%, 25%, 50%, 75%, 100%. For a realistic default, calibrate to roughly one PISA below 85 mg/dL per 73 h of wear [Lobo 2026] **[clinical review]**.
- **Do not** use cliff-like drops (for example 177 to 74 mg/dL in 5 min). Real-time detectors trigger on falls of about 1.9 to 3.1 mg/dL/min [Baysal 2014].

### 4.2 Other faults (each switchable, with a severity knob)

| Fault | Model **[assumption]** | Why include |
|---|---|---|
| Dropout / signal loss | Missing samples, gap length ~ log-normal, median 20 min | Common in practice; alarms must handle gaps |
| Stale readings | Last value repeated for 10 to 30 min | Tests trend logic |
| Drift | Slow multiplicative bias, ±10 to 20% over a sensor's life, reset at sensor change | Sensor ageing |
| Spikes / noise bursts | Short bursts of extra noise | Tests robustness near threshold |

### 4.3 Mixed suite

A single `FaultSuite` config combines all faults with one overall severity `s ∈ [0, 1]` that scales rates and magnitudes, plus per-fault overrides. The default benchmark sweeps the PISA fraction with the other faults at a fixed moderate level, and a second sweep raises all faults together.

## 5. Real-data semi-synthetic track

Inject PISAs from the same model into **real** overnight CGM traces (Weinstock 2016, DiaData; see `DATA.md`) at stable stretches, and score detectors on recall of the injected events. This tests detectors against real sensor noise, though not against real compression.

## 6. Reproducibility

- Every run is driven by one YAML config, with seeds, and writes its config and git commit hash next to its outputs.
- Simulated traces are cached as Parquet under `data/sim/` (gitignored), keyed by a config hash.
