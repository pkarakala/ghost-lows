# Ghost Lows

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23573707.svg)](https://doi.org/10.5281/zenodo.23573707)

## Problem
CGMs (continuous glucose monitors, under-skin sensors) sometimes show false lows, often from being slept on, triggering needless alarms.

## What it does
An open benchmark scoring low-glucose alarms (lows caught, false alarms, warning time) under worsening simulated sensor faults, with and without insulin and carb data.

## Findings
Brackets: 95% confidence intervals.
- Nightly compression caused 0.32 (0.30–0.35) of the trend alarm's 1.53 (1.33–1.73) daily false alarms.
- Nightly compression added 0.09 (0.07–0.10) more daily false alarms to trend than threshold alarms.
- Insulin and carb data (pre-set: 25% fewer compression false alarms): none met the 25% bar; best was gradient boosting on the standard mix, 0.82 (0.74–0.89), inconclusive.
- Published compression detectors cut compression false alarms only by missing real severe lows, and none beat simply making the trend alarm less sensitive (post hoc).
- Trend alarms caught 90% (86–93%) of severe lows (<54 mg/dL, 15 min).

## Limitations
- The simulator lacks counter-regulation (the body's defence against lows).
- 30 virtual patients and smooth sensor noise, not people.
- No public dataset labels real compression lows.
- Real-data checks use the same CGM as the reference, so they are near-circular.

## Try it
[Upload report](https://pkarakala.github.io/ghost-lows/): files stay in your browser. Reproduce (hours):

```
uv sync
make data data-azt1d
make results
```

## Use as a library
`pip install git+https://github.com/pkarakala/ghost-lows`, then ([full example](examples/quickstart.py)):

```python
import ghostlows as gl
trace = gl.load_clarity(gl.sample_export()).dropna(subset=["glucose"])
observed, faults = gl.apply_faults(trace, gl.FaultConfig(pisa_fraction=1.0), seed=1)
print(gl.score_alarm(gl.TrendAlarm(), observed, gl.low_events(trace), faults))
```

## Next
Engineers: [CONTRIBUTING.md](CONTRIBUTING.md). Researchers: [results](results/README.md), [reference](docs/reference/). Clinicians: [summary](docs/SUMMARY.md), [claims to check](docs/CLINICAL_REVIEW.md). AI-assisted readers: [AGENTS.md](AGENTS.md).

## How this was made
Independent project by UCSB students; not funded or endorsed by UCSB. Co-authors: Pranav Reddy and Cohen Ferrari. Research question, study direction and interpretation: Pranav Reddy. Software and documentation were developed with AI coding agents (Claude, Anthropic) under Pranav Reddy's direction. Design decisions and amendments proposed by the agents are logged in docs/reference/DECISIONS.md and were reviewed and accepted by Pranav Reddy, who reviewed all code and results. Literature fact-check: Cohen Ferrari (in progress). Clinical review: none yet.

## License
MIT ([LICENSE](LICENSE)). **Not a medical device. Not for treatment decisions.** If a reading looks wrong, confirm with a fingerstick and follow your care team's advice.
