# Contributions

Research question: Pranav Karakala Reddy. Study design: the design decisions and amendments in `docs/DECISIONS.md` were drafted and recorded by AI agents (Claude, Anthropic) acting in a reviewer role under authority the author delegated, and were accepted by the author. Software, documentation and results text were written with AI coding agents under the author's direction: every commit carries a `Co-Authored-By: Claude` trailer, and three early commits are authored by Claude. The author reviewed the code and results, but not every line. Clinical review: Cohen Ferrari, in progress; no item in `docs/CLINICAL_REVIEW.md` has been signed off yet.

## Records of how the software was built

- [`docs/development/prompts/`](docs/development/prompts/): the phase-by-phase instructions the software was implemented from.
- [`docs/development/SPEC_REVIEW.md`](docs/development/SPEC_REVIEW.md): the review of the specifications made before any code was written.
- [`docs/DECISIONS.md`](docs/DECISIONS.md): the design decisions and every amendment after the pre-registration tag `protocol-v1`, with dates and reasons.
- [`CLAUDE.md`](CLAUDE.md): the project rules given to the coding agents (citations, assumptions, causality, leakage, safety wording, privacy). It stays at the repository root because the agents read it from there.
- Git history: every commit carries a `Co-Authored-By: Claude` trailer; `d75fe42`, `73f24f9` and `c4f71c7` are authored by Claude.
