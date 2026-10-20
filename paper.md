---
title: 'Ghost Lows: an open benchmark for real-time CGM low-glucose alarms under sensor faults'
tags:
  - Python
  - continuous glucose monitoring
  - hypoglycaemia alarms
  - compression artifacts
  - benchmark
  - type 1 diabetes
authors:
  - name: Pranav Karakala Reddy
    affiliation: 1
affiliations:
  - name: Affiliation to be completed by the author before submission
    index: 1
date: 18 October 2026
bibliography: paper.bib
---

# Summary

Continuous glucose monitors (CGMs) warn people with diabetes when their glucose is low or about to be. Some of those warnings are false. The best-documented cause is pressure on the sensor during sleep, a pressure-induced sensor attenuation (PISA) or "compression low" [@Mensh2013; @Facchinetti2016]. False alarms contribute to alarm fatigue [@Shivers2013]. Inside automated insulin delivery they can also suspend insulin without need [@Baysal2014].

Ghost Lows is a Python benchmark that scores real-time low-glucose alarms on what matters to the person wearing the sensor, while the sensor misbehaves: lows caught, false alarms per day and their causes, and minutes of warning. A virtual cohort runs through the UVA/Padova 2008 model [@Kovatchev2009] as implemented in simglucose [@simglucose], and a mixed fault suite is injected on the simulated sensor: PISAs from a published model [@Facchinetti2016], dropouts, stale readings, drift and spikes. The faults never change the reference glucose, so every false alarm can be attributed to its cause. A semi-synthetic track injects the same artifacts into real CGM records [@Weinstock2016; @GlucoBench2024; @AZT1D2025].

The package provides:

- 30 pre-registered reference alarms: threshold and trend rules, causal adaptations of published compression detectors [@Baysal2014; @Idi2023; @Idi2024], learned combiners and gradient boosting, each with and without insulin and carbohydrate context, plus an exploratory multiple-model Kalman filter with an explicit compressed state [after @Facchinetti2013; @Turksoy2017].
- A plug-in interface for scoring a new alarm with the same cross-validation, operating-point rule and statistics.
- A browser-only report that flags a *possible compression artifact* in Dexcom Clarity or LibreView exports without the file leaving the browser.

# Statement of need

Compression detectors have been published, but each was evaluated on its own data with its own metrics, and mostly retrospectively. A detector that can see the whole night is not an alarm, which must decide in real time. No shared testbed measures alarm-level outcomes under a realistic mix of faults, separates compression false alarms from false alarms caused by ordinary sensor noise, or tests what insulin and carbohydrate context adds at a fixed sensitivity. Ghost Lows is that testbed. It is built to be read critically:

- **Truth is separate from the sensor.** Simulated truth is plasma glucose. The CGM is interstitial glucose plus the simulator's autocorrelated sensor error [@Breton2008]. Faults act on the CGM only.
- **Alarms are causal and scored as alarms.** Every alarm is tested to show that future samples cannot change past scores. Alarms keep a refractory period and an ungated urgent-low floor that no gate can suppress. Events, matching windows, cause attribution and alarm rates follow written specifications.
- **The statistics are pre-registered.** Folds are leave-patients-out. The operating point is chosen on training patients only: each alarm's threshold minimises false alarms subject to matching the trend alarm's sensitivity to severe lows. Confidence intervals come from a patient bootstrap. Hypotheses and estimands were frozen in a git tag before the full run. Later changes are logged as dated amendments with their reasons; one change to the exploratory Kalman filter was logged only after the fact (amendment A9). Reporting follows the ADEMP structure for simulation studies [@Morris2019].
- **Built to be reproduced.** Two commands (`make data data-azt1d`, then `make results`) regenerate every table and figure from pinned, checksummed data and seeded configurations. A clean checkout reproduced the headline sweep's tables exactly from the cached cohort; the full pipeline has not been re-run from a clean clone. Literature values in the code carry source comments, values chosen by the authors are marked as assumptions and collected into the results, and claims awaiting clinical review are tagged.

The intended users are researchers who develop or evaluate CGM alarms and artifact detectors, and device and algorithm teams who want a public, falsifiable baseline. The consensus CGM metrics [@Battelino2019] and the browser report also serve people who want to inspect their own exports.

# What the benchmark shows

The results describe 30 virtual patients with one smooth sensor-noise model, not people with diabetes. Confidence intervals are 95% patient-bootstrap intervals. "Severe lows" are below 54 mg/dL for 15 minutes.

*Pre-registered tests (primary).*
- Trend alarms degrade faster than threshold alarms as compressed nights increase (H1), but the effect is small: 0.09 (0.07–0.10) false alarms per day per unit fraction of compressed nights. This is bounded by the PISA model's assumed shape and frequency, which come from abstracts.
- At the frozen operating point (no loss of severe-low sensitivity against the trend alarm), insulin and carbohydrate context did not meaningfully reduce compression false alarms for any detector (H2). Rate ratios were 0.94–1.00 in the default mix, against a smallest effect of interest of 0.75. That operating point awaits clinical review, and thresholds are chosen on in-sample training scores.

*Trade-off curves (secondary, defined after these results were seen; amendments A11 and A13).*
- Along each published gate's curve, compression false alarms fall only once severe lows are given up. The Baysal gate's first clear reduction, to 0.89 (0.81–0.96) times as many, costs 11 more missed severe lows of 249.
- Against the trend alarm with its own threshold lowered (the retuned trend alarm): No published gate gave fewer total false alarms than the retuned trend alarm at any estimable point; the isolation-forest and Baysal gates gave more at most (6 of 8 and 2 of 3). Comparisons are at matched held-out sensitivity (an oracle, not a deployable operating point), cover 18 of 60 planned points, are uncorrected for multiplicity and say nothing about the standard mix. The matched-filter gate could not be compared (its curve reaches only 3 of its 15 planned points, all unstable). CGM-only gradient boosting shifted false alarms between causes: fewer from compression (0.50–0.66 times the retuned trend alarm's, at 7 of its 7 points) with no detectable change in the total (ratios 0.81–1.08, every CI including 1).

*Descriptive.* Even with a compression artifact every night, compression causes 0.32 (0.30–0.35) of the trend alarm's 1.53 (1.33–1.73) false alarms per day, about 21%. Sensor noise and the other faults cause more. This share depends on the assumed compression frequency and on the noise model.

# Limitations

The 2008 simulator lacks the 2013 model's hypoglycaemia nonlinearity and glucagon counter-regulation, so simulated lows are the weakest part of the cohort. The semi-synthetic real-data track checks them. Without counter-regulation, untreated simulated lows run on until the insulin wears off, so the virtual patients treat lows with a fixed rule from public-health advice, which shapes how long and how deep simulated lows are. The simulated sensor error is smooth, so sample-level noise is gentler than a real sensor's. No public dataset labels real compression artifacts: real-data results use injected artifacts, and real artifacts in the reference count as true lows. The PISA model's time constant is an assumption, pending the full text of @Facchinetti2016, and is swept in robustness arms. The realistic PISA frequency comes from the abstract of @Lobo2026. Confidence intervals describe the simulated cohort, not a population. The software is a research tool, not a medical device, and must not be used to decide whether to treat a low.

# AI usage disclosure

Research question: Pranav Karakala Reddy. Study design: the design decisions and amendments in docs/DECISIONS.md were drafted and recorded by AI agents (Claude, Anthropic) acting in a reviewer role under authority the author delegated, and were accepted by the author. Software, documentation and results text were written with AI coding agents under the author's direction: every commit carries a Co-Authored-By: Claude trailer, and three early commits are authored by Claude. The author reviewed the code and results, but not every line. Clinical review: Cohen Ferrari, in progress; no item in docs/CLINICAL_REVIEW.md has been signed off yet.

# Acknowledgements

We thank the teams who made their data and software public: the Jaeb Center for Health Research and the authors of the study of severe hypoglycaemia in older adults [@Weinstock2016]; the GlucoBench curators [@GlucoBench2024]; the AZT1D authors [@AZT1Ddata]; and the author of simglucose [@simglucose]. The code and documentation were written with an AI coding assistant (Claude, Anthropic), as recorded in the commit history; design decisions and amendments are logged in `docs/DECISIONS.md`.

# References
