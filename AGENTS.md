# AGENTS.md

The project rules for any AI agent, whatever the tool; `CLAUDE.md`, `GEMINI.md` and `.github/copilot-instructions.md` only point here. People start at the [README](README.md). Full rules: [ENGINEERING.md](docs/reference/ENGINEERING.md).

## Map

- `src/ghostlows/`: loaders, metrics, simulator, faults, alarms, scoring, upload-report flags.
- `experiments/`: configs and scripts behind every table and figure.
- `scripts/`: download, app build, reproducibility and docs checks, sample export, packaging.
- `results/`: committed tables and figures; [results/README.md](results/README.md), generated from the tables, is the full record.
- `app/`: the upload report.
- `tests/`: pytest, including rule checks.
- `examples/`: the library [quickstart](examples/quickstart.py) and a [plug-in alarm](examples/custom_alarm.py).
- [data/](data/README.md): downloaded datasets and the cached cohort, gitignored.
- [docs/SUMMARY.md](docs/SUMMARY.md): one-page results for clinicians.
- [docs/CLINICAL_REVIEW.md](docs/CLINICAL_REVIEW.md): clinical claims awaiting sign-off.
- [docs/PRIVACY_AND_SAFETY.md](docs/PRIVACY_AND_SAFETY.md): upload-report rules.
- [docs/CITATIONS.md](docs/CITATIONS.md): every source key.
- [RESEARCH.md](docs/reference/RESEARCH.md): questions, hypotheses, limitations.
- [BENCHMARK.md](docs/reference/BENCHMARK.md): alarms, metrics, operating point, statistics.
- [SIMULATION.md](docs/reference/SIMULATION.md), [SIMULATION_NOTES.md](docs/reference/SIMULATION_NOTES.md): cohort and faults.
- [DATA.md](docs/reference/DATA.md): datasets, schema, export formats.
- [DECISIONS.md](docs/reference/DECISIONS.md): decisions and dated amendments.
- [UPLOAD_REPORT.md](docs/reference/UPLOAD_REPORT.md): the upload report as built.
- [docs/development/](docs/development/README.md): build records, reviews, prompts.
- [paper.md](paper.md), [CHANGELOG.md](CHANGELOG.md), [CITATION.cff](CITATION.cff).

## Reading order

README, SUMMARY, results Summary, RESEARCH §2–3 and §6, BENCHMARK, DECISIONS Amendments. To answer a question, start at its table:

| Question | Table |
|---|---|
| How much is compression? | [RQ1](results/README.md#rq1-cgm-only-alarms-as-compression-nights-increase-default-mix), by cause |
| Do trend alarms suffer more? | [H1](results/README.md#h1-trend-versus-threshold-alarms-as-compression-nights-increase) |
| Does insulin and carb context help? | [H2](results/README.md#h2-what-insulin-and-carb-context-adds-compression-false-alarms-cgm--time--iobcob--cgm--time) |
| Does a Kalman filter do better? | [RQ3](results/README.md#rq3-exploratory-a-kalman-filter-with-an-explicit-compressed-state) |
| Does it hold on real data? | [Real data](results/README.md#real-data) |
| What changed after pre-registration? | [Amendments](docs/reference/DECISIONS.md#amendments) |
| What are the limits? | [RESEARCH §6](docs/reference/RESEARCH.md#6-known-limitations-to-state-up-front) |

## Hard rules

Other files cite these numbers. [Full text](docs/reference/ENGINEERING.md#hard-rules).

1. Literature values carry `# SOURCE: <key>` from [CITATIONS.md](docs/CITATIONS.md); never invent one.
2. Values we chose carry `# ASSUMPTION: <why>` and are configurable.
3. Code depending on a clinical claim carries `# CLINICAL-REVIEW: CRn`.
4. Causality: alarms use only past data; a test proves it.
5. No leakage: leave-patients-out splits; CIs across patients.
6. Faults never touch truth (`truth_glucose`).
7. Safety wording: "possible compression artifact"; never "not real", "fake", "ignore" ([rules](docs/PRIVACY_AND_SAFETY.md)).
8. No user data leaves the browser: no backend, no analytics.
9. No data in git, never patient data.
10. Do not overclaim: effect sizes with CIs, limitations from RESEARCH §6.
11. Amend before computing: a dated amendment in DECISIONS first; `protocol-v1` never moves.

## Writing

- Authors: Pranav Reddy and Cohen Ferrari, co-authors with equal contribution, University of California, Santa Barbara; an independent project, not funded or endorsed by UCSB. `pkarakala` is a username, not a name.
- Cohen Ferrari's work is a literature fact-check; never describe it as clinical review.
- The AI usage disclosure is one text, in `README.md`, `paper.md` and `docs/development/README.md`. Change all three or none. Never claim that text is human-written.
- Commits and pull requests carry no AI attribution: no `Co-Authored-By` trailer, no "generated with" footer, no session link. The disclosure covers AI use.
- Short, plain sentences. Cite literature claims; give effect sizes with CIs (rule 10).

## Commands

```
uv sync
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run python scripts/check_docs_preserved.py --before origin/main
uv run ghostlows benchmark --config experiments/configs/smoke.yaml   # minutes
make figures                                       # publication figures, from results/tables/
uv run python experiments/make_results_readme.py   # results/README.md and results/tables/assumptions.md
make data data-azt1d && make results               # hours
```

## Verify a change

Before every push:
- `uv run pytest -q` and `uv run ruff check . && uv run ruff format --check .` pass.
- After a Markdown edit, `uv run python scripts/check_docs_preserved.py --before origin/main` passes. It fails if a number, citation, CR item, limitation or safety sentence has no copy left.
- After a change to `app/`, `ghostlows.io`, `ghostlows.metrics` or `ghostlows.retro`, the browser tests pass ([CONTRIBUTING.md](CONTRIBUTING.md#tests-and-lint)).
- On the pull request, CI is green.

## Propose a change

- One topic per pull request against `main`, with the [template](.github/pull_request_template.md) filled in.
- A change to a result, metric or operating point starts with a dated amendment (rule 11; [how](CONTRIBUTING.md#change-a-result-a-metric-or-the-operating-point)).
- Never edit generated files by hand: change the script that writes them and rerun it.
- Never rewrite git history or move a tag; `protocol-v1` and the release tags depend on it.
- When a rule and a request conflict, stop and ask the project lead.
