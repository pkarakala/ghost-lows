# Simulation and fault-suite specification

How the virtual cohort and the sensor faults are generated, for anyone running, changing or reviewing the simulation. Every number here comes from a cited source or is marked **[assumption]**. Assumptions are configurable and must be listed in the results. Decisions D1–D19 and amendments are explained in [`DECISIONS.md`](DECISIONS.md). What the simulator and the cohort turned out to be, as built, is in [`SIMULATION_NOTES.md`](SIMULATION_NOTES.md); example faults are drawn in [`figures/faults_examples.png`](../figures/faults_examples.png) (`make fault-figure`).

## 1. Simulator

- **simglucose 0.2.11** (Python implementation of the UVA/Padova T1D simulator, 2008 version) [simglucose; Kovatchev 2009]. 30 virtual patients: 10 children, 10 adolescents, 10 adults. The 2008 model has no glucagon counter-regulation and no hypoglycaemia-dependent insulin action [Dalla Man 2014]; see RESEARCH.md §6–7.
- **Install:** `uv sync` installs simglucose through the `sim` extra; Python and `setuptools` pins are in ENGINEERING.md (Stack), and the pandas 3 workaround in SIMULATION_NOTES.md.
- **Truth signal (D1, verified in the source).** simglucose's `BG` output is `observation.Gsub`, the subcutaneous state x[12]/Vg, which is the same signal its CGM adds noise to. The model already lags it behind plasma: `dx12/dt = ksc·(x3 − x12)`, τ = 1/ksc = 6.6–19.9 min across the 30 patients (median about 11). The benchmark therefore uses:
  - `truth_glucose` = plasma glucose x[3]/Vg, recorded every minute;
  - `isf_glucose` = Gsub (model-native interstitial glucose);
  - `cgm_clean` = `isf_glucose` sampled every 5 min plus sensor noise. No extra lag filter.
  - **Lag sensitivity arm:** `isf_glucose` recomputed from plasma with a first-order filter of τ = 6 min [Basu 2013] **[clinical review CR8]**. This is valid because x[12] feeds nothing back into the model.
- **Sampling:** the bundled "Dexcom" sensor samples every 3 min, but all three bundled sensors share the same noise parameters and `GuardianRT` already samples every 5 min. The benchmark sensor is a project-local row with those parameters and `sample_time = 5`; site-packages is not edited. Readings are clipped to the device range 40–400 mg/dL and flagged `below_range`/`above_range` **[assumption]** (simglucose clips at 39/600).
- **Noise:** simglucose uses one Johnson-distributed noise model for all sensors [Breton 2008]: AR(1) on a 15-minute grid, cubic-interpolated to the sample times, so it is smooth (a limitation, RESEARCH.md §6).
- **Run termination:** simglucose ends an episode when glucose falls below 10 mg/dL. The wrapper does not stop; it records such a patient-run as *outside model validity* and excludes it with a count in the results.
- **Length:** 14 days per patient per scenario **[assumption]**, all 30 patients, at least 5 random seeds for scenarios. Calibration (§2) uses separate seeds.

## 2. Controller (D9, D17)

Open-loop basal-bolus control (the RQ2 target population). The stock `BBController` is not used: it gives the full correction bolus again on every 5-minute step during which the patient eats, and its therapy settings produce implausible hypoglycaemia in several patients (DECISIONS.md, pilot).

- **Basal:** the patient's steady-state basal (u2ss) times a per-patient calibrated factor.
- **Meal bolus:** one bolus at the start of each announced meal, equal to announced carbs ÷ carb ratio (per-patient calibrated scale on the ratio from simglucose's `Quest.csv`).
- **Correction:** at most one per meal, added to the meal bolus when the CGM is above 150 mg/dL, aiming for 140 mg/dL with the patient's correction factor **[assumption, as in the stock controller]**.
- **Calibration:** for each patient, choose the basal factor and carb-ratio scale on the *standard* scenario (calibration seeds only) so that 14-day TBR <70 lies in 1–8% and plasma never falls below 40 mg/dL **[assumption, clinical review CR15]**. Lows deeper than that are outside the 2008 model's credible range. Report the calibrated factors. Comparing the cohort's TBR with real per-person TBR needs DiaData, which is not used yet.
- **Treating lows (amendment A6):** the virtual person follows the 15-15 rule [CDC 2024]: 15 g of fast carbohydrate when the displayed CGM is below 70 mg/dL by day, or at or below 55 mg/dL at night (23:00–07:00, when only the urgent-low alarm [Garg 2022] is assumed to wake them). They recheck after 15 min and repeat while below 70 **[assumption, clinical review CR17]**. The trigger is the fault-free simulated CGM, so injected faults cannot cause a treatment (the same post-hoc limitation as D9). Rescue carbohydrate is eaten but never logged: IOB, COB and the alarms do not see it. Without treatment the 2008 model, which lacks counter-regulation, let lows run until the insulin wore off. In the first full cohort this gave 5.6% (default mix) and 20.6% (high mix) of time below 54 mg/dL, with run nadirs near 0 mg/dL. Calibration (above) is defined, and was run, without treatment.
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

- **Shape:** "the output of a first-order linear dynamic system driven by a rectangular function" [Facchinetti 2016], with transfer function G(s) = P/(1 + sτ) (Eq. 6, p.268). The CGM during a PISA is `cgm_clean − P·h(t)`, with h the response of a first-order system with time constant τ to a unit rectangle of length D.
- **Names follow the paper:** P is the gain (mg/dL), D the pressure duration, τ the time constant, and A = (1 − e^(−D/τ))·P the peak deviation, "the maximum amplitude reachable by the CGM signal deviation" (Eq. 7, Fig. 6, p.269). In the code: `Pisa.gain`, `Pisa.pressure_min`, `Pisa.tau`, `Pisa.peak`. Earlier versions called A "depth" and P "amplitude".
- **Reported size is of the observed artifact:** duration median 45 min (5th–95th percentile 30–70), amplitude median 24 mg/dL (10–48) [Facchinetti 2016]. The amplitude is A. Each sampled artifact is generated so that its *realised* A and duration match the sampled values: P = A / (1 − e^(−D/τ)) (Eq. 7) and realised duration = D + τ·ln 10, the time until attenuation falls to 10% of its peak **[assumption, checked]**. A test checks quantiles measured on the generated traces, not on the parameters.
- **Time constant:** τ = 9.1 min, the published median (5th–95th percentile 3.9–21.7; Fig. 8, p.270) [Facchinetti 2016]. The paper reads τ as about one third of the time the artifact takes to vanish after the pressure ends.
- **Fitted parameter distributions** [Facchinetti 2016, p.270]: P log-normal, μ = 3.17, σ = 0.57 (median 24.7 mg/dL, 10.9–48.4); D log-normal, μ = 3.19, σ = 0.42 (median 24.4 min, 13.1–39.4); τ "β (a = 2.35, b = 4.81)", but its goodness-of-fit test is against a gamma distribution. A β distribution lives on [0, 1], so this is read as a typo for gamma(shape 2.35, scale 4.81 min), median 9.7 min **[assumption: likely typo in the paper]**. Correlations: P with τ r = −0.54, P with D r = 0.2, D with τ r = −0.18.
- **Check of the size-to-parameter mapping (A14).** Drawing P, D and τ from their published percentiles, with the published correlations, gives A median 22 mg/dL (5th–95th 7–47) and duration median 47 min (30–76), against the reported 24 (10–48) and 45 (30–70). Medians agree within 10% and the 95th percentiles within 9%; the 5th percentile of A is low (7 vs. 10 mg/dL). So the mapping and the 10% end are consistent with the paper's own parameters at the median and upper tail, and Eq. 7, being the paper's equation, needs no assumption tag. The 10% end stays a choice: a 5% end gives a median of 53 min. `tests/test_faults.py` repeats the check.
- **Distribution:** a two-piece log-normal for each of A and duration, with different log-scale spreads below and above the median, so that the median and both percentiles match exactly **[assumption]**. A single log-normal cannot match A (log-distances 0.88 below vs. 0.69 above the median). A and duration are sampled independently **[assumption]**; the paper reports correlations between P, D and τ, not between A and duration.
- **Drop rate:** follows from τ (initial fall rate ≈ A/τ). Report the realised drop-rate distribution, because it decides whether rate-based detectors such as Baysal's (entry thresholds −1.9 to −3.1 mg/dL/min [Baysal 2014]) can fire. Do not use cliff-like drops (for example 177 to 74 mg/dL in 5 min).
- **Timing:** mostly at night. Sample onset uniformly within 23:00–07:00 **[assumption]**; the time-of-night distribution "has not been modeled in the literature" [Idi 2024]. Published windows: [Facchinetti 2016] estimates its night rate for 00:00–07:59 (p.270); in [Lobo 2026], PISAs of interest are more likely to start between 21:30 and 06:00. 23:00–07:00 lies within their union and is kept (A15). Count and report PISAs that overlap a meal bolus (§4.5).
- **Frequency (severity knob, D13):** the fraction of nights with a PISA, swept 0%, 10%, 25%, 50%, 75%, 100%, with one PISA per compressed night **[assumption]**. Severity never changes A or duration. The realistic frequency is a **range with two published ends** (A14) **[clinical review CR3]**:
  - *Lower end, [Facchinetti 2016]:* 143 artifacts in 108 traces of 7 days (756 sensor-days, about one per 127 h; p.268); probability 0.0014 per sample in 00:00–07:59 and 0.0003 in 08:00–23:59 (p.270). Over 96 night samples that is a PISA on 1 − (1 − 0.0014)^96 ≈ 13% of nights. The two rates are consistent: 0.0014 × 96 + 0.0003 × 192 ≈ 0.19 per day, one per 125 h. These are visually identified artifacts of any depth, and the rate was about halved on clinic days 1 and 4; so this is probably an undercount (our inference, not the paper's).
  - *Upper end, [Lobo 2026]:* calibrate the rate of Lobo's "PISAs of interest" per hour of wear. Table 1 confirms the abstract's counts: 846 in 59,122 h, 89 in 8,189 h and 325 in 26,890 h, one per 70 to 92 h, pooled 1,260 in 94,201 h, about one per 74.8 h (§4.3). The hours are sensor-hours: 405 CGM series from 111 adults with type 1 diabetes, each wearing 2 to 4 Dexcom G7 sensors at once, on the arms and both sides of the abdomen. PISAs were labelled semi-automatically, with a person judging whether a sensor departs from the consensus of the others (Supplement A, as described in the main text). A PISA of interest has a drop of at least 20 mg/dL, a matching rise, lasts 15 to 180 min, has at least one reading below 85 mg/dL and starts at 70 mg/dL or above. The calibration counts injected PISAs with the same tests on the observed CGM (A15); v0.4.0 counted every PISA reaching below 85 mg/dL. On the v0.4.0 cohort that took a PISA on 86% of nights (recomputed at every run), because most simulated PISAs start from higher overnight glucose and never get that low.
  - Why they differ: sensor (G4 Platinum vs. G7), site (abdomen only vs. arms and abdomen), labelling (visual inspection against a second sensor or YSI vs. semi-automatic consensus of 2 to 4 sensors), and what is counted (every artifact vs. only those reaching below 85 mg/dL from a start of at least 70). Lobo's mean starting value for a PISA of interest is 104.9 mg/dL (SD 27.7); the benchmark reports simulated starting glucose against it (face validity, A15).
  - The two ends differ several-fold. Results at a realistic frequency are reported at both (`rq1_realistic_range`), never at one alone. The Lobo-calibrated level stays the D19 training level; `robust_train_facchinetti` fits at the lower end.

### 4.2 Other faults (each switchable, with a severity knob)

| Fault | Model **[assumption]** unless cited; values at full severity (s = 1) | Why include |
|---|---|---|
| Dropout / signal loss | Facchinetti 2016's three-state Markov model once the full text is read. Until then: 4 gaps/day, exponential length with P(gap <20 min) = 0.90 [Facchinetti 2016] (median ≈ 6 min); readings missing | Common in practice; alarms must handle gaps |
| Stale readings | 2/day; last value repeated for 10 to 30 min | Tests trend logic |
| Drift | Linear multiplicative bias reaching ±10 to 20% (× s) at the end of a 10-day sensor, reset at sensor change; labelled once \|bias\| ≥ 5% | Sensor ageing |
| Spikes / noise bursts | 2/day, 15 to 30 min of extra Gaussian noise, SD 20 mg/dL × s | Tests behaviour near threshold |

Overlapping faults are applied in a fixed order (drift, PISA, spikes, stale, dropout). Each sample's `fault_type` is the highest-priority active fault (dropout, stale, PISA, spike, drift); `ghostlows.faults.apply_faults` also returns one row per fault instance (start, end, size), which is what cause attribution uses (BENCHMARK.md §4).

### 4.3 Mixed suite

A single `FaultConfig` combines all faults with one overall severity `s ∈ [0, 1]` that scales rates and magnitudes, plus per-fault overrides. PISAs have their own knob, the fraction of nights (§4.1). The default benchmark sweeps the PISA fraction with the other faults at a fixed moderate level (s = 0.5), and a second sweep raises all faults together.

**Common random numbers.** Each fault type has its own random stream per patient-run, and candidates are drawn at full severity and kept when their uniform draw falls below the severity (thinning). Sweeps are therefore nested: the PISAs at 10% of nights are a subset of those at 25%. Switching one fault type on or off never changes another's realisation. This makes severity curves smooth and the H1 slopes paired.

**Realistic range (A14).** The lower end is `ghostlows.faults.calibrate.FACCHINETTI_FRACTION`, a fixed number from [Facchinetti 2016]'s night rate (§4.1). For the upper end, `ghostlows.faults.realistic_fraction` finds the fraction of nights that reproduces [Lobo 2026]'s rate of PISAs of interest (1,260 in 94,201 sensor-hours, Table 1, about one per 74.8 h), counted with Lobo's definition on the observed CGM, on the simulated cohort itself. It also reports the share of injected PISAs passing each test and their starting glucose. With thinning, the expected rate is exactly linear in the fraction.

### 4.4 Robustness arms

- **Generator mismatch (D8):** test PISAs from perturbed shapes (τ × 0.5 and × 2; depth quantiles × 0.75 and × 1.25) while every detector keeps the nominal model. As built, the τ arms use 5 and 20 min around the nominal 9.1; at 20 min, durations too short for τ are redrawn, so that arm also lengthens PISAs (median 55 vs. 45 min; P12).
- **τ per event (A14):** test PISAs whose P, D and τ are drawn per event from the fitted distributions of §4.1 (log-normal P and D, gamma τ), with the published correlations through a Gaussian copula whose latent correlations are solved to give the published Pearson r. Nothing is redrawn, so durations follow from the parameters (`robust_tau_per_event`).
- **Lag (D1):** the τ = 6 min interstitial signal of §1.

### 4.5 Validity of post-hoc injection (D9)

Injecting faults after simulation assumes the controller never acted on the faulted signal. That holds for open-loop control at night, but a PISA still running at breakfast (onsets from 05:00) would in reality lower the CGM used for the breakfast correction. Report the share of PISAs overlapping a meal bolus. Do not combine post-hoc injection with automated insulin delivery.

## 5. Real-data semi-synthetic track (co-primary for RQ1, D16)

Inject PISAs from the same model into **real** overnight CGM traces (Weinstock 2016; DiaData raw release, deduplicated against Weinstock and D1NAMO; see `DATA.md`) at stable stretches, and score alarms on the injected events. This tests detectors against real sensor noise and real low shapes, though not against real compression. The un-injected CGM is the reference; real, unlabelled PISAs in it bias sensitivity.

As implemented (`experiments/real_data.py`): alarms are fitted on the training folds with PISAs injected on half the nights, then frozen and evaluated at each level. Weinstock uses 2 folds; AZT1D, the H3 track, uses 5. Because the reference lows come from the CGM, the operating point matches level 1 sensitivity, not level 2: the floor catches every CGM-referenced level 2 low by construction (amendment A5). AZT1D carries IOB and COB from user-entered boluses and carbs only (D9). DiaData is not used yet; it is optional, 2.3 GB, and overlaps Weinstock.

## 6. Reproducibility

- Every run is driven by one YAML config, with seeds, and writes its config, git commit hash and benchmark version (`ghostlows-bench v1`, D18) next to its outputs.
- Calibration seeds and benchmark seeds are disjoint.
- Simulated traces are cached as Parquet under `data/sim/` (gitignored), keyed by a config hash. `scripts/package_cohort.py` (`make package`) packages the frozen benchmark cohort for a versioned dataset release; the release itself is pending.
