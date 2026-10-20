# Development records

How the software was built, for readers checking its provenance. These files describe the process, not the benchmark; the specifications are in [`docs/`](../). Authorship is stated in the README, [How this was made](../../README.md#how-this-was-made).

- [`prompts/`](prompts/): the instructions the software was implemented from with AI coding agents, one per roadmap phase ([`../ROADMAP.md`](../ROADMAP.md)), with [`prompts/00_START_HERE.md`](prompts/00_START_HERE.md) as the entry point.
- [`SPEC_REVIEW.md`](SPEC_REVIEW.md): the critical review of the specifications made before any code was written; the decisions taken on it are in [`../DECISIONS.md`](../DECISIONS.md).
- [`REVIEW.md`](REVIEW.md): a referee-style review of the finished repository (2026-10-18), with what was fixed after it and what is left.
- [`../DECISIONS.md`](../DECISIONS.md): the design decisions and every amendment after the pre-registration tag `protocol-v1`, with dates and reasons.
- [`AGENTS.md`](../../AGENTS.md): the project rules given to the coding agents (citations, assumptions, causality, leakage, safety wording, privacy). Until 2026-10-19 they were in `CLAUDE.md`, together with the reviewer persona the agents were given; that version is in git history. `CLAUDE.md` now imports `AGENTS.md`.
- Git history: every commit carries a `Co-Authored-By: Claude` trailer; `d75fe42`, `73f24f9` and `c4f71c7` are authored by Claude.
