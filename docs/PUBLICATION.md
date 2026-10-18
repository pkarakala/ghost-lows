# Publication, citation and usability plan (D18)

The aim: results that survive peer review, can be cited at a fixed version, and can be reused without installing the simulator.

## Outputs and where they go

| Output | Venue | Why there | Status |
|---|---|---|---|
| Methods paper: the benchmark, RQ1–RQ2, real-data validation | *Journal of Diabetes Science and Technology* (alternative: *IEEE J Biomed Health Inform*) | Where PISA and CGM-alarm methods appear [Baysal 2014; Lobo 2026; Idi 2024] | after Phase 7 |
| Software paper | *Journal of Open Source Software* (JOSS) | Peer-reviewed, citable record of the software; requires docs, tests, CI and a statement of need | Phase 10 |
| Benchmark dataset `ghostlows-bench v1` | Zenodo (DOI), CC BY 4.0 | Frozen simulated cohort (truth, interstitial and CGM traces, faults, events, doses) plus configs and hashes. Synthetic, so it can be shared freely | Phase 6 |
| Pre-registration | git tag `protocol-v1` (optional OSF mirror) | Fixes hypotheses H1–H3, estimands and the operating-point rule before the full run | before the Phase 6 full run |

The methods paper is reported in ADEMP form [Morris 2019] and states the limitations in RESEARCH.md §6 up front.

## Citation

- `CITATION.cff` at the repository root: GitHub shows "Cite this repository" and Zenodo reads it.
- One DOI per release through the Zenodo–GitHub integration (`v0.1.0` at Phase 10).
- Every result names the benchmark version it was computed on (`benchmark_version.txt` in each run).
- Datasets and the simulator are cited as listed in `DATA.md` and `CITATIONS.md`.

## Ease of use (targets)

- `pip install "ghostlows[bench]"` scores alarms without the simulator. A command fetches the frozen cohort with a hash check, so users never need Python 3.11 or gym.
- **Plug-in alarms:** implement the four-method `Alarm` protocol (BENCHMARK.md §1) and score it with one command. A worked example in `examples/` runs in CI, so the docs cannot rot.
- **One command per job:** download data, simulate, run the benchmark, make figures (`make all` reproduces the headline tables).
- **Results page** on GitHub Pages generated from `summary.csv`, next to the browser upload dashboard.
- **Docs:** a quickstart (three commands, under five minutes on the smoke config), how scoring works, how to add an alarm.

## Actions for the project lead (outside the repository)

1. Enable the Zenodo–GitHub integration for this repository before tagging `v0.1.0`.
2. Add ORCID iDs and co-authors (the clinical co-lead) to `CITATION.cff`, and check the author name split.
3. Request the dual-sensor dataset with PISA labels from the Padova group [Idi 2024]. This has a long lead time and is the only labelled real data.
4. Obtain the full texts the fault model depends on: [Facchinetti 2016] (time constant, dropout model, frequency) and [Lobo 2026] (PMC13486385).
5. Optional: mirror the `protocol-v1` pre-registration on OSF.
