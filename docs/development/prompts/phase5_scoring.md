# Phase 5: scoring and benchmark runner

```
Read CLAUDE.md and docs/BENCHMARK.md §3–7.
Implement ghostlows.bench: true low events (≥15 min below 70 / 54, SOURCE Battelino 2023), alarm-to-event matching, lows caught, false alarms per day split by cause (compression, other fault, none), warning time reported with miss rate, late announcement, flicker, FDA-style true alert rate and detection rate within ±15 min (SOURCE 21 CFR 862.1355, FDA K212132). Leave-patients-out CV stratified by age group, the pre-registered operating-point rule (level 2 sensitivity ≥ CGM-only trend on training patients, configurable, CLINICAL-REVIEW CR9), and patient-level bootstrap 95% CIs.
Write experiments/run_benchmark.py producing exactly the outputs in BENCHMARK.md §7, including assumptions.md built by collecting `# ASSUMPTION:` lines from the code.
Done when: scoring tests on hand-built traces with known answers pass, and the smoke config runs end to end. Commit and push.
```
