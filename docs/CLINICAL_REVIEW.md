# Clinical claims to verify

The clinical claims the code depends on, for anyone checking them against the literature, including clinicians. [How to review one](../CONTRIBUTING.md#review-a-clinical-claim).

**No clinician has reviewed any item, and no step waits for one** (amendment [A20](reference/DECISIONS.md#amendments)). This is simulation research by undergraduate students, not medical advice.

**Sign-offs.** Each item has two, filled in by a maintainer:
- **Literature checked (name, date):** the claim matches its cited sources. Filled in as `Literature checked: <name>, <YYYY-MM-DD>.` Required.
- **Clinician reviewed (name, role, date):** a clinician agrees with the claim. Filled in as `Clinician reviewed: <name>, <role>, <YYYY-MM-DD>.` Optional: future validation, not a requirement.

Items marked **Judgment** (CR9, CR12, CR16, CR17) are clinical judgments a literature check cannot settle. Each is a **literature-anchored assumption, not clinically validated**: it states its anchor (the published sources it rests on) and its sensitivity (the range tested, or why none). Every item, judgment or fact, is ticked once its literature check is in. A test rejects a ticked sign-off without its names and date, a filled-in one that is not ticked, an item ticked without its literature check, and a judgment without its anchor and sensitivity.

- [x] **CR1. Mechanism.** Reduced local blood flow from compression causes PISAs. [Mensh 2013] says "presumably"; is there direct physiological evidence? [Helton 2011]
  - [Mensh 2013] (healthy nondiabetic adults, four abdominal sensors, sleeping position from video) found aberrant readings strongly correlated with lying on the sensor, mostly sudden decreases, "presumably due to local blood-flow decreases caused by tissue compression" (abstract). [Helton 2011] gives the theoretical framework: pressure-induced stresses change tissue physiology around the sensor, including blood flow and oxygen, and acute forces can change the signal temporarily (abstract). Neither measures the mechanism directly; the claim stands as a hypothesis, worded "thought to".
  - [x] Literature checked: Cohen Ferrari, 2026-11-22.
  - [ ] Clinician reviewed (name, role, date)
- [x] **CR2. Size and duration.** Median depth 24 mg/dL, duration 45 min [Facchinetti 2016, Dexcom G4]. Do these hold for G6/G7, children, arm vs. abdomen?
  - Confirmed for the Dexcom G4 Platinum on the abdomen: 72 people, sensors on the left and right abdomen, 143 artifacts; depth (the peak deviation A) median 24 mg/dL (10–48), duration 45 min (30–70) [Facchinetti 2016, abstract and pp.266–268]. Still open, with no source found: G6/G7, children, the arm.
  - [x] Literature checked: Cohen Ferrari, 2026-11-21.
  - [ ] Clinician reviewed (name, role, date)
- [x] **CR3. Frequency.** How many nights per week a typical user has a PISA. Figures found: ~one per 74.8 h below 85 mg/dL [Lobo 2026, Table 1, sensor-hours]; "once every 5 to 6 days" quoted in [Trinity Biotech 2026]; 143 artifacts in 756 sensor-days (about one per 127 h) and 0.0014 per sample at 00:00–07:59, a PISA on about 13% of nights [Facchinetti 2016, pp.268, 270].
  - Notes (A14): the sources disagree several-fold. Counted as Lobo counts, the cohort cannot reach Lobo's rate even with a PISA every night (0.200 vs. 0.321 per day), so the upper end is capped at 100% of nights (v0.4.0, counting every PISA below 85 mg/dL, needed 86%); Facchinetti's rate gives about 13%. They differ in sensor (Dexcom G4 Platinum vs. G7), site (abdomen vs. arms and abdomen), labelling (visual inspection against a second sensor or YSI, in a trial with clinic nights, vs. semi-automatic labelling against the consensus of 2 to 4 sensors, Lobo's Supplement A) and what is counted (every artifact, about one per 127 sensor-hours, vs. only "PISAs of interest": a drop of at least 20 mg/dL from a start of at least 70 to below 85, a matching rise, 15 to 180 min; one per 74.8 sensor-hours) (A15). The benchmark reports both ends as a range and calls neither alone "realistic". Which end fits a typical home user is the open question.
  - [x] Literature checked: Cohen Ferrari, 2026-11-21.
  - [ ] Clinician reviewed (name, role, date)
- [x] **CR4. Labels.** [Baysal 2014] labels were made by an engineer, not a clinician; acceptable as a reference standard?
  - Confirmed: the reference labels came from "visual inspection of all data points by an expert engineer", with no reference glucose available; about 3% of readings (3,267) were marked [Baysal 2014, p.1093]. [Navarathna 2023] reused the same labelled 1,125 nights. Whether that is an acceptable reference standard is the clinician's question.
  - [x] Literature checked: Cohen Ferrari, 2026-11-22.
  - [ ] Clinician reviewed (name, role, date)
- [x] **CR5. AID impact.** Needless suspensions and rebound highs [Baysal 2014; Altnickel 2026]. Any data for Control-IQ, 780G, Omnipod 5?
  - [Baysal 2014] confirms that PISAs caused unnecessary pump shut-offs that "led to higher than desired morning glucose levels" (p.1092), on a predictive low-glucose-suspend system (Medtronic MiniMed Paradigm REAL-Time Veo with Enlite). [Altnickel 2026] confirms the pattern on a current hybrid closed-loop system (CamAPS FX with a mylife YpsoPump and FreeStyle Libre 3): compression lows prompted automated insulin reduction or suspension, followed by rebound hyperglycemia; 18 manual correction boluses and nocturnal interventions on 12 of 14 nights. It is a single case (one 10-year-old over 14 days), described by the author as hypothesis-generating. Still no data found for Control-IQ, 780G or Omnipod 5.
  - [x] Literature checked: Cohen Ferrari, 2026-11-22.
  - [ ] Clinician reviewed (name, role, date)
- [x] **CR6. Hypoglycaemia levels** (<70, <54, level 3 severe) [IHSG 2017] and the event definition (≥15 min below threshold) [Battelino 2023].
  - Levels confirmed against [IHSG 2017], Table 1. Event rules confirmed against [Battelino 2023] (*Lancet Diabetes Endocrinol* 2023;11:42–57): an event starts after at least 15 consecutive minutes below the threshold and ends after at least 15 consecutive minutes at or above it, as in `bench/events.py`. IHSG words level 1 as "≤70 mg/dL", Battelino 2023 as "<70"; the benchmark follows Battelino 2023.
  - [x] Literature checked: Cohen Ferrari, 2026-11-21.
  - [ ] Clinician reviewed (name, role, date)
- [x] **CR7. Time-below-range targets** <4% below 70, <1% below 54 [Battelino 2019].
  - Confirmed against [Battelino 2019], Table 1: <4% of time below 70 mg/dL and <1% below 54 for type 1 and type 2 diabetes; <1% below 70 for older or high-risk people.
  - [x] Literature checked: Cohen Ferrari, 2026-11-21.
  - [ ] Clinician reviewed (name, role, date)
- [x] **CR8. Blood-to-interstitial lag** ~5 to 6 min [Basu 2013, 8 healthy fasted adults]. Longer during falling glucose or in T1D?
  - [Basu 2013] confirms 5.3 to 6.2 min in 8 healthy, overnight-fasted adults (abdominal microdialysis). It does not support "up to ~10 min", which is removed. Basu notes that the lag may differ between rising and falling glucose, citing other work. No code change.
  - [x] Literature checked: Cohen Ferrari, 2026-11-21.
  - [ ] Clinician reviewed (name, role, date)
- [ ] **CR9. Cost asymmetry.** How many extra false alarms per night is one missed level 2 low worth? Sets the operating point ([BENCHMARK.md](reference/BENCHMARK.md) §5).
  - **Judgment: literature-anchored assumption, not clinically validated.** Anchor: level 2 (<54 mg/dL) marks serious, clinically important hypoglycaemia [IHSG 2017]; false alarms cause alarm fatigue [Shivers 2013]. No published source gives an exchange rate between missed level 2 lows and false alarms. Default: no loss of level 2 sensitivity against the trend alarm (δ = 0). Sensitivity: δ = 0.05 (pre-registered) and the curves at 95% and 99% retention (A11); the reader picks the trade-off.
  - [ ] Literature checked (name, date)
  - [ ] Clinician reviewed (name, role, date)
- [ ] **CR10. Context signals.** Which are plausible (IOB, COB, exercise), and the fastest plausible real overnight fall rate.
  - [ ] Literature checked (name, date)
  - [ ] Clinician reviewed (name, role, date)
- [ ] **CR11. Other causes of false lows** (dehydration, first-day sensor error, poor perfusion, salicylic acid on Libre). Find primary sources or drop them.
  - [ ] Literature checked (name, date)
  - [ ] Clinician reviewed (name, role, date)
- [ ] **CR12. Safety wording and flag rule** for the upload tool ([PRIVACY_AND_SAFETY.md](PRIVACY_AND_SAFETY.md)): flags need both methods and a night-time start; is that conservative enough, and is the wording right? On simulated data the rule flags 36% of injected PISAs, raises a median of 3.5 other flags per 14 days, and in 37% of runs a flag overlaps a real low ([PRIVACY_AND_SAFETY.md, as implemented](reference/UPLOAD_REPORT.md#as-implemented); `results/tables/flag_survey.json`). Since amendment [A12](reference/DECISIONS.md#amendments) the report no longer shows time below range without flagged readings: flags are annotations and a count, with that performance stated next to them. The [A12](reference/DECISIONS.md#amendments) version has been live since 2026-10-19. A clinician's sign-off on the flag rule, the annotation wording and the plain-words performance text would be optional validation (A20).
  - **Judgment: literature-anchored assumption, not clinically validated.** Anchor: none; no consensus source on labelling suspected artifacts in a retrospective report was found. Safety rests on design: flags only annotate and never lower a number (A12), and every page with flags tells the user to check with a fingerstick and follow their care plan. Sensitivity: the flag rule's performance on simulated data is stated beside the flags. The report is a research demonstration; use with real patients would need clinical and usability review, which this project does not claim.
  - [ ] Literature checked (name, date)
  - [ ] Clinician reviewed (name, role, date)
- [ ] **CR13. Simulation assumptions** in [SIMULATION.md](reference/SIMULATION.md) §3 (exercise effect size and duration, sensitivity range, meal error rates).
  - [ ] Literature checked (name, date)
  - [ ] Clinician reviewed (name, role, date)
- [x] **CR14. G7 alert facts.** Urgent Low fixed at 55 mg/dL; Urgent Low Soon predicts 55 within 20 min; G7 MARD 8.2% arm, 9.1% abdomen [Garg 2022]. The benchmark's ungated floor fires on any reading ≤55 mg/dL ([BENCHMARK.md](reference/BENCHMARK.md) §1): is that how the device alarm behaves?
  - The US Dexcom G7 User Guide [Dexcom 2026] says Urgent Low fires "when your sensor reading is 55 mg/dL or below", and Urgent Low Soon when the reading "will be 55 mg/dL or below in less than 20 minutes", even while glucose is in range. [Garg 2022] confirms MARD 8.2% (arm) and 9.1% (abdomen). The ungated floor (any reading ≤55 mg/dL) matches the device. The device's "≤55" differs from the trend alarm's predicted "<55"; the difference is negligible, and nothing changes.
  - [x] Literature checked: Cohen Ferrari, 2026-11-21.
  - [ ] Clinician reviewed (name, role, date)
- [ ] **CR15. Virtual-cohort calibration target.** Under standard meals, each virtual patient's therapy settings are calibrated so that 14-day TBR <70 is within 1–8% and plasma glucose never falls below 40 mg/dL ([SIMULATION.md](reference/SIMULATION.md) §2). Is this a plausible range for open-loop T1D users?
  - [ ] Literature checked (name, date)
  - [ ] Clinician reviewed (name, role, date)
- [ ] **CR16. Smallest effect size of interest.** [H2](reference/RESEARCH.md#3-hypotheses-fixed-before-running-the-full-benchmark-frozen-by-the-git-tag-protocol-v1) calls a context effect meaningful if compression false alarms fall by at least 25% (rate ratio ≤0.75) at matched sensitivity ([RESEARCH.md](reference/RESEARCH.md) §3). Is 25% the right bar for patients and caregivers?
  - **Judgment: literature-anchored assumption, not clinically validated.** Anchor: none; no published minimal important reduction in CGM false alarms was found. Default: 25% (frozen). Sensitivity (post hoc, A20, `results/tables/sesoi_sensitivity.csv`): on the default mix the null holds at every PISA level for any SESOI of 20% or more. At 15%, `trend` is inconclusive at 2 of 5 levels; at 10%, `trend` (rate ratio about 0.89) is a meaningful reduction at 4 of 5 levels. The H2 null therefore holds only for a bar of about 20% or more.
  - [ ] Literature checked (name, date)
  - [ ] Clinician reviewed (name, role, date)
- [ ] **CR17. How virtual patients treat lows (amendment [A6](reference/DECISIONS.md#amendments)).** The virtual person eats 15 g of fast carbohydrate when the displayed CGM is below 70 mg/dL by day, or at or below 55 mg/dL at night (23:00–07:00, when only the urgent-low alarm is assumed to wake them), rechecks after 15 min, repeats while below 70, and never logs the rescue carbs [CDC 2024; Garg 2022]. Is this a fair picture of open-loop CGM users, by day and at night?
  - **Judgment: literature-anchored assumption, not clinically validated.** Anchor: the 15-15 rule [CDC 2024]; the urgent-low alarm is fixed at 55 mg/dL [Garg 2022; Dexcom 2026]. No source found on how often users wake to a low alarm. Default: as above. Sensitivity: none run; a different night trigger is proposal P5 and needs a rerun. Real people treat less regularly (RESEARCH.md §6).
  - [ ] Literature checked (name, date)
  - [ ] Clinician reviewed (name, role, date)
