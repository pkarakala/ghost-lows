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

from ghostlows.bench.pipeline import collect_assumptions

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


def warning_cell(w: pd.DataFrame | None, alarm: str, level: float, mix: str) -> str:
    """Median warning before caught level 2 lows (patient-level, with CI) and the miss rate."""
    if w is None:
        return "–"
    r = w[
        (w["alarm_name"] == alarm)
        & (w["level"] == level)
        & (w["mix"] == mix)
        & (w["low_level"] == 2)
    ]
    if r.empty or pd.isna(r["warning_median_min"].iloc[0]):
        return "–"
    r = r.iloc[0]
    return f"{r['warning_median_min']:.0f} ({r['lo']:.0f} to {r['hi']:.0f}); missed {r['miss_rate']:.0%}"


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
    lines += gates_note(s)
    lines += [
        "",
        f"At the highest level ({top:.0%} of nights), by cause and with lows caught:",
        "",
        "| Alarm | Compression | Other fault | Near event | Noise | Level 1 caught | Level 2 caught | Warning before caught level 2 lows, min (95% CI); miss rate |",
        "|---|---|---|---|---|---|---|---|",
    ]
    w = table(TABLES / f"{MAIN}__warning.csv")
    for alarm in CGM_ONLY:
        g = s[(s["alarm_name"] == alarm) & (s["level"] == top)]
        if g.empty:
            continue
        r = g.iloc[0]
        lines.append(
            f"| `{alarm}` | {ci(r, 'false_compression_per_day')} | {ci(r, 'false_other_fault_per_day')} | "
            f"{ci(r, 'false_near_event_per_day')} | {ci(r, 'false_noise_per_day')} | "
            f"{ci(r, 'sens_l1', pct=True)} | {ci(r, 'sens_l2', pct=True)} | {warning_cell(w, alarm, top, mix)} |"
        )
    lines += cause_share(s, top)
    if w is not None:
        lines += [
            "",
            "Warning time is the median over patients of each patient's median run-level warning (onset minus first alarm, caught lows only), with a patient-bootstrap CI, always shown with the miss rate (BENCHMARK.md §4). Amendment A10 (post hoc) moved the bootstrap from patient-runs to patients; the v0.1.0 values are kept next to the new ones in `tables/amendments/A10__warning_old_vs_new.csv`. Simulated warning times are pessimistic, because the model's sensor lag is longer than measured in people (RESEARCH.md §6).",
        ]
    return lines


def cause_share(s: pd.DataFrame, top: float, alarm: str = "trend") -> list[str]:
    """What share of an alarm's false alarms compression causes at the highest PISA level."""
    g = s[(s["alarm_name"] == alarm) & (s["level"] == top)]
    if g.empty:
        return []
    r = g.iloc[0]
    share = r["false_compression_per_day"] / r["false_per_day"]
    return [
        "",
        f"Even with a PISA on {top:.0%} of nights, compression causes {ci(r, 'false_compression_per_day')} "
        f"of `{alarm}`'s {ci(r, 'false_per_day')} false alarms per day ({share:.0%}); noise with no fault or low nearby "
        f"({r['false_noise_per_day']:.2f}) and the other faults ({r['false_other_fault_per_day']:.2f}) cause more. "
        "In this simulator, compression is a minor share of false low alarms.",
    ]


def section_h1(h1: pd.DataFrame | None) -> list[str]:
    lines = ["### H1: trend versus threshold alarms as compression nights increase", ""]
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


def h1_magnitude(h1: pd.DataFrame, mix: str = "default") -> str:
    """The H1 slope difference in plain words: extra false alarms with a PISA on every night."""
    r = h1[h1["mix"] == mix]
    if r.empty:
        return ""
    d = float(r["median_slope_diff"].iloc[0])
    return (
        f"Size of the effect ({mix} mix): going from no compressed nights to a PISA on every night "
        f"adds {d:.2f} more false alarms per day to `trend` than to `threshold`, about one extra "
        f"false alarm every {1 / d:.0f} days. Supported, but small."
    )


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
    return lines + ["", h2_levels_note(h2.dropna(subset=["rate_ratio"])), ""]


def h2_levels_note(h: pd.DataFrame) -> str:
    """Whether the H2 reading depends on the PISA level (the estimand does not fix one)."""
    pos = h[h["level"] > 0]
    n_read = pos.groupby(["detector", "mix"])["reading"].nunique()
    levels = sorted(pos["level"].unique())
    span = f"{levels[0]:.0%}–{levels[-1]:.0%}" if levels else ""
    text = (
        "The pre-registered H2 estimand does not name a PISA level; the table shows the highest, "
        "as the reporting code at the tag `protocol-v1` already did. "
    )
    if len(n_read) and (n_read == 1).all():
        return (
            text
            + f"Every reading is the same at every PISA level from {span} (`contrasts_h2.csv`)."
        )
    changed = ", ".join(f"`{d}` ({m})" for d, m in n_read[n_read > 1].index)
    return text + f"Readings change across PISA levels {span} for: {changed} (`contrasts_h2.csv`)."


def section_all_faults() -> list[str]:
    """RQ1 with every fault type rising together (rq1_all_faults)."""
    s = table(TABLES / "rq1_all_faults__summary.csv")
    if s is None:
        return []
    h1 = table(TABLES / "rq1_all_faults__contrast_h1.csv")
    w = table(TABLES / "rq1_all_faults__warning.csv")
    d = s[s["mix"] == "default"]
    levels = sorted(d["level"].unique())
    top = levels[-1]
    alarms = [
        a
        for a in ("floor_only", "threshold", "trend", "gbm_time", "gbm_time_ctx")
        if a in set(d["alarm_name"])
    ]
    lines = [
        "### RQ1 with every fault rising together (default mix)",
        "",
        "Severity of all faults (PISA fraction, dropout, stale readings, drift, spikes) set to the level (SIMULATION.md §4.3). False alarms per day (95% CI):",
        "",
        "| Alarm | "
        + " | ".join(f"severity {lv:g}" for lv in levels)
        + f" | Level 2 caught at {top:g} | Warning at {top:g}, min; miss rate |",
        "|---|" + "---|" * (len(levels) + 2),
    ]
    for alarm in alarms:
        g = d[d["alarm_name"] == alarm].set_index("level")
        cells = [ci(g.loc[lv], "false_per_day") if lv in g.index else "–" for lv in levels]
        sens = ci(g.loc[top], "sens_l2", pct=True) if top in g.index else "–"
        warn = "–"
        if w is not None:
            r = w[
                (w["alarm_name"] == alarm)
                & (w["level"] == top)
                & (w["mix"] == "default")
                & (w["low_level"] == 2)
            ]
            if len(r) and pd.notna(r["warning_median_min"].iloc[0]):
                warn = f"{r['warning_median_min'].iloc[0]:.0f}; missed {r['miss_rate'].iloc[0]:.0%}"
        lines.append(f"| `{alarm}` | " + " | ".join(cells) + f" | {sens} | {warn} |")
    if h1 is not None and len(h1):
        parts = [
            f"{r['mix']} {fmt_ci(r['median_slope_diff'], r['lo'], r['hi'])}"
            for _, r in h1.iterrows()
        ]
        lines += [
            "",
            "Slope difference (trend − threshold), false alarms/day per unit severity: "
            + "; ".join(parts)
            + ".",
        ]
    return lines + [""]


def same_series(s: pd.DataFrame, a: str, b: str, col: str = "false_per_day") -> bool:
    x = s[s["alarm_name"] == a].sort_values(["mix", "level"])[col].to_numpy()
    y = s[s["alarm_name"] == b].sort_values(["mix", "level"])[col].to_numpy()
    return len(x) > 0 and len(x) == len(y) and bool(np.allclose(x, y, rtol=0, atol=1e-9))


def gates_note(s: pd.DataFrame, curves: bool = True) -> list[str]:
    """Say when the published gates suppressed nothing, or almost nothing, at the operating point."""
    gates = [
        a
        for a in ("baysal_gate", "matched_filter_causal_gate", "iforest_causal_gate")
        if a in set(s["alarm_name"])
    ]
    off = [g for g in gates if same_series(s, g, "trend")]
    trend = s[s["alarm_name"] == "trend"].sort_values(["mix", "level"])["false_per_day"].to_numpy()
    near = []
    for g in gates:
        x = s[s["alarm_name"] == g].sort_values(["mix", "level"])["false_per_day"].to_numpy()
        if g not in off and len(x) and len(x) == len(trend):
            gap = float(np.abs(x - trend).max())
            if gap < 0.05:
                size = "less than 0.01" if gap < 0.01 else f"at most {gap:.2f}"
                near.append(f"`{g}` differs from `trend` by {size} false alarms/day")
    if not off and not near:
        return []
    text = ""
    if off:
        text += "Identical to `trend` here: " + ", ".join(f"`{g}`" for g in off) + ". "
    if near:
        text += "; ".join(near) + ". "
    if curves:
        text += (
            "At the pre-registered operating point (D5, δ = 0), which allows no loss of training "
            "sensitivity against `trend`, the thresholds chosen for these gates suppress no or "
            "almost no trend alarms (`thresholds.csv`). This describes the operating point, not "
            "what the detectors can do. The trade-off curves below (secondary, post hoc; amendment "
            "A11) show what each gate removes as training sensitivity is given up, and at what "
            "cost in lows."
        )
    else:
        text += (
            "As in the simulation (RQ1 above), the gates' thresholds at the pre-registered operating "
            "point suppress no or almost no trend alarms. Trade-off curves were produced for the "
            "simulation only (amendment A11), not for the real-data tracks."
        )
    return ["", text]


# ------------------------------------------------------------------ trade-off curves (A11)

CURVE_GATES = ("baysal_gate", "matched_filter_causal_gate", "iforest_causal_gate")
CURVE_ROWS = ("r=1.00", "r=0.99", "r=0.95", "r=0.90", "r=0.80")


def curve_cell(r, col: str, pct: bool = False) -> str:
    if pct:
        return f"{r[col]:.0%} ({r[col + '_lo']:.0%}–{r[col + '_hi']:.0%})"
    return f"{r[col]:.2f} ({r[col + '_lo']:.2f}–{r[col + '_hi']:.2f})"


def section_curves() -> list[str]:
    """Trade-off curves (amendment A11): secondary and post hoc, read from curves__*.csv."""
    lines = ["### Trade-off curves (secondary, post hoc; amendment A11)", ""]
    s, g = table(TABLES / "curves__summary.csv"), table(TABLES / "curves__gates.csv")
    h, meta = table(TABLES / "curves__h2.csv"), read_json(TABLES / "curves__meta.json")
    if s is None or g is None or h is None:
        return lines + ["Not computed: `uv run python experiments/run_curves.py`.", ""]
    lines += [
        "D5 and BENCHMARK.md §4 call for curves across thresholds; v0.1.0 reported only operating points. "
        "These curves were added after all v0.1.0 results had been seen, so they are secondary: the pre-registered tests above stay the primary results. "
        "Each alarm is fitted as in the benchmark (D19). In each fold, the threshold at retention r is the one D5 picks with the constraint "
        '"training level 2 sensitivity ≥ r × the trend alarm\'s"; r = 1.00 is the pre-registered δ = 0 point. '
        f"Held-out patients are scored with PISA on {meta.get('test_level', 1.0):.0%} of nights, other faults moderate. "
        f"The r = 1.00 points (and the published thresholds of `threshold` and `trend`) reproduce the v0.1.0 thresholds, rates and CIs exactly ({meta.get('checks_reproduced')} of {meta.get('checks')} checks, `curves__check.csv`). "
        "`trend` here sweeps its own prediction threshold; its published rule is the r = 1.00 row in the tables above.",
        "",
        "**Default mix, CGM-only alarms** (held out; false alarms per day split by cause; 95% patient-bootstrap CIs):",
        "",
        "| Alarm | r | Training sensitivity given up (mean over folds) | Level 2 caught | Lows caught / lows | Compression false alarms/day | Other false alarms/day |",
        "|---|---|---|---|---|---|---|",
    ]
    d = s[s["mix"] == "default"]
    for alarm in ("trend", *CURVE_GATES):
        for point in CURVE_ROWS:
            r = d[(d["alarm_name"] == alarm) & (d["point"] == point)]
            if r.empty:
                continue
            r = r.iloc[0]
            lines.append(
                f"| `{alarm}` | {point[2:]} | {r['train_sens_loss']:.3f} | {curve_cell(r, 'sens_l2', pct=True)} | "
                f"{r['caught_l2']:.0f} / {r['events_l2']:.0f} | {curve_cell(r, 'false_compression_per_day')} | {curve_cell(r, 'false_other_per_day')} |"
            )
    lines += [
        "",
        "**Where the gates start removing compression false alarms.** For each gate and mix: the largest r below 1 at which held-out compression false alarms per day are lower than at r = 1 with a paired-bootstrap CI of the ratio below 1, and what that costs in level 2 lows (definition fixed in A11 before computing).",
        "",
        "| Gate | Mix | r | Compression false alarms, ratio to r = 1 | Level 2 sensitivity, difference (percentage points) | Extra missed level 2 lows |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in g.sort_values(["mix", "alarm_name"]).iterrows():
        if pd.isna(r["retention"]):
            lines.append(f"| `{r['alarm_name']}` | {r['mix']} | none | — | — | — |")
            continue
        lines.append(
            f"| `{r['alarm_name']}` | {r['mix']} | {r['retention']:.2f} | "
            f"{fmt_ci(r['compression_ratio'], r['compression_ratio_lo'], r['compression_ratio_hi'], 3)} | "
            f"{pp(r['sens_l2_diff'])} ({pp(r['sens_l2_diff_lo'])} to {pp(r['sens_l2_diff_hi'])}) | "
            f"{r['extra_missed_l2']:.0f} of {r['events_l2']:.0f} |"
        )
    lines += [
        "",
        "**H2 on the curves.** Context over CGM-arm rate ratio of held-out compression false alarms at the marked retentions, read with the pre-registered H2 rule (SESOI 0.75). "
        "Secondary: the pre-registered H2 test is the r = 1.00 column, which reproduces the H2 table above. "
        "The two arms are compared at the same training retention, not at the same held-out sensitivity. The Kalman pair is exploratory (A3).",
        "",
        "| Detector | Mix | r = 1.00 | r = 0.99 | r = 0.95 | Reading at 0.99 / 0.95 |",
        "|---|---|---|---|---|---|",
    ]
    for (det, mix), x in h.groupby(["detector", "mix"]):
        x = x.set_index("retention")
        cells = [
            fmt_ci(x.at[r, "rate_ratio"], x.at[r, "lo"], x.at[r, "hi"]) if r in x.index else "—"
            for r in (1.0, 0.99, 0.95)
        ]
        reads = " / ".join(x.at[r, "reading"] for r in (0.99, 0.95) if r in x.index)
        lines.append(f"| `{det}` | {mix} | {' | '.join(cells)} | {reads} |")
    lines.append("")
    for fig in sorted((REPO / "results" / "figures").glob("curves__*.png")):
        if fig.stem == "curves__a13":
            continue
        lines.append(f"![{fig.stem}](figures/{fig.name})")
    return lines + [""]


def pp(x: float) -> str:
    return f"{100 * x:+.1f}".replace("-", "−")


def h2_curves_note(h: pd.DataFrame) -> str:
    """Whether H2 reads the same at r = 0.95 and 0.99 as at the pre-registered point."""
    pivot = h.pivot_table(
        index=["detector", "mix"], columns="retention", values="reading", aggfunc="first"
    )
    cols = [c for c in (0.95, 0.99, 1.0) if c in pivot]
    same = pivot[cols].nunique(axis=1) == 1
    changed = ", ".join(f"`{d}` ({m})" for d, m in pivot.index[~same])
    meaningful = ", ".join(
        f"`{d}` ({m}, r = {r:.2f})"
        for (d, m), row in pivot.iterrows()
        for r in cols
        if row[r] == "meaningful reduction"
    )
    text = "Readings at r = 0.95 and 0.99 match the pre-registered r = 1.00 reading for " + (
        "every detector and mix." if same.all() else f"every detector and mix except {changed}."
    )
    return text + (
        f" Meaningful reduction at: {meaningful}."
        if meaningful
        else " No detector reaches a meaningful reduction at any marked point."
    )


def section_a13() -> list[str]:
    """Amendment A13 (secondary, post hoc): gates and gbm against a retuned trend alarm at
    matched held-out level 2 sensitivity, read from curves__a13.csv."""
    lines = [
        "### A13: gates versus a retuned trend alarm at matched sensitivity (secondary, post hoc)",
        "",
    ]
    a = table(TABLES / "curves__a13.csv")
    if a is None or a.empty:
        return lines + ["Not computed: `uv run python experiments/run_curves.py`.", ""]
    lines += [
        "Question (fixed in A13 before computing): at the same held-out level 2 sensitivity, does each published gate, or CGM-only gradient boosting, give fewer false alarms per day than the `trend` alarm with its own prediction threshold swept? "
        "Each curve is interpolated linearly at trend's zero-loss held-out sensitivity minus 2 to 10 points. The ratio is comparator ÷ retuned trend, with a paired patient bootstrap (both curves recomputed on the same resampled patients). "
        "A comparator *adds value* only if the CI of the total ratio is below 1. "
        "Flags: *coarse*, the curve points either side of s are more than 3 points of sensitivity apart; *unstable*, more than 5% of bootstrap draws could not be interpolated. "
        f"Exploratory: {len(a)} comparisons, no multiplicity correction.",
        "",
        "| Mix | Comparator | Level 2 sensitivity | False alarms/day: comparator vs retuned trend | Total ratio (95% CI) | Compression ratio (95% CI) | Flags | Reading |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for _, r in a.sort_values(["mix", "comparator", "sens_l2"]).iterrows():
        flags = ", ".join(
            f for f, on in (("coarse", r["coarse"]), ("unstable", r["unstable"])) if on
        )
        lines.append(
            f"| {r['mix']} | `{r['comparator']}` | {r['sens_l2']:.0%} | "
            f"{r['total_per_day']:.2f} vs {r['total_per_day_reference']:.2f} | "
            f"{fmt_ci(r['total_ratio'], r['total_ratio_lo'], r['total_ratio_hi'])} | "
            f"{fmt_ci(r['compression_ratio'], r['compression_ratio_lo'], r['compression_ratio_hi'])} | "
            f"{flags or '—'} | {r['reading']} |"
        )
    lines += ["", "The reading is in the [Summary](#summary).", ""]
    fig = REPO / "results" / "figures" / "curves__a13.png"
    if fig.exists():
        lines.append(f"![curves__a13](figures/{fig.name})")
    return lines + [""]


def span(x: pd.Series) -> str:
    lo, hi = f"{x.min():.2f}", f"{x.max():.2f}"
    return lo if lo == hi else f"{lo}–{hi}"


def a13_verdict(a: pd.DataFrame) -> str:
    """The A13 finding, generated from the table whichever way it falls. Only estimable, stable
    grid points are read."""
    ok = a[np.isfinite(a["total_ratio"]) & ~a["unstable"].astype(bool)]
    gates = ok[ok["comparator"].str.endswith("_gate")]
    adds = gates[gates["reading"] == "adds value"]
    names = {
        "iforest_causal_gate": "isolation-forest",
        "baysal_gate": "Baysal",
        "matched_filter_causal_gate": "matched-filter",
    }
    counts = {
        n: (int((g["reading"] == "worse than retuned trend").sum()), len(g))
        for n, g in gates.groupby("comparator")
        if n in names
    }
    if adds.empty:
        head = "No published gate gave fewer total false alarms than the retuned trend alarm at any estimable point"
    else:
        head = (
            "Published gates gave fewer total false alarms than the retuned trend alarm at "
            + ", ".join(
                f"`{r['comparator']}` ({r['mix']}, {r['sens_l2']:.0%})" for _, r in adds.iterrows()
            )
        )
    order = [n for n in ("iforest_causal_gate", "baysal_gate") if n in counts]
    if order and all(counts[n][0] > counts[n][1] / 2 for n in order):
        head += (
            "; the "
            + " and ".join(names[n] for n in order)
            + " gates gave more at most ("
            + " and ".join(f"{counts[n][0]} of {counts[n][1]}" for n in order)
            + ")"
        )
    no_standard = "standard" in set(a["mix"]) and "standard" not in set(ok["mix"])
    text = (
        head
        + ". Comparisons are at matched held-out sensitivity (an oracle, not a deployable operating "
        + f"point), cover {len(ok)} of {len(a)} planned points, are uncorrected for multiplicity"
        + (" and say nothing about the standard mix." if no_standard else ".")
    )
    for n, rows in a.groupby("comparator"):
        if n not in names or n in set(ok["comparator"]):
            continue
        reached = int(np.isfinite(rows["total_ratio"]).sum())
        text += f" The {names[n]} gate could not be compared " + (
            f"(its curve reaches only {reached} of its {len(rows)} planned points, all unstable)."
            if reached
            else "(its curve never reaches the comparison range)."
        )
    g = ok[ok["comparator"] == "gbm"]
    if len(g):
        comp = g[g["compression_ratio_hi"] < 1]
        same = bool(((g["total_ratio_lo"] <= 1) & (g["total_ratio_hi"] >= 1)).all())
        text += (
            " CGM-only gradient boosting shifted false alarms between causes: fewer from compression "
            f"({span(comp['compression_ratio'])} times the retuned trend alarm's, at {len(comp)} of "
            f"its {len(g)} points)"
            + (
                f" with no detectable change in the total (ratios {span(g['total_ratio'])}, every CI "
                "including 1)."
                if same
                else f"; total ratio {span(g['total_ratio'])}."
            )
        )
    return text


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


ROBUST_ALARMS = (
    "trend",
    "baysal_gate",
    "matched_filter_causal_gate",
    "iforest_causal_gate",
    "gbm_time",
    "gbm_time_ctx",
    "trend_combined_time_ctx",
)
ARM_MEANING = {
    "robust_delta05": "D5 allows a 5-point loss of level 2 sensitivity",
    "robust_lag6": "CGM rebuilt from plasma with a 6-min lag",
    "robust_tau5": "test PISAs with a 5-min time constant (filter and gates assume 10)",
    "robust_tau20": "test PISAs with a 20-min time constant",
    "robust_early20": "alarms up to 20 min (not 30) before onset count as on time",
    "robust_early45": "alarms up to 45 min before onset count as on time",
    "robust_late30": "alarms up to 30 min (not 15) after onset still catch the low",
}


def section_robustness() -> list[str]:
    lines = ["### Robustness arms (default mix)", ""]
    main = table(TABLES / f"{MAIN}__summary.csv")
    rows = []
    for path in sorted(TABLES.glob("robust_*__summary.csv")):
        name = path.name.split("__")[0]
        s = pd.read_csv(path)
        s = s[s["mix"] == "default"]
        top = s["level"].max()
        lines_arm = []
        for alarm in ROBUST_ALARMS:
            g = s[(s["alarm_name"] == alarm) & (s["level"] == top)]
            if g.empty:
                continue
            r = g.iloc[0]
            ref = "–"
            if main is not None:
                m = main[
                    (main["mix"] == "default")
                    & (main["alarm_name"] == alarm)
                    & (main["level"] == top)
                ]
                if len(m):
                    ref = f"{m['false_per_day'].iloc[0]:.2f}; {m['sens_l2'].iloc[0]:.0%}"
            lines_arm.append(
                f"| {name} | `{alarm}` | {top:.0%} | {ci(r, 'false_per_day')} | {ci(r, 'false_compression_per_day')} | {ci(r, 'sens_l2', pct=True)} | {ref} |"
            )
        if lines_arm:
            rows.append(f"| **{name}**: {ARM_MEANING.get(name, '')} | | | | | | |")
            rows += lines_arm
    if not rows:
        return lines + ["Not run yet.", ""]
    return lines + [
        "Each arm changes one thing (in bold) and is compared with the main analysis at the same PISA level (last column: false alarms/day; level 2 caught).",
        "",
        "| Arm | Alarm | PISA nights | False alarms/day | Compression false alarms/day | Level 2 caught | Main analysis |",
        "|---|---|---|---|---|---|---|",
        *rows,
        "",
    ]


def comparator(b: str) -> tuple[str, str]:
    """Split "best ... alarm (`x` in 4 of 5 folds; ...)" into the comparator and its fold counts."""
    name, _, pool = b.partition(" (")
    return name, pool.removesuffix(")")


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
        f"{mix.capitalize()} mix, which the filter's development did not use (amendment A3). Ratios below 1 and positive sensitivity differences favour the first alarm; 95% paired patient-bootstrap CIs. The comparator is chosen in each fold on training patients only, from in-sample training false alarms (how often each was chosen is listed below). Exploratory: no decision rule. The filter's pressure mode, like the matched filter, uses the same PISA model that generates the injected artifacts, and the τ-mismatch arms do not include the Kalman alarms, so this comparison favours them (docs/development/REVIEW.md M6).",
        "",
        *(
            f"- {name}: {pool}"
            for name, pool in dict.fromkeys(
                comparator(b) for b in r.loc[r["contrast"] == "versus best discriminative", "b"]
            )
        ),
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
        second = comparator(b)[0] if contrast == "versus best discriminative" else f"`{b}`"
        lines.append(f"| {contrast} | `{a}` vs {second} | {measure} | " + " | ".join(cells) + " |")
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
        "Read mechanically from the tables below, with the rules of docs/reference/RESEARCH.md §3 (H1, H2) and amendment A4 (H3); nothing in this section is typed by hand.",
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
            + ". "
            + h1_magnitude(h1)
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
                f"- **H2, secondary** (the ratio is closer to 1 on the high-perturbation mix than on the standard mix): {int(closer)} of {sec[['high', 'standard']].dropna().shape[0]} detectors (point estimates; no CI on the difference)."
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
            readings = h2[(h2["mix"] == matched) & (h2["level"] == lv)]["reading"]
            flat = len(readings) and (readings == "no meaningful reduction").all()
            lines.append(
                f"- **H3** (the context benefit is closer to 1 on real AZT1D nights than in simulation, matched mix `{matched}`, PISA on {lv:.0%} of nights; descriptive, A4): holds for {int(closer)} of {len(both)} detectors."
                + (
                    " Uninformative here: on the matched mix the simulation itself shows no meaningful context benefit (every reading 'no meaningful reduction'), so there is no benefit for real data to shrink."
                    if flat
                    else ""
                )
                + " AZT1D users are on automated insulin delivery, not the open-loop target population (D9)."
            )
    g, hc = table(TABLES / "curves__gates.csv"), table(TABLES / "curves__h2.csv")
    if g is not None and hc is not None:
        d = g[(g["mix"] == "default") & g["retention"].notna()]
        parts = [
            f"`{r['alarm_name']}` from r = {r['retention']:.2f}, compression false alarms × "
            f"{fmt_ci(r['compression_ratio'], r['compression_ratio_lo'], r['compression_ratio_hi'], 3)} "
            f"for {r['extra_missed_l2']:.0f} more missed level 2 lows of {r['events_l2']:.0f}"
            for _, r in d.sort_values("alarm_name").iterrows()
        ]
        lines.append(
            "- **Trade-off curves** (secondary, post hoc, amendment A11; default mix; r = training sensitivity kept relative to `trend`): the gates start removing compression false alarms at "
            + "; ".join(parts)
            + ". "
            + h2_curves_note(hc)
        )
    a13 = table(TABLES / "curves__a13.csv")
    if a13 is not None and len(a13):
        lines.append(
            "- **A13** (secondary, post hoc; gates and CGM-only gradient boosting vs. the trend alarm with its threshold retuned, at matched held-out level 2 sensitivity): "
            + a13_verdict(a13)
        )
    rq3 = table(TABLES / "rq3_kalman__contrasts_rq3.csv")
    if rq3 is not None and len(rq3):
        r = rq3[(rq3["mix"] == "default") & (rq3["level"] == rq3["level"].max())]
        r = r[(r["a"] == "kalman_pisa") & (r["measure"] == "false alarms, ratio")]
        parts = [
            f"vs. {comparator(row['b'])[0] if row['contrast'] == 'versus best discriminative' else '`' + row['b'] + '`'} "
            f"{fmt_ci(row['estimate'], row['lo'], row['hi'])}"
            for _, row in r.iterrows()
        ]
        if parts:
            lines.append(
                f"- **RQ3** (exploratory; default mix, PISA on {r['level'].iloc[0]:.0%} of nights; `kalman_pisa`, false alarms, ratio): "
                + "; ".join(parts)
                + ". Compression false alarms and level 2 sensitivity: [RQ3 table](#rq3-exploratory-a-kalman-filter-with-an-explicit-compressed-state)."
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
        f"### Semi-synthetic RQ1 (D16): {meta.get('dataset', 'Weinstock 2016')}",
        "",
        f"{meta.get('patients')} people, {meta.get('days', float('nan')):.0f} days. Reference lows are taken from the un-injected CGM: "
        f"{meta.get('reference_l1_events')} level 1, {meta.get('reference_l2_events')} level 2. {meta.get('labelled', '')}",
        "",
        "**Read this table for the compression column only.** The reference lows come from the same CGM the alarms read, and outside the injected PISAs the two are identical. Lows caught (†) is therefore near-circular: `threshold` catches every level 1 low and every alarm catches every level 2 low by construction (amendment A5), and the learned alarms are trained to predict their own input falling below 70 mg/dL. Lows caught and total false alarms do not rank alarms on real data. What this track measures is the false alarms caused by the injected PISAs, and how they grow with the share of PISA nights; only that column supports the co-primary role D16 gives the track.",
        "",
        "| Alarm | PISA nights | False alarms/day | Compression false alarms/day | Level 1 caught † | Level 2 caught † |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in s.sort_values(["alarm_name", "level"]).iterrows():
        lines.append(
            f"| `{r['alarm_name']}` | {r['level']:.0%} | {ci(r, 'false_per_day')} | {ci(r, 'false_compression_per_day')} | "
            f"{ci(r, 'sens_l1', pct=True)} | {ci(r, 'sens_l2', pct=True)} |"
        )
    lines += gates_note(s, curves=False)
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
    lines = ["### H3: the context benefit on real data (AZT1D)", ""]
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
    if sim is not None and matched:
        readings = sim[(sim["mix"] == matched) & (sim["level"] == level)]["reading"]
        if len(readings) and (readings == "no meaningful reduction").all():
            lines += [
                "",
                f"On the matched mix (`{matched}`) the simulation itself shows no meaningful context benefit, so both ratios sit near 1 and H3 is uninformative: there is no simulated benefit for real data to shrink.",
            ]
    lines += ["", azt1d_note(a)]
    return lines + [""]


def azt1d_note(a: pd.DataFrame) -> str:
    """What the AZT1D ratios alone can and cannot say."""
    ok = a.dropna(subset=["rate_ratio"])
    if ok.empty:
        return ""
    widest = (ok["hi"] - ok["lo"]).idxmax()
    w = ok.loc[widest]
    all_one = bool(((ok["lo"] <= 1) & (ok["hi"] >= 1)).all())
    return (
        ("On AZT1D every CI includes 1" if all_one else "On AZT1D not every CI includes 1")
        + f"; the widest, `{widest}` ({w['lo']:.2f}–{w['hi']:.2f}), does not exclude a modest benefit. "
        "AZT1D users are on automated insulin delivery (Control-IQ), not the open-loop population "
        "RQ2 targets (D9), and the artifacts are injected, not real."
    )


def section_reproducibility() -> list[str]:
    """Which commit produced which table, and what the clean-checkout check covered."""
    by_commit: dict[str, list[str]] = {}
    for f in sorted(TABLES.glob("*__git_commit.txt")):
        by_commit.setdefault(f.read_text().strip()[:7], []).append(f.name.split("__")[0])
    lines = ["## Reproducibility", ""]
    if by_commit:
        lines.append(
            "Each benchmark run records the commit it ran at (`results/tables/<run>__git_commit.txt`): "
            + "; ".join(
                f"`{c}` for {', '.join(f'`{n}`' for n in names)}" for c, names in by_commit.items()
            )
            + ". The warning-time, age-group and RQ3 tables were derived afterwards from each run's "
            "`metrics.csv` by `experiments/run_all.py` at later commits, and the real-data tables "
            "(`real__*`) carry no commit record."
        )
        lines.append("")
    lines += [
        "`make reproduce` (`scripts/check_reproducible.py`) clones the commit recorded for `rq1_pisa_sweep`, installs it with `uv sync --locked`, reruns that config on the cached cohort, compares the tables, and re-simulates three randomly chosen patient-runs. On 2026-10-18 it reproduced `summary.csv` (540 rows), `contrasts_h2.csv` (108), `contrast_h1.csv` (3) and `thresholds.csv` (450) exactly from commit `4725089`, and the three re-simulated runs matched the cached cohort exactly.",
        "",
        "This is weaker than re-running everything. It needs the cached cohort under `data/sim/` (from `make results`, about 2.3 h). The cohort's cache key includes the package version, and the cohort was simulated at version 0.0.1, so at a later version `make results` simulates it afresh under a new key. The full pipeline was run once to produce these results and has not been repeated from a clean clone.",
        "",
    ]
    return lines


def limitations() -> list[str]:
    text = (REPO / "docs" / "reference" / "RESEARCH.md").read_text()
    m = re.search(r"## 6\. Known limitations to state up front\n(.*?)\n## 7", text, flags=re.S)
    return [
        "## Limitations (from docs/reference/RESEARCH.md §6)",
        "",
        m.group(1).strip() if m else "See docs/reference/RESEARCH.md §6.",
        "",
    ]


def main() -> None:
    summary = table(TABLES / f"{MAIN}__summary.csv")
    meta_path = TABLES / f"{MAIN}__meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    lines = [
        "# Results",
        "",
        "Every benchmark result, for anyone checking a claim. Generated by `experiments/make_results_readme.py` from the tables in `results/tables/`; do not edit by hand. Regenerate everything with `make results`.",
        "Benchmark version: `ghostlows-bench v1`. Simulated cohort: 30 virtual patients (UVA/Padova 2008 via simglucose), 14 days, 5 seeds, three scenario mixes. Confidence intervals are 95% patient-bootstrap intervals over this cohort, not a population (BENCHMARK.md §6).",
        "",
    ]
    if summary is None:
        lines += ["No results yet: run `make results`.", ""]
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
            *section_all_faults(),
            *section_h2(table(TABLES / f"{MAIN}__contrasts_h2.csv"), meta.get("train_level")),
            *section_curves(),
            *section_a13(),
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
    lines += section_reproducibility()
    lines += [
        *limitations(),
        "## Assumptions",
        "",
        "Every `# ASSUMPTION:` in the code, collected from the current code when this README is generated: `results/tables/assumptions.md`.",
        "",
    ]
    (TABLES / "assumptions.md").write_text(collect_assumptions())
    (REPO / "results" / "README.md").write_text("\n".join(lines))
    print("wrote results/README.md")


if __name__ == "__main__":
    main()
