# Research plan

Citations in [brackets] resolve to entries in [`CITATIONS.md`](CITATIONS.md). Items marked **[clinical review]** are listed in [`CLINICAL_REVIEW.md`](CLINICAL_REVIEW.md).

## 1. Definitions

| Term | Definition used in this project | Source |
|---|---|---|
| **PISA / compression low** | A transient, mostly downward deviation of the CGM signal caused by pressure on the sensor site, typically during sleep. | [Mensh 2013; Facchinetti 2016; Baysal 2014] |
| **Ghost low** | A CGM low reading, or a low alarm, caused by a sensor artifact rather than by low blood glucose. Not an established term; we define it here and map it to PISA plus the other faults in the suite. | This project |
| **Level 1 / level 2 hypoglycaemia** | Glucose <70 mg/dL / <54 mg/dL. **[clinical review]** | [IHSG 2017; Battelino 2019] |
| **CGM hypoglycaemic event** | At least 15 consecutive minutes below the threshold; ends after at least 15 min at or above it. **[clinical review]** | [Battelino 2023] |
| **Real-time alarm** | A decision at time *t* that uses only data up to *t*. | This project |
| **Context** | Insulin on board (IOB), carbohydrates on board (COB) and time of night, as available to a pump/AID or logging user. | This project |

## 2. Primary research question

> **How much do sensor faults, especially compression artifacts, degrade real-time CGM low-glucose alarms on lows caught, false alarms per day and warning time, and how much of that degradation does insulin and carbohydrate context recover at a fixed level of safety?**

### RQ1. Fault impact

How much do compression and other sensor faults degrade existing low alarms (threshold, trend, Baysal rules [Baysal 2014], matched filter [Idi 2023], isolation forest [Idi 2024], gradient boosting [Navarathna 2023]) on lows caught, false alarms per day and warning time, as fault severity rises?

### RQ2. Value of context

At a fixed sensitivity on level 2 lows, how many compression false alarms per night does adding insulin and carb context remove? Report the compression and non-compression parts of the reduction separately.

*Why this split matters:* in the original proof of concept, 82% of the false-alarm reduction came from ordinary noise near 70 mg/dL rather than from compression. A ghost-low method has to move the compression column, not just filter noise.

### RQ3. Model-based versus discriminative

Does a filter with an explicit "compressed" hidden state plus insulin and meal inputs [after Facchinetti 2013; Turksoy 2017] beat the best discriminative detector, and does either hold up on real data?

## 3. Hypotheses (fixed before running the full benchmark)

- **H1.** False alarms per day rise for every CGM-only alarm as the fraction of compressed nights rises, and trend alarms degrade faster than threshold alarms because they react to the drop rate.
- **H2.** At a fixed level 2 sensitivity, context reduces compression false alarms per day by a meaningful amount (effect size and confidence interval reported, no fixed target), and the reduction is smaller on scenarios with unannounced exercise and insulin-sensitivity changes than on standard scenarios.
- **H3.** The context benefit measured in simulation shrinks on real data, because real lows have causes that IOB does not see.

Null results are results. The benchmark is the contribution whichever way H2 comes out.

## 4. What is new, and why

**Summary.** Compression-low detection itself is established [Baysal 2014; Navarathna 2023; Idi 2023; Idi 2024; Manzoni 2025; Lobo 2026], and detecting it from CGM values alone is well covered. What does not exist is:

1. **An open benchmark that scores low alarms, not detectors.** Prior work reports detector metrics such as sensitivity, false positives per day or PR-AUC [Idi 2024; Manzoni 2025; Lobo 2026]. None scores each real-time *alarm* on lows caught, false alarms per day and minutes of warning together, under a *mixed* fault suite with adjustable severity. Fault-injection testbeds exist for controllers and generic faults but have no PISA model [Zhou 2021; APS_TestBed 2022]. CGM benchmarks are about forecasting and have no sensor faults [GlucoBench 2024; GlucoFM-Bench 2026; MetaboNet-Bench 2026].
2. **A controlled ablation of insulin and carb context at alarm time.** Context-based alarm gating is claimed in product patents [US 11,406,331; US 9,119,528; US 10,231,659; US 2024/0139415], but no open study measures, detector by detector and at a fixed safety level, how much context adds over CGM-only methods.
3. **A simulation design that avoids insulin leakage.** In simglucose every low is caused by the insulin model the context features read. Adding lows that insulin does not explain (unannounced exercise, sensitivity changes, meal errors) is needed for an honest ablation.
4. **Fault realism from the literature.** Compression is injected from the published PISA model [Facchinetti 2016] (median depth 24 mg/dL, median duration 45 min), as used by [Idi 2024], instead of hand-made shapes.

Confidence: medium. The patent scan read summaries, not claims, and the full text of [Lobo 2026] was not available. See `CITATIONS.md`.

**Patent note.** Publishing a benchmark and comparing methods carries little patent risk. Risk grows only if the upload tool becomes a product that suppresses or gates real alarms. Hence: the tool stays retrospective, uses the label "possible compression artifact", ships under an open licence with a no-medical-use disclaimer, and the university tech-transfer office is consulted before any commercial or clinical use. This is not a legal opinion.

## 5. Scope

**In scope:** simulated benchmark; real-data checks on public datasets; CGM-only and context-aware baselines; an in-browser upload dashboard.

**Out of scope for now:** prospective data collection, any change to real device alarms, clinical claims, and the literature write-up (to be done separately after fact-checking).

## 6. Known limitations to state up front

- simglucose implements the 2008 UVA/Padova model with 30 virtual patients and one shared CGM noise model [simglucose; Kovatchev 2009; Breton 2008].
- No public dataset has PISA labels. The one labelled real set (36 adults, two G6 sensors) is held by Padova [Idi 2024].
- Insulin and carb context exists only for pump/AID users or people who log; many standalone G7 users have none.
- There is no G7-specific PISA data in the literature found so far.
- The Dexcom Urgent Low Soon prediction model is not public; the trend alarm here is a stand-in (predict 55 mg/dL within 20 min) [Garg 2022].
