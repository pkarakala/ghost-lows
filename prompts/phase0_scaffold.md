# Phase 0: scaffold

```
Read CLAUDE.md and docs/ROADMAP.md (phase 0) and docs/DATA.md §2.
Create: pyproject.toml (Python 3.11, uv, package `ghostlows` under src/, deps: numpy, pandas, scipy, scikit-learn, pyarrow, pyyaml, matplotlib, plotly; optional extra `sim` = simglucose, "setuptools<70"; dev = pytest, ruff), the empty subpackages io, metrics, sim, faults, alarms, bench, retro, tests/test_smoke.py, .github/workflows/ci.yml (uv, Python 3.11, ruff + pytest), Makefile (install, test, lint, data, smoke, all), and scripts/download_data.py exactly as DATA.md §2 describes (GlucoBench raw_data.zip from GitHub by default, DiaData opt-in with --diadata, manual instructions for AZT1D, CGMacros, OhioT1DM, MANIFEST.json with SHA-256).
Done when: `uv run pytest` passes, ruff passes, the download script fetches GlucoBench and writes the manifest. Commit and push.
```
