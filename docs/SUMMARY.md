# Results on one page

For clinicians. All results are simulated and describe 30 virtual patients, not people with diabetes.

## What we asked

Continuous glucose monitors (CGMs, under-skin glucose sensors) can show false lows. The best-known cause is pressure on the sensor during sleep, a "compression low". We asked three questions:
- How many false low alarms does compression cause?
- Do some alarm designs suffer more than others?
- Do insulin and carb records help an alarm ignore compression?

Each virtual patient was simulated for 14 days, 5 times. We added sensor faults to the simulated sensor, but never to the true glucose. So every false alarm has a known cause. Brackets give 95% confidence intervals (CI, the plausible range).

## Where false alarms come from

![False alarms per day by cause, with a compression low every night](../results/figures/rq1_pisa_sweep__false_alarms_by_cause.png)

*Each bar is one alarm design; blue is compression. Look at `threshold` (fires below 70 mg/dL), `trend` (predicts 55 mg/dL within 20 minutes) and `floor_only` (fires at 55 mg/dL or below). For every design, sensor noise (grey) and other faults (orange) cause more false alarms than compression.*

## The three basic alarms, with a compression low every night

| Alarm | False alarms per day | Of which compression | Severe lows caught | Warning before a severe low, min; missed |
|---|---|---|---|---|
| Floor only (55 mg/dL or below) | 0.20 (0.17–0.23) | 0.09 (0.07–0.11) | 36% (28%–43%) | -9 (-10 to -6); missed 64% |
| Threshold (below 70 mg/dL) | 1.35 (1.15–1.56) | 0.25 (0.21–0.29) | 86% (81%–91%) | 3 (1 to 5); missed 14% |
| Trend (predicts 55 in 20 min) | 1.53 (1.33–1.73) | 0.32 (0.30–0.35) | 90% (86%–93%) | 7 (2 to 11); missed 10% |

A severe low is glucose below 54 mg/dL for 15 minutes. A negative warning means the alarm typically fired after the low began.

## What we found

- **Compression is a minor cause.** Even with a compression low every night, it caused about 21% of the trend alarm's false alarms.
- **Trend alarms suffer a little more.** Going from no compressed nights to all, trend alarms gained 0.09 (0.07–0.10) more false alarms per day than threshold alarms. That is about one extra every 11 days.
- **Insulin and carb records did not help enough.** We set the bar in advance: a 25% cut in compression false alarms. No detector came close; the best ratio was 0.94 (0.90–0.96).
- **Fewer compression alarms cost severe lows.** In a later analysis, decided after the main results, detectors removed compression alarms only by missing severe lows. The first clear cut, by the Baysal 2014 detector, to 0.89 (0.81–0.96) times as many, missed 11 more of 249.
- **A model-based filter was mixed (exploratory).** A Kalman filter (a sensor-tracking model) with a "compressed" state raised fewer false alarms than the best learned alarm, 0.88 (0.80–0.98). It did no better than itself without that state, 1.05 (0.93–1.18).
- **Real data could not settle it.** On real overnight records with injected compression, every confidence interval included no effect.

## What this does and does not mean

These results describe a simulator, not patients. Simulated lows are its weakest part, because the model lacks the body's own defence against lows. Thresholds and the cost of a missed low await clinical review.

**Not a medical device. Not for treatment decisions.** If a reading looks wrong, confirm with a fingerstick and follow your care team's advice.

## Next

- [Claims for a clinician to check](CLINICAL_REVIEW.md)
- [Every limitation](reference/RESEARCH.md#6-known-limitations-to-state-up-front)
- [Every result](../results/README.md)
