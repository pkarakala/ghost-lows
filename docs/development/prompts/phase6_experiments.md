# Phase 6: experiments for RQ1 and RQ2

```
Read CLAUDE.md, docs/RESEARCH.md §2–3 and docs/BENCHMARK.md.
Create configs and run: (a) RQ1 severity sweep of PISA fraction 0/10/25/50/75/100% with other faults fixed at moderate, and a sweep raising all faults together; (b) RQ2 with/without-context ablation for every detector at the fixed operating point, on standard scenarios and on the full scenario mix. Write experiments/make_figures.py for: severity curves, sensitivity vs false-alarms/day curves, false alarms split by cause (stacked), paired context deltas with CIs, and example traces.
Write results/README.md: headline tables with CIs, figures, an honest reading of H1–H3 (null results are fine), limitations from RESEARCH.md §6 and the assumptions list. Make `make all` reproduce everything.
Done when: everything regenerates from one command on a clean checkout. Commit and push (figures and summary tables only, not raw run data).
```
