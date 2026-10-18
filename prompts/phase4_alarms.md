# Phase 4: alarms

```
Read CLAUDE.md and docs/BENCHMARK.md §1–2.
Implement ghostlows.alarms with the Alarm protocol: threshold (70 and 55), trend (predict <55 within 20 min; stand-in for G7 Urgent Low Soon, SOURCE Garg 2022, CLINICAL-REVIEW CR14), baysal_gate (SOURCE Baysal 2014), matched_filter_gate (SOURCE Idi 2023), iforest_gate (SOURCE Idi 2024), gbm (Navarathna 2023 style, causal CGM features, predicts a true low within the horizon), and _ctx variants adding IOB, COB and time-of-night. Follow each paper as closely as its text allows; mark every gap `# ASSUMPTION:`. Add a refractory period and flicker tracking.
Done when: a parametrised causality test passes for every alarm (changing future samples never changes past scores), and each alarm has a unit test on a synthetic trace with a known answer. Commit and push.
```
