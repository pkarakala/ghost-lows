# Ghost Lows

## Problem
Continuous glucose monitors (CGMs, under-skin glucose sensors) sometimes show false lows. Sleeping on the sensor causes many, triggering needless alarms.

## What it does
This open benchmark scores low-glucose alarms on lows caught, false alarms and warning time under worsening simulated sensor faults. It also tests whether insulin and carb data help.

## Findings
Brackets: 95% confidence intervals (CI, plausible range).
- Nightly compression caused 0.32 (0.30–0.35) of the trend alarm's 1.53 (1.33–1.73) daily false alarms.
- From no compressed nights to all, trend alarms gained 0.09 (0.07–0.10) more daily false alarms than threshold alarms.
- Insulin and carb data missed the pre-set 25% cut in compression false alarms: best ratio 0.94 (0.90–0.96).
- Trend alarms caught 90% (86–93%) of severe lows (<54 mg/dL, 15 min).

## Limitations
- The simulator lacks counter-regulation (the body's defence against lows).
- 30 virtual patients and smooth sensor noise, not people.
- No public dataset labels real compression lows.

## Try it
[Upload report](https://pkarakala.github.io/ghost-lows/): files stay in your browser. Reproduce (hours):

```
uv sync
make data data-azt1d
make results
```

## Next
- Engineers: [CONTRIBUTING.md](CONTRIBUTING.md)
- Researchers: [results](results/README.md), [reference](docs/reference/)
- Clinicians: [summary](docs/SUMMARY.md), [claims to check](docs/CLINICAL_REVIEW.md)
- AI-assisted readers: [AGENTS.md](AGENTS.md)

## How this was made
Research question, study direction and interpretation: Pranav Karakala Reddy. Software and documentation were developed with AI coding agents (Claude, Anthropic) under the author's direction. Design decisions and amendments proposed by the agents are logged in docs/reference/DECISIONS.md and were reviewed and accepted by the author. The author reviewed all code and results. Clinical review: Cohen Ferrari (in progress; no item in docs/CLINICAL_REVIEW.md signed off yet).

## License and disclaimer
MIT ([LICENSE](LICENSE)). **Not a medical device. Not for treatment decisions.** If a reading looks wrong, confirm with a fingerstick and follow your care team's advice.
