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

Ghost Lows is a Python benchmark that scores real-time low-glucose alarms on what matters to the person wearing the sensor: how many lows the alarm catches, how many false alarms it raises per day and why, and how many minutes of warning it gives. It scores them while the sensor misbehaves. It runs a virtual cohort through the UVA/Padova 2008 model [@Kovatchev2009] as implemented in simglucose [@simglucose]. On top of the simulated sensor it injects a mixed fault suite: PISAs from a published model [@Facchinetti2016], dropouts, stale readings, drift and spikes. The faults never change the reference glucose, so every false alarm can be attributed to its cause. A semi-synthetic track injects the same artifacts into real CGM records [@Weinstock2016; @GlucoBench2024; @AZT1D2025].

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

# Limitations

The 2008 simulator lacks the 2013 model's hypoglycaemia nonlinearity and glucagon counter-regulation, so simulated lows are the weakest part of the cohort. The semi-synthetic real-data track exists to check them. Without counter-regulation, untreated simulated lows run on until the insulin wears off, so the virtual patients treat lows with a fixed rule taken from public-health advice, and that rule shapes how long and how deep simulated lows are. The simulated sensor error is smooth, so sample-level noise is gentler than a real sensor's. No public dataset labels real compression artifacts: real-data results use injected artifacts, and real artifacts in the reference count as true lows. The PISA model's time constant is an assumption, pending the full text of @Facchinetti2016, and is swept in robustness arms. The realistic PISA frequency comes from the abstract of @Lobo2026. Confidence intervals describe the simulated cohort, not a population. The software is a research tool, not a medical device, and must not be used to decide whether to treat a low.

# AI usage disclosure

Research question: Pranav Karakala Reddy. Study design: the design decisions and amendments in docs/DECISIONS.md were drafted and recorded by AI agents (Claude, Anthropic) acting in a reviewer role under authority the author delegated, and were accepted by the author. Software, documentation and results text were written with AI coding agents under the author's direction: every commit carries a Co-Authored-By: Claude trailer, and three early commits are authored by Claude. The author reviewed the code and results, but not every line. Clinical review: Cohen Ferrari, in progress; no item in docs/CLINICAL_REVIEW.md has been signed off yet.

# Acknowledgements

We thank the teams who made their data and software public: the Jaeb Center for Health Research and the authors of the study of severe hypoglycaemia in older adults [@Weinstock2016]; the GlucoBench curators [@GlucoBench2024]; the AZT1D authors [@AZT1Ddata]; and the author of simglucose [@simglucose]. The code and documentation were written with an AI coding assistant (Claude, Anthropic), as recorded in the commit history; design decisions and amendments are logged in `docs/DECISIONS.md`.

# References
