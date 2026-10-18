# Benchmark specification

Benchmark version **`ghostlows-bench v1`** (D18): the alarms, truth, metrics, operating point and statistics below, together with the frozen simulation and fault configs. Any change to them that alters results makes a new benchmark version. Decisions D1–D19 and amendments are explained in [`DECISIONS.md`](DECISIONS.md).

## 1. Alarm interface

Every alarm is causal: at each sample time *t* it may use only data up to *t*.

```python
class Alarm(Protocol):
    name: str
    uses_context: bool
    def fit(self, train: pd.DataFrame) -> None: ...          # no-op for rule-based alarms
    def score(self, df: pd.DataFrame) -> pd.Series: ...       # per-sample risk score, causal
    def alarms(self, df: pd.DataFrame, threshold: float) -> pd.DataFrame: ...  # alarm events
```

- `score` is **one scalar per sample**, and `threshold` is the only operating-point parameter (D5). A gated alarm keeps its trend component at the fixed definition in §2 and scores as `1[trend fires] × (1 − gate score)`, so the threshold tunes only the gate.
- **Urgent-low floor (D4):** every alarm also fires, ungated, on any CGM reading ≤55 mg/dL **[assumption, clinical review CR14]**, mirroring the device alarm that cannot be silenced. No gate or context can suppress it. Floor alarms are labelled and reported separately.
- `fit` sees training patients only. Feature normalisation uses training-fold statistics or trailing windows, never a test patient's whole trace (D14).
- Alarm events have `patient_id`, `time`, `alarm_name`, `is_floor`. A refractory period (default 30 min **[assumption]**) stops one episode from firing many alarms; re-fires inside 15 min are counted as **flicker**.

## 2. Alarms

| Name | Description | Source |
|---|---|---|
| `threshold` | Fires when CGM < 70. The 55 variant is the floor alone (`floor_only`) | Standard |
| `trend` | Linear extrapolation over the last 15 to 20 min predicts < 55 within 20 min. Stand-in for Dexcom Urgent Low Soon, whose model is not public | [Garg 2022] |
| `baysal_gate` | Trend alarm suppressed when the Baysal rule-based detector flags a PISA. Uses one pre-specified parameter set from the paper; the others are a sensitivity analysis | [Baysal 2014] |
| `matched_filter_causal_gate` | Trend alarm gated by a matched filter for the PISA shape, using past samples only | causal adaptation of [Idi 2023] |
| `iforest_causal_gate` | Trend alarm gated by an isolation-forest anomaly score on trailing-window CGM features | causal adaptation of [Idi 2024] |
| `gbm` | Gradient-boosted classifier on causal CGM features predicting a true low within the horizon | [Navarathna 2023] style |
| Context arms (D2) | For every detector, four arms that differ only in their inputs: CGM-only, `_time` (+time of day), `_ctx` (+IOB/COB), `_time_ctx` (+both). Each arm passes the detector's output and its extra inputs through the same learned combiner (L2-regularised logistic regression) fitted on training patients; the published rule without a combiner is also reported as the *as published* reference. For `gbm` the arms are its feature sets | Ablation, this project |
| `kalman_pisa` (stretch, RQ3) | Multiple-model Kalman filter with an explicit compressed state, an autocorrelated sensor-error state, and insulin and carbohydrate inputs. Ablations: `kalman_pisa_cgm` (no inputs) and `kalman_nopisa` (no compressed state). Selected by name, not part of `all` (amendment A3) | after [Facchinetti 2013; Turksoy 2017; Mahmoudi 2017; Facchinetti 2016; Breton 2008] |

**Implementation notes (Phase 4).**
- `baysal_gate` uses the paper's rules a–f with its clinically used "trial" parameter set (g′_in −2.0, g′_out −3.1, ratio 1.5, 1 ± 0.3) [Baysal 2014]; the other three sets are a sensitivity analysis. Its Kalman estimate follows the structure in [Cameron 2012]: glucose and rate every minute, updated at readings, reset towards 140 mg/dL after 20 min of dropout. Tuning values are assumptions, because the paper's appendix equations were not available. Readings flagged as PISA do not update the filter. t_PISA,max = 120 min and t_dropout,max = 20 min are assumptions.
- `matched_filter_causal_gate` correlates the last four 5-min CGM changes with the drop phase of the median Facchinetti PISA and scales by relative drop size. It needs about 20 min of the drop, so it is late by construction.
- `iforest_causal_gate` scores five trailing-window features (10-min rate, its 30-min minimum, its change, drop from the 60-min median, CGM) with an isolation forest fitted on training patients; the gate is the training ECDF of the anomaly score.
- Learned alarms are trained on `label` = a true level 1 low ongoing or starting within 30 min, computed by the benchmark from truth (`ghostlows.bench.events.low_labels`). They never see truth columns (`ghostlows.alarms.view`).

**Implementation notes (Phase 9, `kalman_pisa`).**
- *States and modes.* An interacting multiple model filter tracks artifact-free glucose, its unexplained rate (a damped random walk), the compression artifact and its amplitude, and an autocorrelated sensor error [Breton 2008]. The CGM reads glucose + artifact + sensor error + white noise. There are three modes: steady; manoeuvre, where the rate may change 30 times faster, as after a meal, an insulin peak or exercise; and pressure. Pressure is the PISA model of [Facchinetti 2016]: a first-order response to a rectangle, using the generator's time constant, its median PISA's amplitude as the prior mean, and its mean pressure time. Pressure starts at Lobo 2026's rate. Without the manoeuvre mode, a sustained real fall could only be explained as ever-deepening compression; in development this locked the CGM-only filter into "pressure" until the CGM read about 20 mg/dL.
- *Inputs.* Insulin and carbohydrate absorbed per minute (the fall of recorded IOB and COB) times gains from non-negative least squares on training patients. The pooled gains come out at about a third of the simulator's median correction factor: patients differ in sensitivity, and boluses are confounded with meals. This limits what the inputs can add.
- *Score.* The probability, under the mixture of modes, that artifact-free glucose is below 55 mg/dL 20 min ahead. D5 chooses the threshold.
- *Tuning.* The noise settings (white and autocorrelated sensor noise, rate variance) are chosen on 16 training runs per fold by the average precision of the score for the training label, over a fixed grid that includes white noise. Maximum likelihood was tried first and rejected. In development it picked a white-noise, agile filter that tracks compression as glucose: training average precision 0.37 against 0.56, and 1.88 against 0.37–0.57 false alarms per day on held-out patients. Likelihood cannot separate a smooth sensor error from glucose; the simulator's sensor error has SD 11 mg/dL and autocorrelation 0.71 at 15 min and 0.46 at 30 min.
- *What development showed about the compressed state.* With the sensor-error state in place, the pressure mode was inert. Its probability was no higher inside injected PISAs than outside, and larger onset priors only lowered average precision. Dips the size of a PISA are common in the sensor error, so the shape of a dip says little. `kalman_nopisa` measures this on the full benchmark.
- *Development data.* The design choices above were made on the standard mix of the final cohort, including held-out results on one fold. RQ3 is therefore exploratory, and its headline is read on the default mix, which development did not use (amendment A3).

Reimplementations of published methods follow the papers as closely as their text allows. Any detail the paper does not give is marked in code with `# ASSUMPTION:` and listed in the results. Retrospective methods [Idi 2023; Idi 2024; Manzoni 2025] used in real time are **new, causal adaptations** (D7). Every deviation from the paper is documented, their detection latency is reported, and the retrospective originals are scored on the retrospective track.

## 3. Ground truth (D11)

- **True low event (simulation):** on the 1-minute `truth_glucose` (plasma, D1), at least 15 consecutive minutes below 70 (level 1) or below 54 (level 2); the event ends after at least 15 consecutive minutes at or above the threshold [Battelino 2023].
- **CGM-referenced event (real data):** a run of readings below the threshold spanning at least 15 min (first to last reading plus one sampling interval); a gap longer than two sampling intervals ends the run **[assumption]**.
- Level 2 events lie inside level 1 events. Each level is scored separately; false-alarm matching uses level 1 events, so an alarm during any true low is not false.

## 4. Metrics (per patient, then aggregated)

| Metric | Definition |
|---|---|
| **Matching (D12)** | An alarm matches the first event with alarm time in [onset − 30 min, event end]. An event is **caught** if a matched alarm falls in [onset − 30, onset + 15] **[assumption on windows]**. Matched alarms after onset + 15 are **late**, not false. Sensitivity analysis: early window 20/30/45 min, late bound 15/30 min |
| **Lows caught** (sensitivity) | Share of true low events caught, per level |
| **False alarms per day** | Unmatched alarms per 24 h of wear, **split by cause** (D10), assigned at the alarm in this order: *compression* if a PISA was active in [t − 30, t] min; *other fault* if another fault was; *near-event* if within 60 min after a true low ends or 30–60 min before an onset; otherwise *noise* **[assumption on windows]**. Counts per night equal counts per 24 h of wear (D13) |
| **Warning time** | Onset time minus first alarm time, for caught events. Report the median **together with** the miss rate, never alone. As implemented: the median over patient-runs of each run's median warning, with a patient-bootstrap CI (`warning.csv`), because event-level warnings are not stored |
| **Late announcement** | For level 2 lows whose non-floor alarm was suppressed or missed: time from onset to the first alarm, usually the floor (D4) |
| **Flicker** | Re-fires within 15 min |
| **Detection latency** | For gated detectors: time from PISA onset to the gate first flagging it (D7) |
| **Leak (D3)** | AUC of IOB at nocturnal (23:00–07:00) true level 1 onsets vs. all nocturnal samples, per scenario mix and dataset |
| **FDA-style alert rates** | True alert rate and detection rate within ±15 min of a reference low, following the definitions in the iCGM special controls [21 CFR 862.1355] and the Libre 3 decision summary [FDA K212132] |

Also produce: sensitivity vs. false-alarms-per-day curves for each alarm across thresholds (the threshold-free comparison), and every metric as a function of fault severity.

## 5. Operating point (pre-registered, D5)

Choose each alarm's threshold on the **training** patients only: θ\* minimises false alarms per day subject to level 2 sensitivity (floor alarms included) being at least that of the CGM-only `trend` alarm on the same training patients **[clinical review CR9: the cost of one missed level 2 low vs. extra false alarms]**. δ = 0 is primary; a 5-percentage-point non-inferiority margin (δ = 0.05) is a sensitivity analysis. Ties go to the more sensitive threshold. A training fold with fewer than 10 level 2 events is flagged as not estimable **[assumption]**; its thresholds match level 1 sensitivity instead (amendment A7). Report test-fold metrics at θ\*, including the achieved test sensitivity, alongside the threshold-free curves. Commit the operating-point rule to `experiments/configs/` before running the final benchmark. Fitting and threshold choice happen once per fold and scenario mix, on training patients at the training fault level (the realistic default PISA fraction, other faults moderate); the frozen alarms are then evaluated at every sweep level (D19).

*Gated alarms* (`*_gate`) keep the trend alarm's own rule fixed and tune only the gate: the score is 1 − gate where the trend alarm fires (and −∞ where it does not), and the candidate thresholds span every suppression fraction of the training firings, from none to almost all. For the binary Baysal gate this is a choice between the published rule and no suppression. No suppression is the trend alarm itself, so a feasible threshold always exists (amendment A1 in `DECISIONS.md`).

θ\* is searched over training-score quantiles: 30 spaced evenly from the median upwards (from the minimum for gated alarms), plus 15 at log-spaced firing fractions from 5% to 0.01% of training samples, where low alarms operate (amendment A2).

## 6. Statistics (D14)

- **Leave-patients-out cross-validation** over all 30 virtual patients (5 folds, stratified by age group). No patient's data in both training and test.
- **Confidence intervals across patients**, not across seeds or runs: patient-level bootstrap stratified by age group, 2,000 resamples, 95% percentile intervals. They describe variability across this simulator's cohort, not a population.
- Repeated seeds change scenarios and faults; they do not add independent patients. Report effective sample size honestly.
- Paired comparisons (with vs. without context) use the same patients, scenarios and faults.
- Report results by age group and pooled; children dominate low counts.
- Pre-registered decision rules apply only to H1–H3 (RESEARCH.md §3). Everything else is estimation, reported with CIs and no significance claims.
- Report the study in ADEMP form: aims, data-generating mechanisms, estimands, methods, performance measures [Morris 2019].

## 7. Outputs

`experiments/run_benchmark.py --config experiments/configs/<name>.yaml` writes to `results/<run_id>/`:

- `metrics.csv` (one row per alarm × severity × fold × patient)
- `summary.csv` (aggregated with CIs)
- `figures/` (PNG + SVG): severity curves, sensitivity–false-alarm curves, false alarms split by cause, example traces
- `config.yaml`, `git_commit.txt`, `benchmark_version.txt`, `assumptions.md` (auto-collected `# ASSUMPTION:` lines)
- `thresholds.csv` (per fold and mix: chosen threshold, training reference sensitivity, feasibility), `contrasts_h2.csv` and `contrast_h1.csv` (the pre-registered contrasts), `meta.json` (training fault level and the realistic-PISA calibration)

Fold fits and evaluations can run in parallel processes (`workers` in the config, `--workers` on the command line); results do not depend on it (a test compares serial and parallel runs).

`experiments/run_all.py` (part of `make results`) runs every config in `experiments/configs/` that produces results (`rq1_pisa_sweep`, `rq3_kalman`, `rq1_all_faults`, `robust_*`), draws the figures, copies the headline figures and tables to `results/figures/` and `results/tables/` (committed) and writes `results/README.md`.
