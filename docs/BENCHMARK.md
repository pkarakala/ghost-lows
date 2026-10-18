# Benchmark specification

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

Alarm events have `patient_id`, `time`, `alarm_name`. A refractory period (default 30 min **[assumption]**) stops one episode from firing many alarms; re-fires inside 15 min are counted as **flicker**.

## 2. Alarms

| Name | Description | Source |
|---|---|---|
| `threshold` | Fires when CGM < 70 (and a 55 variant) | Standard |
| `trend` | Linear extrapolation over the last 15 to 20 min predicts < 55 within 20 min. Stand-in for Dexcom Urgent Low Soon, whose model is not public | [Garg 2022] |
| `baysal_gate` | Trend alarm suppressed when the Baysal rule-based detector flags a PISA (rate-of-change thresholds about −1.9 to −3.1 mg/dL/min) | [Baysal 2014] |
| `matched_filter_gate` | Trend alarm gated by a matched filter for the PISA shape | [Idi 2023] |
| `iforest_gate` | Trend alarm gated by an isolation-forest anomaly score on CGM features | [Idi 2024] |
| `gbm` | Gradient-boosted classifier on causal CGM features predicting a true low within the horizon | [Navarathna 2023] style |
| `*_ctx` variants | Same detectors with IOB, COB and time-of-night features added | Ablation, this project |
| `kalman_pisa` (stretch) | Kalman/HMM filter with an explicit "compressed" state, insulin and meal inputs | after [Facchinetti 2013; Turksoy 2017] |

Reimplementations of published methods follow the papers as closely as their text allows. Any detail the paper does not give is marked in code with `# ASSUMPTION:` and listed in the results.

## 3. Ground truth

- **True low event:** `truth_glucose` < 70 for ≥ 15 consecutive minutes (level 1), or < 54 (level 2); event ends after ≥ 15 min at or above the threshold [Battelino 2023].
- **Fault-caused low:** `cgm_observed` < 70 while `truth_glucose` ≥ 70, labelled by the fault type active at that time.

## 4. Metrics (per patient, then aggregated)

| Metric | Definition |
|---|---|
| **Lows caught** (sensitivity) | Share of true low events with an alarm between 30 min before onset and 15 min after onset **[assumption on window]** |
| **False alarms per day** | Alarms not matched to a true low event, per 24 h of wear, **split by cause**: compression, other fault, no fault (noise) |
| **Warning time** | Onset time minus alarm time, for caught events. Report the median **together with** the miss rate, never alone |
| **Late announcement** | Time-to-alarm on missed-then-caught level 2 lows (for alarms with a safety net) |
| **Flicker** | Re-fires within 15 min |
| **FDA-style alert rates** | True alert rate and detection rate within ±15 min of a reference low, following the definitions in the iCGM special controls [21 CFR 862.1355] and the Libre 3 decision summary [FDA K212132] |

Also produce: sensitivity vs. false-alarms-per-day curves for each alarm across thresholds, and every metric as a function of fault severity.

## 5. Operating point (pre-registered)

Choose each detector's threshold on the **training** patients only, so that level 2 sensitivity is at least that of the CGM-only `trend` alarm on the same training patients (default) **[clinical review: the cost of one missed level 2 low vs. extra false alarms]**. Then report test-fold metrics at that threshold. Commit the operating-point rule to `experiments/configs/` before running the final benchmark.

## 6. Statistics

- **Leave-patients-out cross-validation** over all 30 virtual patients (e.g. 5 folds, stratified by age group). No patient's data in both training and test.
- **Confidence intervals across patients**, not across seeds or runs (patient-level bootstrap, 95%).
- Repeated seeds change scenarios and faults; they do not add independent patients. Report effective sample size honestly.
- Paired comparisons (with vs. without context) use the same patients, scenarios and faults.

## 7. Outputs

`experiments/run_benchmark.py --config experiments/configs/<name>.yaml` writes to `results/<run_id>/`:

- `metrics.csv` (one row per alarm × severity × fold × patient)
- `summary.csv` (aggregated with CIs)
- `figures/` (PNG + SVG): severity curves, sensitivity–false-alarm curves, false-alarm split by cause, example traces
- `config.yaml`, `git_commit.txt`, `assumptions.md` (auto-collected `# ASSUMPTION:` lines)
