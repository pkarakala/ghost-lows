# Ghost Lows

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23573707.svg)](https://doi.org/10.5281/zenodo.23573707)

An open benchmark for real-time CGM low-glucose alarms under sensor faults. Continuous glucose monitors (CGMs, under-skin sensors) can show false lows, often when slept on (a compression low). Ghost Lows scores alarms on lows caught, false alarms and warning time as simulated faults worsen, with and without insulin and carb data.

**Finding.** With a compression low every night in 30 virtual patients, the trend alarm caught 90% (86–93%) of severe lows, and compression caused 0.32 (0.30–0.35) of its 1.53 (1.33–1.73) false alarms per day (95% CIs). Insulin and carb data never cut compression false alarms by the pre-set 25%, and published compression detectors cut them only by missing real severe lows (post hoc).

**Limits.** The simulator lacks counter-regulation (the body's defence against lows). No public dataset labels real compression lows. Real-data checks use the same CGM as the reference, so they are near-circular. [All limitations](docs/reference/RESEARCH.md#6-known-limitations-to-state-up-front).

## Run it

- [Upload report](https://pkarakala.github.io/ghost-lows/): files stay in your browser.
- Reproduce every result (hours): `uv sync`, then `make data data-azt1d` and `make results`.
- Library: `pip install git+https://github.com/pkarakala/ghost-lows` ([full example](examples/quickstart.py)):

```python
import ghostlows as gl
trace = gl.load_clarity(gl.sample_export()).dropna(subset=["glucose"])
observed, faults = gl.apply_faults(trace, gl.FaultConfig(pisa_fraction=1.0), seed=1)
print(gl.score_alarm(gl.TrendAlarm(), observed, gl.low_events(trace), faults))
```

## Cite

Cite the concept DOI [10.5281/zenodo.23573707](https://doi.org/10.5281/zenodo.23573707), which resolves to the latest version, and name the benchmark version, `ghostlows-bench v1` (details: [CITATION.cff](CITATION.cff)).

## Read next

Clinicians: [summary](docs/SUMMARY.md), [claims to check](docs/CLINICAL_REVIEW.md). Researchers: [results](results/README.md), [specifications](docs/reference/README.md), [changes](CHANGELOG.md). Contributors: [CONTRIBUTING.md](CONTRIBUTING.md). AI agents: [AGENTS.md](AGENTS.md). Provenance: [build records](docs/development/README.md).

## How this was made

Independent project by UCSB students; not funded or endorsed by UCSB. Co-authors: Pranav Reddy and Cohen Ferrari. Research question, study direction and interpretation: Pranav Reddy. Software and documentation were developed with AI coding agents (Claude, Anthropic) under Pranav Reddy's direction. Design decisions and amendments proposed by the agents are logged in docs/reference/DECISIONS.md and were reviewed and accepted by Pranav Reddy, who reviewed all code and results. Literature fact-check: Cohen Ferrari (in progress). Clinical review: none yet.

## License

MIT ([LICENSE](LICENSE)). **Not a medical device. Not for treatment decisions.** If a reading looks wrong, confirm with a fingerstick and follow your care team's advice.
