# Phase 8: upload dashboard

```
Read CLAUDE.md and docs/PRIVACY_AND_SAFETY.md (all of it).
Implement ghostlows.retro: retrospective "possible compression artifact" flags on an uploaded trace using published CGM-only methods (start with the Baysal 2014 rules and the matched filter, Idi 2023), each flag with its reasons (drop rate, depth, duration, time of night) and the method's citation. Pure Python, Pyodide-safe.
Build app/ with stlite (pin an exact version from the CDN): upload a Clarity or LibreView CSV, then show the consensus metrics, AGP, daily overlays, a nightly view with flags, and TBR with and without possible artifacts side by side. Show the disclaimers and fingerstick sentence from PRIVACY_AND_SAFETY.md on every page. No backend, no analytics, nothing written to storage. Build ghostlows as a pure-Python wheel the page loads. Add a GitHub Actions workflow to deploy app/ to GitHub Pages.
Done when: a Playwright test loads the page, uploads tests/fixtures/clarity_sample.csv and checks the metrics and flags render and that no request carries file contents; the Pages deploy works. Commit and push.
```
