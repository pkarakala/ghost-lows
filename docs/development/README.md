# Development records

How the software was built, for readers checking its provenance. These files describe the process, not the benchmark; the specifications are in [`docs/reference/`](../reference/). Plain-text paths in these records predate the move of the specifications to `docs/reference/` (after v0.2.0); their links point to the new place. Authorship is stated in the README, [How this was made](../../README.md#how-this-was-made).

- [`prompts/`](prompts/): the instructions the software was implemented from with AI coding agents, one per roadmap phase, with [`prompts/00_START_HERE.md`](prompts/00_START_HERE.md) as the entry point.
- [`ROADMAP.md`](ROADMAP.md): the phases the software was built in, and the open items (blocked or deferred work).
- [`SPEC_REVIEW.md`](SPEC_REVIEW.md): the critical review of the specifications made before any code was written; the decisions taken on it are in [`../reference/DECISIONS.md`](../reference/DECISIONS.md).
- [`REVIEW.md`](REVIEW.md): a referee-style review of the finished repository (2026-10-18), with what was fixed after it and what is left.
- [`decisions_pending.md`](decisions_pending.md): choices made while the project lead was away during the fixes after that review, each reversible.
- [`../reference/DECISIONS.md`](../reference/DECISIONS.md): the design decisions and every amendment after the pre-registration tag `protocol-v1`, with dates and reasons.
- [`AGENTS.md`](../../AGENTS.md): the project rules given to the coding agents (citations, assumptions, causality, leakage, safety wording, privacy); their full text is in [`ENGINEERING.md`](../reference/ENGINEERING.md) since the docs restructure after v0.2.0. Until 2026-10-19 they were in `CLAUDE.md`, together with the reviewer persona the agents were given; that version is in git history. `CLAUDE.md` now imports `AGENTS.md`.
- Git history: every commit up to `v0.2.0` carries a `Co-Authored-By: Claude` trailer; `d75fe42`, `73f24f9` and `c4f71c7` are authored by Claude. Later commits carry no trailer: `.claude/settings.json` turns it off. History is not rewritten, because the `protocol-v1` and release tags depend on it.

## How this was made

Research question, study direction and interpretation: Pranav Karakala Reddy. Software and documentation were developed with AI coding agents (Claude, Anthropic) under the author's direction. Design decisions and amendments proposed by the agents are logged in docs/reference/DECISIONS.md and were reviewed and accepted by the author. The author reviewed all code and results. Literature fact-check: Cohen Ferrari (in progress).
