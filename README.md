# Ghost Lows

**An open benchmark for real-time CGM low-glucose alarms under sensor faults, and a measurement of what insulin and carbohydrate context adds.**

> **Not a medical device. Not for treatment decisions.** This project is research software. Nothing it produces should be used to decide whether to treat, ignore or silence a low glucose reading. If a reading looks wrong, confirm with a fingerstick and follow your care team's advice.

## The problem

Continuous glucose monitors (CGMs) such as the Dexcom G7 and FreeStyle Libre sometimes report low glucose that is not real. The best documented cause is pressure on the sensor during sleep, known in the literature as a **pressure-induced sensor attenuation (PISA)** or **compression low** [Mensh 2013; Facchinetti 2016]. In this project, a **ghost low** means a CGM low reading or low alarm caused by a sensor artifact rather than by low blood glucose. Compression is the main artifact studied, alongside signal dropout, drift and stale readings.

Compression lows are typically shallow (median depth 24 mg/dL) and short (median 45 min) [Facchinetti 2016], occur mostly overnight, and are long enough to meet the consensus definition of a CGM hypoglycaemic event [Battelino 2023]. They cause false overnight alarms, which contribute to alarm fatigue [Shivers 2013], and inside automated insulin delivery they can trigger needless insulin suspensions followed by high morning glucose [Baysal 2014].

## What is already known

Detecting compression lows is **not** new:

- Real-time, rule-based PISA detection on real data [Baysal 2014].
- Machine-learning detectors, including gradient boosting [Navarathna 2023] and a prospective detector of PISA onset scored by PR-AUC [Lobo 2026].
- Retrospective detectors that use CGM values only: matched filter [Idi 2023], isolation forest on simulated data and on 36 adults wearing two sensors [Idi 2024], and a Bayesian smoothness approach [Manzoni 2025].
- Model-based sensor-fault detection using insulin and meal inputs [Facchinetti 2013; Turksoy 2017], and fault-tolerant prediction with insulin and carbs [Sanchez 2025].
- Patents on PISA-aware alarm handling [US 2024/0139415; US 2024/0138770] and on gating low alarms with insulin and carb context [US 11,406,331; US 9,119,528; US 10,231,659].
- A commercial multi-sensor approach with no published metrics [Trinity Biotech 2026].

## What this project does that is new

1. **An open, alarm-level benchmark.** No published suite scores each real-time low alarm on *lows caught*, *false alarms per day* and *minutes of warning* together, while the severity of a *mixed* fault suite (compression, dropout, drift, stale readings) is varied. Existing fault-injection testbeds target controller faults or generic faults with no PISA model [Zhou 2021; APS_TestBed 2022], and existing CGM benchmarks are forecasting benchmarks with no sensor faults [GlucoBench 2024; GlucoFM-Bench 2026; MetaboNet-Bench 2026]. Detector metrics such as sensitivity with false positives per day already exist [Idi 2024; Manzoni 2025]; the novelty is scoring *alarms in real time* across *several fault types at once*.
2. **A controlled ablation of physiological context.** The same published detectors (threshold, trend, Baysal rules, matched filter, isolation forest, gradient boosting) are run with and without insulin-on-board and carbs-on-board, at a fixed safety level on level 2 lows (<54 mg/dL). The detectors exist; a controlled measurement of what insulin and carb context adds *at alarm time* does not.
3. **A simulation that does not leak the answer.** In a standard simulator every low is caused by the insulin model, so insulin features look unrealistically strong. The scenarios here add unannounced exercise, insulin-sensitivity changes and missed or miscounted meals so that some lows are not predictable from insulin, and compression is injected from the published PISA model [Facchinetti 2016] instead of hand-made shapes.
4. **An open, privacy-preserving upload tool** that runs entirely in the browser, computes the consensus CGM metrics [Battelino 2019] and retrospectively flags *possible compression artifacts* using published CGM-only methods. The tool implements published work; the research contribution is the benchmark.

A hidden-state filter with an explicit "compressed" state is included as a stretch entry. It is only a modest opening given prior model-based work [Facchinetti 2013; Turksoy 2017; Mahmoudi 2017].

Novelty was assessed on 2026-10-18 from abstracts, full texts where available, and a patent scan; see [`docs/CITATIONS.md`](docs/CITATIONS.md) for what was and was not read.

## Research questions

See [`docs/RESEARCH.md`](docs/RESEARCH.md). In short:

- **RQ1.** How much do compression and other sensor faults degrade existing low alarms on lows caught, false alarms per day and warning time?
- **RQ2.** At a fixed sensitivity on level 2 lows, how many compression false alarms does adding insulin and carb context remove, and how much of the effect is on compression versus other noise?
- **RQ3.** Does a filter with an explicit "compressed" state beat the best discriminative model, and does either hold up on real data?

## Repository layout (planned)

```
src/ghostlows/
  io/        Dexcom Clarity, LibreView and dataset loaders -> one common table
  metrics/   consensus CGM metrics (TIR, TBR, TAR, CV, GMI, AGP)
  sim/       simglucose wrapper, 5-min sensor, realistic scenarios
  faults/    PISA (Facchinetti model), dropout, drift, stale readings, mixed suite
  alarms/    threshold, trend, Baysal, matched filter, isolation forest, boosting, (+ context), Kalman/HMM
  bench/     event detection, alarm scoring, cross-validation, confidence intervals
  retro/     retrospective "possible compression artifact" flagging for uploads
experiments/ configs and scripts that produce every table and figure
app/         in-browser dashboard (stlite / Pyodide), no server
tests/
docs/        research plan, roadmap, simulation, benchmark, data, privacy, citations
prompts/     step-by-step prompts for building this with Claude Code
```

## Documents

| File | What it holds |
|---|---|
| [`docs/RESEARCH.md`](docs/RESEARCH.md) | Definitions, research questions, hypotheses, novelty summary |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Build phases with acceptance criteria |
| [`docs/SIMULATION.md`](docs/SIMULATION.md) | Simulator, scenarios and fault-suite specification |
| [`docs/BENCHMARK.md`](docs/BENCHMARK.md) | Alarms, metrics, operating point and statistics |
| [`docs/DATA.md`](docs/DATA.md) | Datasets, licences, download steps, export formats |
| [`docs/PRIVACY_AND_SAFETY.md`](docs/PRIVACY_AND_SAFETY.md) | Rules for the upload tool |
| [`docs/CITATIONS.md`](docs/CITATIONS.md) and [`docs/references.bib`](docs/references.bib) | Every source, with links and verification status |
| [`docs/CLINICAL_REVIEW.md`](docs/CLINICAL_REVIEW.md) | Claims the clinical co-lead must verify |
| [`prompts/`](prompts/) | Prompts to paste into Claude Code, one per phase |

## Team

- Engineering: Pranav Karakala Reddy.
- Clinical and biology fact-checking: clinical co-lead (see `docs/CLINICAL_REVIEW.md`).

## Licence

Code: MIT (see `LICENSE`). Datasets keep their own licences (see `docs/DATA.md`); none are redistributed in this repository.
