# Phase 1: data I/O and metrics

```
Read CLAUDE.md, docs/DATA.md §3–4 and docs/ROADMAP.md (phase 1).
Implement ghostlows.io: load_glucobench(name), load_clarity(path_or_buffer), load_libreview(path_or_buffer), all returning the common schema in DATA.md §3. Handle Clarity metadata rows, keep EGV rows only, map "Low"/"High" to device limits with glucose_flag. Handle LibreView's two header rows and Record Type. Keep ghostlows.io and ghostlows.metrics pure Python + numpy/pandas (they must run in Pyodide).
Implement ghostlows.metrics: mean, SD, CV, GMI, TIR 70–180, TBR <70 and <54, TAR >180 and >250, wear %, and AGP percentile curves (5/25/50/75/95 by time of day). Cite Battelino 2019 with `# SOURCE:`. The GMI formula and targets are CLINICAL-REVIEW CR7.
Create synthetic fixtures by hand in tests/fixtures/ (a Clarity CSV and a LibreView CSV, a few days each, including Low/High values, gaps and alert rows). Never use real patient data.
Done when: fixtures parse, metrics equal hand-computed values on a tiny fixture, GlucoBench files load with row and patient counts logged. Commit and push.
```
