# Research plan

The research questions, hypotheses, novelty claim and limitations; for researchers and reviewers judging the claims. Citations in [brackets] resolve to entries in [`CITATIONS.md`](../CITATIONS.md). Items marked **[clinical review]** are listed in [`CLINICAL_REVIEW.md`](../CLINICAL_REVIEW.md). Design decisions D1–D19, amendments A1–A13 and proposed amendments P4–P9 (P1–P3 adopted as A10–A12), with their evidence, are in [`DECISIONS.md`](DECISIONS.md).

## 1. Definitions

| Term | Definition used in this project | Source |
|---|---|---|
| **PISA / compression low** | A transient, mostly downward deviation of the CGM signal caused by pressure on the sensor site, typically during sleep. | [Mensh 2013; Facchinetti 2016; Baysal 2014] |
| **Ghost low** | A CGM low reading, or a low alarm, caused by a sensor artifact rather than by low blood glucose. Not an established term; we define it here and map it to PISA plus the other faults in the suite. | This project |
| **Level 1 / level 2 hypoglycaemia** | Glucose <70 mg/dL / <54 mg/dL. **[clinical review CR6]** | [IHSG 2017; Battelino 2019] |
| **True low event (simulation)** | Plasma glucose below the threshold for at least 15 consecutive minutes, ending after at least 15 consecutive minutes at or above it, computed on the 1-minute plasma signal (D1, D11). **[clinical review CR6]** | [Battelino 2023] |
| **CGM hypoglycaemic event (real data)** | The same rule applied to CGM readings: a run below the threshold spanning at least 15 minutes (D11). | [Battelino 2023] |
| **Real-time alarm** | A decision at time *t* that uses only data up to *t*. | This project |
| **Context** | Insulin on board (IOB) and carbohydrates on board (COB), computed only from recorded doses and announced carbohydrates, never from simulator truth. Time of day is *not* context: every CGM user has it, so it is a separate arm of the ablation (D2). | This project |
| **Target population (RQ2)** | People on open-loop insulin delivery who record boluses and carbohydrates: multiple daily injections with a connected pen, or a pump without automated adjustment (D9). With automated insulin delivery, insulin delivery itself responds to the CGM, artifacts included. | This project |

## 2. Primary research question

> **How much do sensor faults, especially compression artifacts, degrade real-time CGM low-glucose alarms on lows caught, false alarms per day and warning time, and how much of that degradation does insulin and carbohydrate context recover at a fixed level of safety?**

### RQ1. Fault impact

How much do compression and other sensor faults degrade existing low alarms (threshold, trend, Baysal rules [Baysal 2014], matched filter [Idi 2023], isolation forest [Idi 2024], gradient boosting [Navarathna 2023]) on lows caught, false alarms per day and warning time, as fault severity rises? Answered in simulation and, because simulated lows are the least trustworthy part of the simulator, also on real CGM lows with injected compression artifacts (§7, D16).

### RQ2. Value of context

**Estimand.** In the target population, at matched level 2 sensitivity, the ratio of compression false alarms per night with versus without IOB/COB, with time of day available in both arms (D2, D5). Report the compression and non-compression parts separately, and report the ratio at three levels of how much of the nocturnal hypoglycaemia recorded insulin can explain (D3).

*Why this split matters:* a method can cut false alarms by filtering ordinary noise near 70 mg/dL without touching compression. A ghost-low method has to move the compression column.

### RQ3. Model-based versus discriminative

Does a filter with an explicit "compressed" hidden state plus insulin and meal inputs [after Facchinetti 2013; Turksoy 2017] beat the best discriminative detector, and does either hold up on real data?

*Operationalised (exploratory, amendment A3; no decision rule).* `kalman_pisa` against the discriminative alarm with the same inputs (the five `_combined_ctx` arms and `gbm_ctx`), chosen in each fold as the one with the fewest false alarms per day on that fold's training patients at its D5 operating point; test results play no part in the choice. The CGM-only `kalman_pisa_cgm` is compared in the same way with the CGM-only arms and `gbm`. Estimands, per mix and fault level with a paired patient bootstrap: the ratio of false alarms (all, and compression), and the difference in level 2 sensitivity. Two ablations: `kalman_pisa` against `kalman_nopisa` (what the compressed state adds) and against `kalman_pisa_cgm` (what the inputs add). The headline is the default mix. On real data, `kalman_pisa_cgm` runs on the semi-synthetic Weinstock track alongside the CGM-only alarms.

## 3. Hypotheses (fixed before running the full benchmark; frozen by the git tag `protocol-v1`)

- **H1 (fault impact).** For each CGM-only alarm, the per-patient least-squares slope of false alarms per day against the fraction of compressed nights is summarised across patients (median, 95% patient-bootstrap CI). That false alarms rise for threshold alarms follows by construction, because artifacts only lower the CGM, so this is a check, not a finding. The hypothesis is that **trend alarms degrade faster**: the paired slope difference (trend − threshold) is positive, with a CI that excludes 0.
- **H2 (value of context).** Primary contrast: the rate ratio RR = compression false alarms per night of [CGM + time + IOB/COB] over [CGM + time], at the pre-registered operating point, per detector, on the default scenario mix, with a paired patient-bootstrap CI. Smallest effect size of interest: RR = 0.75, a 25% reduction **[assumption, clinical review CR9]**. It is relative because absolute rates scale with the assumed PISA frequency. Reading: *meaningful reduction* if the CI's upper bound is below 1 and the point estimate is ≤0.75; *no meaningful reduction* if the CI's lower bound is above 0.75; otherwise *inconclusive*. Secondary: RR is closer to 1 on the high-perturbation mix than on the standard mix.
- **H3 (real data).** The context benefit shrinks on real data: RR on semi-synthetic AZT1D nights (real CGM, recorded user-entered boluses and carbs, injected compression) is closer to 1 than in simulation at a matched unexplained-low fraction (D3). Real compression artifacts already present in AZT1D are unlabelled and contaminate the reference; this is stated as a limitation of H3. *Operationalised before any AZT1D result (amendment A4):* the matched mix is the simulated mix with the closest leak AUC; per detector at PISA on every night, H3 holds when |log RR| is smaller on AZT1D; descriptive, with both CIs reported.

The benchmark is the contribution whichever way H2 comes out.

## 4. What is new, and why

**Prior work.**
- **Mechanism and size.** Compression lows are typically shallow (median depth 24 mg/dL) and short (median 45 min) [Facchinetti 2016]. They occur mostly overnight. They are long enough to meet the consensus definition of a CGM hypoglycaemic event [Battelino 2023]. They cause false overnight alarms, which contribute to alarm fatigue [Shivers 2013]. Inside automated insulin delivery they can trigger needless insulin suspensions followed by high morning glucose [Baysal 2014] **[clinical review CR5]**.
- **Rule-based detection.** Real-time, rule-based PISA detection on real data [Baysal 2014].
- **Machine learning.** Machine-learning detectors include gradient boosting [Navarathna 2023]. A prospective detector of PISA onset is scored by PR-AUC [Lobo 2026].
- **Retrospective, CGM-only detectors.**
  - Matched filter [Idi 2023].
  - Isolation forest, on simulated data and on 36 adults wearing two sensors [Idi 2024].
  - A Bayesian smoothness approach [Manzoni 2025].
- **Model-based fault detection.** Model-based sensor-fault detection uses insulin and meal inputs [Facchinetti 2013; Turksoy 2017]. Fault-tolerant prediction uses insulin and carbs [Sanchez 2025].
- **Patents.**
  - On PISA-aware alarm handling [US 2024/0139415; US 2024/0138770].
  - On gating low alarms with insulin and carb context [US 11,406,331; US 9,119,528; US 10,231,659].
- **Commercial.** A commercial multi-sensor approach with no published metrics [Trinity Biotech 2026].

Novelty was assessed on 2026-10-18 from abstracts, full texts where available, and a patent scan that read summaries, not claims. Confidence: medium. `CITATIONS.md` says what was and was not read.

Compression-low detection itself is established (above), and detecting it from CGM values alone is well covered. What does not exist is:

1. **An open benchmark that scores low alarms, not detectors.** Prior work reports detector metrics such as sensitivity, false positives per day or PR-AUC [Idi 2024; Manzoni 2025; Lobo 2026]. [Lobo 2026] detects PISA onset prospectively, to inform "canceling of hypoglycemia alarms", but scores the detector by PR-AUC. None scores each real-time *alarm* on lows caught, false alarms per day and minutes of warning together, under a *mixed* fault suite with adjustable severity. Fault-injection testbeds exist for controllers and generic faults but have no PISA model [Zhou 2021; APS_TestBed 2022]. CGM benchmarks are about forecasting and have no sensor faults [GlucoBench 2024; GlucoFM-Bench 2026; MetaboNet-Bench 2026]. *To check before claiming:* whether the commercial UVA/Padova simulator's sensor models include PISA (Facchinetti 2016 aims to add these artifacts to simulators; see also US 10,546,659), and the full text of [Lobo 2026] (PMC13486385).
2. **A controlled ablation of insulin and carb context at alarm time.** Context-based alarm gating is claimed in product patents (above), but no open study measures, detector by detector and at a fixed safety level, how much context adds over CGM-only methods.
3. **A simulation that varies how much insulin explains.** In simglucose every low is caused by the insulin model the context features read. Yet in a pilot, bolus IOB barely separated nocturnal low onsets from other night-time moments (AUC 0.54, DECISIONS.md). How much context can help is therefore an empirical question. The scenario mixes vary it on purpose (unannounced exercise, sensitivity changes, meal errors) and report the result as an axis (D3).
4. **Fault realism from the literature.** Compression is injected from the published PISA model [Facchinetti 2016], as used by [Idi 2024], instead of hand-made shapes.

**Patent note.** Publishing a benchmark and comparing methods carries little patent risk. Risk grows only if the upload tool becomes a product that suppresses or gates real alarms. Hence: the tool stays retrospective, uses the label "possible compression artifact", ships under an open licence with a no-medical-use disclaimer, and the university tech-transfer office is consulted before any commercial or clinical use. This is not a legal opinion.

## 5. Scope

**In scope:** simulated benchmark; real-data checks on public datasets; CGM-only and context-aware baselines; an in-browser upload dashboard.

**Out of scope for now:** prospective data collection, any change to real device alarms, clinical claims, and the literature write-up (to be done separately after fact-checking).

## 6. Known limitations to state up front

- **Simulated hypoglycaemia is the weakest part of the simulator.** simglucose implements the 2008 UVA/Padova model [simglucose; Kovatchev 2009]. It lacks the 2013 model's nonlinear rise of insulin action in hypoglycaemia and its glucagon counter-regulation [Dalla Man 2014]. Those equations are published, but the parameter values needed to add them are not. Hence the real-data validation in §7 (D16).
- Virtual patients treat lows with a fixed rule (15 g when the fault-free CGM is below 70 mg/dL by day or at or below 55 at night, never logged; amendment A6). Real people treat less regularly. Without any treatment the 2008 model gives impossible hypoglycaemia, so the rule is needed, but it shapes how long and how deep simulated lows are **[clinical review CR17]**. Its night trigger (≤55 mg/dL) is the urgent-low floor and the trend alarm's target, and its day trigger (<70) is the threshold alarm's, so true lows tend to end where the alarms fire; a decoupled arm is proposed (P5).
- The three scenario mixes span a narrow range of how much recorded insulin explains nocturnal lows: leak AUC 0.69, 0.65 and 0.63 (SIMULATION_NOTES.md). The secondary H2 comparison and H3 therefore compare modestly different worlds, and AZT1D's real 0.59 lies outside the simulated range.
- The "realistic" training fault level reproduces Lobo 2026's rate of PISAs reaching below 85 mg/dL. In the treated cohort that takes a PISA on 86% of nights, because most simulated PISAs start from higher overnight glucose and never get that low. Alarms are fitted with compression on most nights (D19).
- The stock controller settings give implausible hypoglycaemia in several virtual patients (DECISIONS.md, pilot). Therapy settings are calibrated per patient to a pre-specified range (D17); that range is itself an assumption **[clinical review CR15]**.
- 30 virtual patients and one shared CGM noise model [simglucose; Breton 2008]. The noise is smooth (AR(1) on a 15-minute grid, cubic-interpolated), so sample-level noise and spikes are gentler than in real sensors. Confidence intervals describe this cohort, not a population.
- The model's blood-to-interstitial lag (τ = 1/ksc, 6.6–19.9 min, median about 11) is longer than the 5–6 min measured in healthy fasted adults [Basu 2013], so simulated warning times are pessimistic; a sensitivity arm uses 6 min (D1).
- No public dataset has PISA labels. The one labelled real set (36 adults, two G6 sensors) is held by Padova [Idi 2024].
- Insulin and carb context exists only for pump/AID users or people who log; many standalone G7 users have none. AZT1D, the H3 data, comes from users of automated insulin delivery, not the open-loop population RQ2 targets (D9).
- The pre-registered results are read at one operating point (D5, δ = 0: no loss of training level 2 sensitivity against the trend alarm). The curves across thresholds the protocol calls for were added only after the v0.1.0 results had been seen (amendment A11), so they are secondary. They show that the gates start removing compression false alarms only once some level 2 lows are given up, and that H2 reads the same at 95% and 99% retention. Amendment A13, also post hoc: No published gate gave fewer total false alarms than the retuned trend alarm at any estimable point; the isolation-forest and Baysal gates gave more at most (6 of 8 and 2 of 3). Comparisons are at matched held-out sensitivity (an oracle, not a deployable operating point), cover 18 of 60 planned points, are uncorrected for multiplicity and say nothing about the standard mix. The matched-filter gate could not be compared (its curve reaches only 3 of its 15 planned points, all unstable).
- Learned alarms choose their threshold on scores from the patients they were fitted on, which is optimistic (P6). The RQ3 comparator is chosen from the same in-sample rates.
- The matched filter, the flag rule and the Kalman filter's pressure mode use the same PISA model that generates the injected artifacts, so they have a home advantage that real artifacts would not give them. The τ-mismatch arms test part of this, but not for the Kalman alarms (P7).
- The realistic training PISA fraction is calibrated on the whole default-mix cohort, test patients included (a fault-generator setting, not outcome information; P8).
- False alarms are attributed to the first fault active in the 30 min before them. Drift labels cover long stretches, so some alarms that sensor noise alone would have caused may be counted as "other fault".
- On the real-data tracks the reference lows come from the same CGM the alarms read, so lows caught there is near-circular. Only the false alarms caused by injected PISAs are informative.
- There is no G7-specific PISA data in the literature found so far; the injected artifacts come from Dexcom G4 data [Facchinetti 2016]. The model's time constant and the mapping from reported artifact size to model inputs await the full text (SIMULATION.md §4.1).
- The Dexcom Urgent Low Soon prediction model is not public; the trend alarm here is a stand-in (predict 55 mg/dL within 20 min) [Garg 2022].

## 7. Validation strategy

1. **Real lows with injected artifacts (co-primary for RQ1).** Inject PISAs from the same model into real overnight CGM (Weinstock 2016; DiaData raw, deduplicated) and score every alarm. Truth is the un-injected CGM, so false alarms caused by the injected artifacts can be attributed exactly. Real, unlabelled PISAs in the reference bias sensitivity, and lows caught on this track is near-circular (§6). DiaData is not used yet (optional, 2.3 GB, and overlaps Weinstock).
2. **Face validity of simulated lows.** Compare simulated nocturnal true lows (fall rate in the 30 min before onset, nadir, duration) and the overnight glucose distribution (the share of the night in 70–95 mg/dL, where a median-depth artifact creates a false low) with real CGM (Weinstock 2016, DiaData). Report the comparison whatever it shows.
3. **Labelled real data.** Request access to the dual-sensor set with PISA labels [Idi 2024] from the Padova group. Until then, real-data results report rates and agreement between detectors, not accuracy.
