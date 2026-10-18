"""Write results/README.md from the committed tables in results/tables/ (BENCHMARK.md §7).

Every number in the README comes from these files; nothing is typed by hand. Run by
experiments/run_all.py, or alone after a run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
TABLES = REPO / "results" / "tables"
MAIN = "rq1_pisa_sweep"
CGM_ONLY = [
    "floor_only",
    "threshold",
    "trend",
    "baysal_gate",
    "matched_filter_causal_gate",
    "iforest_causal_gate",
]


def ci(row, name, digits=2, pct=False):
    est, lo, hi = row.get(name), row.get(f"{name}_lo"), row.get(f"{name}_hi")
    if est is None or pd.isna(est):
        return "–"
    f = (lambda v: f"{100 * v:.0f}%") if pct else (lambda v: f"{v:.{digits}f}")
    return f"{f(est)} ({f(lo)}–{f(hi)})"


def table(path: Path):
    return pd.read_csv(path) if path.exists() else None


def section_rq1(summary: pd.DataFrame, mix: str = "default") -> list[str]:
    s = summary[(summary["mix"] == mix) & summary["alarm_name"].isin(CGM_ONLY)]
    levels = sorted(s["level"].unique())
    lines = [
        f"### RQ1: CGM-only alarms as compression nights increase ({mix} mix)",
        "",
        "False alarms per day (95% patient-bootstrap CI), other faults at moderate severity:",
        "",
        "| Alarm | " + " | ".join(f"PISA nights {lv:.0%}" for lv in levels) + " |",
        "|---|" + "---|" * len(levels),
    ]
    for alarm in CGM_ONLY:
        g = s[s["alarm_name"] == alarm].set_index("level")
        if g.empty:
            continue
        lines.append(
            f"| `{alarm}` | "
            + " | ".join(ci(g.loc[lv], "false_per_day") if lv in g.index else "–" for lv in levels)
            + " |"
        )
    top = max(levels)
    lines += [
        "",
        f"At the highest level ({top:.0%} of nights), by cause and with lows caught:",
        "",
        "| Alarm | Compression | Other fault | Near event | Noise | Level 1 caught | Level 2 caught |",
        "|---|---|---|---|---|---|---|",
    ]
    for alarm in CGM_ONLY:
        g = s[(s["alarm_name"] == alarm) & (s["level"] == top)]
        if g.empty:
            continue
        r = g.iloc[0]
        lines.append(
            f"| `{alarm}` | {ci(r, 'false_compression_per_day')} | {ci(r, 'false_other_fault_per_day')} | "
            f"{ci(r, 'false_near_event_per_day')} | {ci(r, 'false_noise_per_day')} | "
            f"{ci(r, 'sens_l1', pct=True)} | {ci(r, 'sens_l2', pct=True)} |"
        )
    return lines


def section_h1(h1: pd.DataFrame | None) -> list[str]:
    lines = ["### H1: do trend alarms degrade faster than threshold alarms?", ""]
    if h1 is None or h1.empty:
        return lines + ["Not computed.", ""]
    lines += [
        "| Mix | Median slope difference (trend − threshold), false alarms/day per unit PISA fraction | Supported (CI above 0) |",
        "|---|---|---|",
    ]
    for _, r in h1.iterrows():
        lines.append(
            f"| {r['mix']} | {r['median_slope_diff']:.2f} ({r['lo']:.2f}–{r['hi']:.2f}) | {'yes' if r['supported'] else 'no'} |"
        )
    return lines + [""]


def section_h2(h2: pd.DataFrame | None, level: float | None) -> list[str]:
    lines = [
        "### H2: what insulin and carb context adds (compression false alarms, [CGM + time + IOB/COB] ÷ [CGM + time])",
        "",
    ]
    if h2 is None or h2.empty:
        return lines + ["Not computed.", ""]
    h = h2.dropna(subset=["rate_ratio"])
    if level is not None and (h["level"] == level).any():
        h = h[h["level"] == level]
    else:
        h = h[h["level"] == h["level"].max()]
    lines += [
        f"At PISA level {h['level'].iloc[0]:.0%} of nights. Reading rule (pre-registered, SESOI 0.75): see RESEARCH.md §3.",
        "",
        "| Detector | Mix | Count with context | Count without | Rate ratio (95% CI) | Reading |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in h.sort_values(["mix", "detector"]).iterrows():
        lines.append(
            f"| `{r['detector']}` | {r['mix']} | {r['count_context']:.0f} | {r['count_base']:.0f} | "
            f"{r['rate_ratio']:.2f} ({r['lo']:.2f}–{r['hi']:.2f}) | {r['reading']} |"
        )
    return lines + [""]


def section_robustness() -> list[str]:
    lines = ["### Robustness arms (default mix)", ""]
    rows = []
    for path in sorted(TABLES.glob("robust_*__summary.csv")):
        name = path.name.split("__")[0]
        s = pd.read_csv(path)
        top = s["level"].max()
        for alarm in ("trend", "baysal_gate", "trend_combined_time_ctx"):
            g = s[(s["alarm_name"] == alarm) & (s["level"] == top)]
            if len(g):
                r = g.iloc[0]
                rows.append(
                    f"| {name} | `{alarm}` | {top:.0%} | {ci(r, 'false_per_day')} | {ci(r, 'false_compression_per_day')} | {ci(r, 'sens_l2', pct=True)} |"
                )
    if not rows:
        return lines + ["Not run yet.", ""]
    return lines + [
        "| Arm | Alarm | PISA nights | False alarms/day | Compression false alarms/day | Level 2 caught |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
    ]


def section_rq3(
    rq3: pd.DataFrame | None, kalman: pd.DataFrame | None, mix: str = "default"
) -> list[str]:
    lines = ["### RQ3 (exploratory): a Kalman filter with an explicit compressed state", ""]
    if rq3 is None or rq3.empty:
        return lines + ["Not run yet.", ""]
    r = rq3[rq3["mix"] == mix]
    levels = sorted(r["level"].unique())
    show = [levels[0], levels[-1]]
    lines += [
        f"{mix.capitalize()} mix, which the filter's development did not use (amendment A3). Ratios below 1 and positive sensitivity differences favour the first alarm; 95% paired patient-bootstrap CIs. The comparator is chosen in each fold on training patients only; the pool and how often each was chosen are in brackets. Exploratory: no decision rule.",
        "",
        "| Contrast | First vs second | Measure | "
        + " | ".join(f"PISA nights {lv:.0%}" for lv in show)
        + " |",
        "|---|---|---|" + "---|" * len(show),
    ]
    for (contrast, a, b, measure), g in r.groupby(["contrast", "a", "b", "measure"], sort=False):
        g = g.set_index("level")
        cells = [
            f"{g.loc[lv, 'estimate']:.2f} ({g.loc[lv, 'lo']:.2f}–{g.loc[lv, 'hi']:.2f})"
            if lv in g.index and pd.notna(g.loc[lv, "estimate"])
            else "–"
            for lv in show
        ]
        lines.append(f"| {contrast} | `{a}` vs {b} | {measure} | " + " | ".join(cells) + " |")
    if kalman is not None:
        k = kalman[(kalman["mix"] == mix) & (kalman["level"] == kalman["level"].max())]
        lines += [
            "",
            f"Kalman alarms at {k['level'].max():.0%} PISA nights: false alarms/day, compression false alarms/day, level 2 caught.",
            "",
            "| Alarm | False alarms/day | Compression false alarms/day | Level 2 caught |",
            "|---|---|---|---|",
        ]
        for _, row in k.sort_values("alarm_name").iterrows():
            lines.append(
                f"| `{row['alarm_name']}` | {ci(row, 'false_per_day')} | {ci(row, 'false_compression_per_day')} | {ci(row, 'sens_l2', pct=True)} |"
            )
    return lines + [""]


def limitations() -> list[str]:
    text = (REPO / "docs" / "RESEARCH.md").read_text()
    m = re.search(r"## 6\. Known limitations to state up front\n(.*?)\n## 7", text, flags=re.S)
    return [
        "## Limitations (from docs/RESEARCH.md §6)",
        "",
        m.group(1).strip() if m else "See docs/RESEARCH.md §6.",
        "",
    ]


def main() -> None:
    summary = table(TABLES / f"{MAIN}__summary.csv")
    meta_path = TABLES / f"{MAIN}__meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    lines = [
        "# Results",
        "",
        "Generated by `experiments/make_results_readme.py` from the tables in `results/tables/`; regenerate everything with `make all`.",
        "Benchmark version: `ghostlows-bench v1`. Simulated cohort: 30 virtual patients (UVA/Padova 2008 via simglucose), 14 days, 5 seeds, three scenario mixes. Confidence intervals are 95% patient-bootstrap intervals over this cohort, not a population (BENCHMARK.md §6).",
        "",
    ]
    if summary is None:
        lines += ["No results yet: run `make all`.", ""]
    else:
        realistic = meta.get("realistic_pisa") or {}
        lines += [
            f"Training fault level (D19): PISA on {meta.get('train_level', float('nan')):.0%} of nights"
            + (
                f" (realistic default from Lobo 2026's rate; reachable: {realistic.get('reachable')}; "
                f"rate with a PISA every night {realistic.get('rate_at_full', float('nan')) * 24:.3f} per day vs. target "
                f"{realistic.get('target_per_hour', float('nan')) * 24:.3f})."
                if realistic
                else "."
            ),
            "",
            "## Headline results",
            "",
            *section_rq1(summary),
            "",
            *section_h1(table(TABLES / f"{MAIN}__contrast_h1.csv")),
            *section_h2(table(TABLES / f"{MAIN}__contrasts_h2.csv"), meta.get("train_level")),
            *section_robustness(),
            *section_rq3(
                table(TABLES / "rq3_kalman__contrasts_rq3.csv"),
                table(TABLES / "rq3_kalman__summary.csv"),
            ),
            "## Figures",
            "",
        ]
        for fig in sorted((REPO / "results" / "figures").glob(f"{MAIN}__*.png")):
            lines.append(f"![{fig.stem}](figures/{fig.name})")
        lines.append("")
    lines += [
        "## Reading of the hypotheses",
        "",
        "H1 and H2 are read mechanically from the tables above with the rules in docs/RESEARCH.md §3. H3 (real data) is reported in the real-data section once the semi-synthetic AZT1D track has run (ROADMAP phase 7).",
        "",
        *limitations(),
        "## Assumptions",
        "",
        "Every `# ASSUMPTION:` in the code, collected at run time: `results/tables/assumptions.md`.",
        "",
    ]
    assumptions = REPO / "results" / MAIN / "assumptions.md"
    if assumptions.exists():
        (TABLES / "assumptions.md").write_text(assumptions.read_text())
    (REPO / "results" / "README.md").write_text("\n".join(lines))
    print("wrote results/README.md")


if __name__ == "__main__":
    main()
