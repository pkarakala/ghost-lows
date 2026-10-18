# Phase 2: simulation

```
Read CLAUDE.md, docs/SIMULATION.md §1–3 and §6.
Implement ghostlows.sim on simglucose 0.2.11: a 5-minute sensor (copy Dexcom noise parameters, sample_time 5, without editing site-packages), all 30 virtual patients, a basal-bolus controller with carb-ratio and correction boluses, and the scenario families in SIMULATION.md §3 (carb miscounting, missed bolus, skipped meal after bolus, day-level insulin-sensitivity drift, unannounced exercise), each switchable and seeded. Compute IOB and COB the way a pump would (configurable action curve, marked ASSUMPTION).
Inspect the simglucose source and document in docs/SIMULATION_NOTES.md which state `BG` and the CGM read. If they share a compartment, add a configurable blood-to-interstitial first-order lag (5–10 min, SOURCE Basu 2013, CLINICAL-REVIEW CR8).
Output one long table per run in the common schema plus truth_glucose, insulin, carbs, iob, cob, scenario event labels; cache as Parquet under data/sim/ keyed by config hash. Provide experiments/configs/sim_smoke.yaml (2 patients × 2 days) and sim_full.yaml (30 × 14 days, 5 seeds). Parallelise across patients.
Done when: smoke config runs in under a minute; full config runs; a test checks that exercise and sensitivity changes produce lows that IOB alone does not predict (compare low rates with and without them). Commit and push.
```
