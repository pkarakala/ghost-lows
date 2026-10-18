# Phase 3: fault suite

```
Read CLAUDE.md and docs/SIMULATION.md §4–5.
Implement ghostlows.faults: PISA following Facchinetti 2016 (rectangular pressure input through a first-order system; duration median 45 min, 5–95th pct 30–70; depth median 24 mg/dL, 5–95th pct 10–48; fit log-normals to these and store the fitted parameters in config; nocturnal onset window; frequency set by fraction of compressed nights; realistic default calibrated to Lobo 2026, CLINICAL-REVIEW CR3). Also dropout, stale readings, drift and spikes as in §4.2, and a FaultSuite with overall severity s in [0,1] and per-fault overrides. Faults act on cgm_clean to produce cgm_observed and add fault_type and fault_id per sample; they must never modify truth_glucose. Every literature value gets `# SOURCE:`; every chosen value gets `# ASSUMPTION:`.
Write a function that injects PISAs into real overnight traces at stable stretches (semi-synthetic track, §5).
Done when: tests show sampled PISA quantiles match the reported medians and 5th/95th percentiles within tolerance; no fault changes truth_glucose; a figure of example faults is saved to docs/figures/faults_examples.png. Commit and push.
```
