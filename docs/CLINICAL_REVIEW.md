# Claims for the clinical co-lead to verify

Tick each item once it has been checked against the full text or with a clinician. Code that depends on an item cites it with `# CLINICAL-REVIEW: <id>`.

- [ ] **CR1. Mechanism.** Reduced local blood flow from compression causes PISAs. [Mensh 2013] says "presumably"; is there direct physiological evidence? [Helton 2011]
- [ ] **CR2. Size and duration.** Median depth 24 mg/dL, duration 45 min [Facchinetti 2016, Dexcom G4]. Do these hold for G6/G7, children, arm vs. abdomen?
- [ ] **CR3. Frequency.** How many nights per week a typical user has a PISA. Only figures found: ~one per 73 h below 85 mg/dL [Lobo 2026]; "once every 5 to 6 days" quoted in [Trinity Biotech 2026].
- [ ] **CR4. Labels.** [Baysal 2014] labels were made by an engineer, not a clinician; acceptable as a reference standard?
- [ ] **CR5. AID impact.** Needless suspensions and rebound highs [Baysal 2014; Altnickel 2026]. Any data for Control-IQ, 780G, Omnipod 5?
- [ ] **CR6. Hypoglycaemia levels** (<70, <54, level 3 severe) [IHSG 2017] and the event definition (≥15 min below threshold) [Battelino 2023].
- [ ] **CR7. Time-below-range targets** <4% below 70, <1% below 54 [Battelino 2019].
- [ ] **CR8. Blood-to-interstitial lag** ~5 to 6 min, up to ~10 [Basu 2013, 8 healthy fasted adults]. Longer during falling glucose or in T1D?
- [ ] **CR9. Cost asymmetry.** How many extra false alarms per night is one missed level 2 low worth? Sets the operating point (BENCHMARK.md §5).
- [ ] **CR10. Context signals.** Which are plausible (IOB, COB, exercise), and the fastest plausible real overnight fall rate.
- [ ] **CR11. Other causes of false lows** (dehydration, first-day sensor error, poor perfusion, salicylic acid on Libre). Find primary sources or drop them.
- [ ] **CR12. Safety wording** for the upload tool (PRIVACY_AND_SAFETY.md).
- [ ] **CR13. Simulation assumptions** in SIMULATION.md §3 (exercise effect size and duration, sensitivity range, meal error rates).
- [ ] **CR14. G7 alert facts.** Urgent Low fixed at 55 mg/dL; Urgent Low Soon predicts 55 within 20 min; G7 MARD 8.2% arm, 9.1% abdomen [Garg 2022].
