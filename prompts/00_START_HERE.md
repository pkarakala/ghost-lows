# Start here: the focused implementation prompt

Paste the block below into Claude Code (CLI) from the root of a clone of this repo. It builds the whole project phase by phase. If a session runs out of context, start a new one and paste the same block; Claude will pick up from the roadmap and git log. To work one phase at a time instead, use the `phaseN_…` prompts in this folder.

---

```
You are building the Ghost Lows project in this repository. Read CLAUDE.md, then docs/RESEARCH.md, docs/ROADMAP.md, docs/SIMULATION.md, docs/BENCHMARK.md, docs/DATA.md, docs/PRIVACY_AND_SAFETY.md and docs/CITATIONS.md. The docs are the specification; follow them.

Goal: an open benchmark that scores real-time CGM low-glucose alarms on lows caught, false alarms per day (split by cause) and minutes of warning, under a mixed sensor-fault suite with compression injected from the published Facchinetti 2016 PISA model, plus a controlled ablation of what insulin and carb context adds at a fixed level 2 (<54 mg/dL) sensitivity. Then an in-browser stlite dashboard where people upload a Dexcom Clarity or LibreView CSV and get consensus CGM metrics plus retrospective "possible compression artifact" flags. The benchmark is the contribution, not a new detector.

Work through docs/ROADMAP.md phases 0 to 8 in order (then 9 and 10 if time allows). For each phase:
1. Check git log and the code to see what is already done; do not redo finished phases.
2. Plan briefly, then implement with tests.
3. Meet the phase's "Done when" criteria exactly. Run `uv run pytest -q` and `uv run ruff check .`.
4. Commit with a clear message, and push.
5. Update docs/ROADMAP.md by ticking the phase (add "✅ done <date>" to its row) and update any spec you had to change.

Non-negotiable rules (from CLAUDE.md): cite every literature value with `# SOURCE: <key>` from docs/CITATIONS.md and never invent a citation or number; mark our own choices `# ASSUMPTION:` and make them configurable; alarms must be causal with a test proving it; leave-patients-out splits and patient-level CIs only; faults never modify truth_glucose; user-facing wording says "possible compression artifact" and never that a low was not real; no user data leaves the browser; no data in git.

Environment: Python 3.11 via uv. simglucose 0.2.11 needs `setuptools<70` because it imports gym → pkg_resources. Its bundled Dexcom sensor samples every 3 min; add a 5-min sensor without editing site-packages.

When something in the spec cannot be done as written (for example a paper's exact equation is not available), implement the closest documented approximation, mark it `# ASSUMPTION:`, record it in docs/SIMULATION_NOTES.md, and carry on. Stop and ask me only for decisions that change the research question.

At the end, write results/README.md with the headline tables and figures for RQ1 and RQ2, the limitations from docs/RESEARCH.md §6, and the auto-collected assumptions.
```
