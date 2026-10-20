# Claims for the clinical co-lead to verify

The clinical claims the code depends on, for the clinical co-lead and any clinician reviewing them ([how to review one](../CONTRIBUTING.md#review-a-clinical-claim)). Tick each item once it has been checked against the full text or with a clinician. Code that depends on an item cites it with `# CLINICAL-REVIEW: <id>`.

- [ ] **CR1. Mechanism.** Reduced local blood flow from compression causes PISAs. [Mensh 2013] says "presumably"; is there direct physiological evidence? [Helton 2011]
- [ ] **CR2. Size and duration.** Median depth 24 mg/dL, duration 45 min [Facchinetti 2016, Dexcom G4]. Do these hold for G6/G7, children, arm vs. abdomen?
- [ ] **CR3. Frequency.** How many nights per week a typical user has a PISA. Only figures found: ~one per 74.8 h below 85 mg/dL [Lobo 2026, abstract counts]; "once every 5 to 6 days" quoted in [Trinity Biotech 2026].
- [ ] **CR4. Labels.** [Baysal 2014] labels were made by an engineer, not a clinician; acceptable as a reference standard?
- [ ] **CR5. AID impact.** Needless suspensions and rebound highs [Baysal 2014; Altnickel 2026]. Any data for Control-IQ, 780G, Omnipod 5?
- [ ] **CR6. Hypoglycaemia levels** (<70, <54, level 3 severe) [IHSG 2017] and the event definition (≥15 min below threshold) [Battelino 2023].
- [ ] **CR7. Time-below-range targets** <4% below 70, <1% below 54 [Battelino 2019].
- [ ] **CR8. Blood-to-interstitial lag** ~5 to 6 min, up to ~10 [Basu 2013, 8 healthy fasted adults]. Longer during falling glucose or in T1D?
- [ ] **CR9. Cost asymmetry.** How many extra false alarms per night is one missed level 2 low worth? Sets the operating point (BENCHMARK.md §5).
- [ ] **CR10. Context signals.** Which are plausible (IOB, COB, exercise), and the fastest plausible real overnight fall rate.
- [ ] **CR11. Other causes of false lows** (dehydration, first-day sensor error, poor perfusion, salicylic acid on Libre). Find primary sources or drop them.
- [ ] **CR12. Safety wording and flag rule** for the upload tool (PRIVACY_AND_SAFETY.md): flags need both methods and a night-time start; is that conservative enough, and is the wording right? On simulated data the rule flags 35% of injected PISAs, raises a median of 4 other flags per 14 days, and in 37% of runs a flag overlaps a real low (PRIVACY_AND_SAFETY.md, as implemented; `results/tables/flag_survey.json`). Since amendment A12 the report no longer shows time below range without flagged readings: flags are annotations and a count, with that performance stated next to them. The A12 version has been live since 2026-10-19. **Sign-off by Cohen Ferrari is still open** for the flag rule, the annotation wording and the plain-words performance text.
- [ ] **CR13. Simulation assumptions** in SIMULATION.md §3 (exercise effect size and duration, sensitivity range, meal error rates).
- [ ] **CR14. G7 alert facts.** Urgent Low fixed at 55 mg/dL; Urgent Low Soon predicts 55 within 20 min; G7 MARD 8.2% arm, 9.1% abdomen [Garg 2022]. The benchmark's ungated floor fires on any reading ≤55 mg/dL (BENCHMARK.md §1): is that how the device alarm behaves?
- [ ] **CR15. Virtual-cohort calibration target.** Under standard meals, each virtual patient's therapy settings are calibrated so that 14-day TBR <70 is within 1–8% and plasma glucose never falls below 40 mg/dL (SIMULATION.md §2). Is this a plausible range for open-loop T1D users?
- [ ] **CR16. Smallest effect size of interest.** H2 calls a context effect meaningful if compression false alarms fall by at least 25% (rate ratio ≤0.75) at matched sensitivity (RESEARCH.md §3). Is 25% the right bar for patients and caregivers?
- [ ] **CR17. How virtual patients treat lows (amendment A6).** The virtual person eats 15 g of fast carbohydrate when the displayed CGM is below 70 mg/dL by day, or at or below 55 mg/dL at night (23:00–07:00, when only the urgent-low alarm is assumed to wake them), rechecks after 15 min, repeats while below 70, and never logs the rescue carbs [CDC 2024; Garg 2022]. Is this a fair picture of open-loop CGM users, by day and at night?
