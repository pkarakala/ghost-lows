"""Write results/README.md from the committed tables in results/tables/ (BENCHMARK.md §7).

Every number in the README comes from these files; nothing is typed by hand. Run by
experiments/run_all.py, or alone after a run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
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


def section_age_groups() -> list[str]:
    """Results by age group as well as pooled (D14)."""
    s = table(TABLES / f"{MAIN}__summary_by_age_group.csv")
    h1 = table(TABLES / f"{MAIN}__contrast_h1_by_age_group.csv")
    if s is None:
        return []
    lines = ["### By age group (D14)", ""]
    if h1 is not None and len(h1):
        lines += [
            "H1 slope difference (trend − threshold) by age group:",
            "",
            "| Mix | Adolescents | Adults | Children |",
            "|---|---|---|---|",
        ]
        for mix, g in h1.groupby("mix"):
            g = g.set_index("age_group")
            cells = [
                fmt_ci(g.loc[a, "median_slope_diff"], g.loc[a, "lo"], g.loc[a, "hi"])
                if a in g.index
                else "–"
                for a in ("adolescent", "adult", "child")
            ]
            lines.append(f"| {mix} | " + " | ".join(cells) + " |")
        lines.append("")
    top = s["level"].max()
    d = s[(s["mix"] == "default") & (s["level"] == top)]
    alarms = [
        a
        for a in (
            "threshold",
            "trend",
            "gbm_time",
            "gbm_time_ctx",
            "trend_combined_time",
            "trend_combined_time_ctx",
        )
        if a in set(d["alarm_name"])
    ]
    lines += [
        f"False alarms per day and level 2 lows caught by age group (default mix, PISA on {top:.0%} of nights):",
        "",
        "| Alarm | Adolescents | Adults | Children |",
        "|---|---|---|---|",
    ]
    for alarm in alarms:
        g = d[d["alarm_name"] == alarm].set_index("age_group")
        cells = [
            f"{ci(g.loc[a], 'false_per_day')}; {ci(g.loc[a], 'sens_l2', pct=True)}"
            if a in g.index
            else "–"
            for a in ("adolescent", "adult", "child")
        ]
        lines.append(f"| `{alarm}` | " + " | ".join(cells) + " |")
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


def h2_level(h: pd.DataFrame, level: float | None) -> float:
    """The H2 display level: the training level if it was evaluated, else the highest level."""
    return level if level is not None and (h["level"] == level).any() else h["level"].max()


def fmt_ci(est, lo, hi, digits=2) -> str:
    return f"{est:.{digits}f} ({lo:.{digits}f}–{hi:.{digits}f})"


def section_summary(meta: dict) -> list[str]:
    """One bullet per hypothesis and RQ3, each read mechanically from the committed tables with
    the pre-registered rules (RESEARCH.md §3; amendments A3, A4)."""
    lines = [
        "## Summary",
        "",
        "Read mechanically from the tables below; nothing in this section is typed by hand.",
        "",
    ]
    h1 = table(TABLES / f"{MAIN}__contrast_h1.csv")
    if h1 is not None and len(h1):
        parts = [
            f"{r['mix']}: {fmt_ci(r['median_slope_diff'], r['lo'], r['hi'])}, {'supported' if r['supported'] else 'not supported'}"
            for _, r in h1.iterrows()
        ]
        lines.append(
            "- **H1** (trend alarms degrade faster than threshold alarms as compression nights increase; median per-patient slope difference, false alarms/day per unit PISA fraction): "
            + "; ".join(parts)
            + "."
        )
    h2 = table(TABLES / f"{MAIN}__contrasts_h2.csv")
    if h2 is not None and len(h2):
        h = h2.dropna(subset=["rate_ratio"])
        lv = h2_level(h, meta.get("train_level"))
        d = h[(h["mix"] == "default") & (h["level"] == lv)]
        by = d.groupby("reading")["detector"].apply(
            lambda x: ", ".join(f"`{v}`" for v in sorted(x))
        )
        lines.append(
            f"- **H2** (default mix, PISA on {lv:.0%} of nights; compression false alarms with IOB/COB ÷ without, SESOI 0.75): "
            + "; ".join(f"{k}: {v}" for k, v in by.items())
            + "."
        )
        sec = h[h["level"] == lv].pivot_table(index="detector", columns="mix", values="rate_ratio")
        if {"high", "standard"} <= set(sec.columns):
            closer = (np.log(sec["high"]).abs() < np.log(sec["standard"]).abs()).sum()
            lines.append(
                f"- **H2, secondary** (the ratio is closer to 1 on the high-perturbation mix than on the standard mix): {int(closer)} of {sec[['high', 'standard']].dropna().shape[0]} detectors."
            )
    az = table(TABLES / "real__azt1d_contrasts_h2.csv")
    az_meta = read_json(TABLES / "real__azt1d_meta.json")
    leak = meta.get("leak_auc") or {}
    if az is not None and h2 is not None and leak:
        matched = min(leak, key=lambda m: abs(leak[m]["iob"] - az_meta.get("leak_auc_iob", np.nan)))
        lv = az["level"].max()
        a = az[az["level"] == lv].set_index("detector")["rate_ratio"]
        b = h2[(h2["mix"] == matched) & (h2["level"] == lv)].set_index("detector")["rate_ratio"]
        both = pd.concat([a.rename("azt1d"), b.rename("sim")], axis=1).dropna()
        if len(both):
            closer = (np.log(both["azt1d"]).abs() < np.log(both["sim"]).abs()).sum()
            lines.append(
                f"- **H3** (the context benefit is closer to 1 on real AZT1D nights than in simulation, matched mix `{matched}`, PISA on {lv:.0%} of nights; descriptive, A4): holds for {int(closer)} of {len(both)} detectors."
            )
    rq3 = table(TABLES / "rq3_kalman__contrasts_rq3.csv")
    if rq3 is not None and len(rq3):
        r = rq3[(rq3["mix"] == "default") & (rq3["level"] == rq3["level"].max())]
        for _, row in r[r["a"] == "kalman_pisa"].iterrows():
            lines.append(
                f"- **RQ3** (exploratory; default mix, PISA on {row['level']:.0%} of nights): `kalman_pisa` vs. {row['b'] if row['contrast'] == 'versus best discriminative' else '`' + row['b'] + '`'}, {row['measure']}: {fmt_ci(row['estimate'], row['lo'], row['hi'])}."
            )
    return lines + [""]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def section_real() -> list[str]:
    lines = ["## Real data", ""]
    s, meta = table(TABLES / "real__summary.csv"), read_json(TABLES / "real__meta.json")
    if s is None:
        return lines + ["Not run yet: `uv run python experiments/real_data.py`.", ""]
    lines += [
        f"### Semi-synthetic RQ1 (co-primary, D16): {meta.get('dataset', 'Weinstock 2016')}",
        "",
        f"{meta.get('patients')} people, {meta.get('days', float('nan')):.0f} days. Reference lows are taken from the un-injected CGM: "
        f"{meta.get('reference_l1_events')} level 1, {meta.get('reference_l2_events')} level 2. {meta.get('labelled', '')}",
        "",
        "| Alarm | PISA nights | False alarms/day | Compression false alarms/day | Level 1 caught | Level 2 caught |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in s.sort_values(["alarm_name", "level"]).iterrows():
        lines.append(
            f"| `{r['alarm_name']}` | {r['level']:.0%} | {ci(r, 'false_per_day')} | {ci(r, 'false_compression_per_day')} | "
            f"{ci(r, 'sens_l1', pct=True)} | {ci(r, 'sens_l2', pct=True)} |"
        )
    fv = table(TABLES / "real__face_validity.csv")
    lines += ["", "### Face validity of simulated lows (D16)", ""]
    if fv is None:
        lines.append("Not run yet (needs the full simulated cohort).")
    else:
        lines += [
            "Medians per source: CGM fall rate in the 30 min before a nocturnal low, its nadir and duration, the share of the night at 70–95 mg/dL, and time below 70.",
            "",
            "| Source | Fall rate (mg/dL/min) | Nadir (mg/dL) | Duration (min) | Night at 70–95 | Time below 70 | Nocturnal lows |",
            "|---|---|---|---|---|---|---|",
        ]
        for _, r in fv.iterrows():
            lines.append(
                f"| {r['source']} | {r['fall_rate']:.2f} | {r['nadir']:.0f} | {r['duration_min']:.0f} | "
                f"{r['night_70_95']:.0%} | {r['tbr70']:.1%} | {r['nocturnal_lows']:.0f} |"
            )
        if (REPO / "results" / "figures" / "real__face_validity.png").exists():
            lines += ["", "![face validity](figures/real__face_validity.png)"]
    return lines + [""] + section_h3()


def section_h3() -> list[str]:
    lines = ["### H3: does the context benefit shrink on real data? (AZT1D)", ""]
    az = table(TABLES / "real__azt1d_contrasts_h2.csv")
    az_meta = read_json(TABLES / "real__azt1d_meta.json")
    sim = table(TABLES / f"{MAIN}__contrasts_h2.csv")
    sim_meta = read_json(TABLES / f"{MAIN}__meta.json")
    if az is None:
        return lines + [
            "Not run yet: `uv run python experiments/real_data.py --dataset azt1d`.",
            "",
        ]
    leak = sim_meta.get("leak_auc") or {}
    az_leak = az_meta.get("leak_auc_iob", float("nan"))
    matched = min(leak, key=lambda m: abs(leak[m]["iob"] - az_leak)) if leak else None
    level = az["level"].max()
    lines += [
        f"{az_meta.get('patients')} people, {az_meta.get('days', float('nan')):.0f} days. {az_meta.get('context', '')}. "
        f"Leak AUC (IOB) on AZT1D {az_leak:.2f}"
        + (
            "; simulated mixes: "
            + ", ".join(f"{m} {v['iob']:.2f}" for m, v in leak.items())
            + f". Matched mix (closest leak AUC): **{matched}**."
            if matched
            else "."
        ),
        "",
        f"Compression false alarms, [CGM + time + IOB/COB] ÷ [CGM + time], at PISA on {level:.0%} of nights. Reading (amendment A4): H3 holds for a detector when the AZT1D ratio is closer to 1, on the log scale, than the simulated ratio on the matched mix. The reading is descriptive: the two ratios come from different samples, and real artifacts in the AZT1D reference are unlabelled. {az_meta.get('labelled', '')}",
        "",
        "| Detector | AZT1D rate ratio (95% CI) | Simulated, matched mix (95% CI) | Closer to 1 on AZT1D |",
        "|---|---|---|---|",
    ]
    a = az[az["level"] == level].set_index("detector")
    b = (
        sim[(sim["mix"] == matched) & (sim["level"] == level)].set_index("detector")
        if sim is not None and matched
        else None
    )
    for det, r in a.iterrows():
        cell_a = (
            f"{r['rate_ratio']:.2f} ({r['lo']:.2f}–{r['hi']:.2f})"
            if pd.notna(r["rate_ratio"])
            else "–"
        )
        cell_b, verdict = "–", "–"
        if (
            b is not None
            and det in b.index
            and pd.notna(b.loc[det, "rate_ratio"])
            and pd.notna(r["rate_ratio"])
        ):
            rb = b.loc[det]
            cell_b = f"{rb['rate_ratio']:.2f} ({rb['lo']:.2f}–{rb['hi']:.2f})"
            closer = abs(np.log(r["rate_ratio"])) < abs(np.log(rb["rate_ratio"]))
            verdict = "yes" if closer else "no"
        lines.append(f"| `{det}` | {cell_a} | {cell_b} | {verdict} |")
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
            *section_summary(meta),
            "## Headline results",
            "",
            *section_rq1(summary),
            "",
            *section_h1(table(TABLES / f"{MAIN}__contrast_h1.csv")),
            *section_h2(table(TABLES / f"{MAIN}__contrasts_h2.csv"), meta.get("train_level")),
            *section_age_groups(),
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
    lines += section_real()
    lines += [
        "## Reading of the hypotheses",
        "",
        "H1 and H2 are read mechanically from the tables above with the rules in docs/RESEARCH.md §3; H3 with the rule of amendment A4 in the real-data section.",
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
