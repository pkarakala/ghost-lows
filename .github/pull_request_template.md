## What changed

## Why

## Does it change any number in results/?

No / Yes: amendment A__ in `docs/reference/DECISIONS.md`, dated before anything was computed (AGENTS.md rule 11).

## Tests run

- [ ] `uv run pytest -q`
- [ ] `uv run ruff check . && uv run ruff format --check .`
- [ ] Browser tests, if `app/`, `ghostlows.io`, `ghostlows.metrics` or `ghostlows.retro` changed (CONTRIBUTING.md)

## Checklist

- [ ] Every new or changed alarm has a causality test (rule 4).
- [ ] Literature values carry `# SOURCE:`; values we chose carry `# ASSUMPTION:` (rules 1–2).
- [ ] No data committed: nothing from `data/` or `results/*/`, no patient data, even de-identified (rule 9).
- [ ] User-facing text says "possible compression artifact", never "not real", "fake" or "ignore" (rule 7).
