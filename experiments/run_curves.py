"""Trade-off curves (amendment A11; secondary, post hoc) into results/curves/ and results/tables/.

    uv run python experiments/run_curves.py            # skips the sweep if points.csv exists
    uv run python experiments/run_curves.py --force    # recompute the sweep

Scores every candidate threshold of the alarms in configs/curves.yaml on training and held-out
patients (`ghostlows.bench.curves`), then writes the curve table, the gate and H2 readings, the
check that r = 1 reproduces the v0.1.0 operating points, and one figure per scenario mix. If the
check fails, nothing is copied to results/tables/ (A11).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ghostlows.bench import curves  # noqa: E402
from ghostlows.bench.pipeline import BenchConfig  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "curves"
TABLES, FIGURES = REPO / "results" / "tables", REPO / "results" / "figures"
SOURCES = ("rq1_pisa_sweep", "rq3_kalman")  # the v0.1.0 runs the r = 1 point must reproduce
CHECKED = ["sens_l2", "false_per_day", "false_compression_per_day"]
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
ARM_COLORS = {"published": MUTED, "base": "#2a78d6", "context": "#eb6834"}
MARKERS = {"r=1.00": "o", "r=0.99": "s", "r=0.95": "^", "published": "*"}
TITLES = {
    "threshold": "threshold",
    "trend": "trend",
    "baysal": "Baysal",
    "matched_filter_causal": "matched filter",
    "iforest_causal": "isolation forest",
    "gbm": "gradient boosting",
    "kalman": "Kalman (exploratory)",
}
PUBLISHED_OF = {
    "threshold": "threshold",
    "trend": "trend",
    "baysal": "baysal_gate",
    "matched_filter_causal": "matched_filter_causal_gate",
    "iforest_causal": "iforest_causal_gate",
}


def check(summary: pd.DataFrame) -> pd.DataFrame:
    """r = 1 (published point for the rule alarms) against the v0.1.0 summary at PISA on every
    night, and r = 1 thresholds against the v0.1.0 thresholds (amendment A11)."""
    rows = []
    for source in SOURCES:
        s = pd.read_csv(TABLES / f"{source}__summary.csv")
        s = s[np.isclose(s["level"], 1.0)]
        t = pd.read_csv(TABLES / f"{source}__thresholds.csv")
        for _, b in s[s["alarm_name"].isin(summary["alarm_name"])].iterrows():
            point = "published" if b["alarm_name"] in curves.PUBLISHED else "r=1.00"
            a = summary[
                (summary["alarm_name"] == b["alarm_name"])
                & (summary["mix"] == b["mix"])
                & (summary["point"] == point)
            ]
            for col in [c + e for c in CHECKED for e in ("", "_lo", "_hi")]:
                rows.append(
                    {
                        "source": source,
                        "alarm_name": b["alarm_name"],
                        "mix": b["mix"],
                        "point": point,
                        "measure": col,
                        "v0.1.0": b[col],
                        "curve": a[col].iloc[0] if len(a) else np.nan,
                    }
                )
        rows += threshold_rows(source, t)
    out = pd.DataFrame(rows)
    out["reproduced"] = np.isclose(out["v0.1.0"], out["curve"], rtol=0, atol=1e-9, equal_nan=True)
    return out


def threshold_rows(source: str, t: pd.DataFrame) -> list[dict]:
    chosen = pd.read_csv(OUT / "choices.csv")
    r1 = chosen[chosen["point"] == "r=1.00"]
    m = t.merge(r1, on=["mix", "fold", "alarm_name"], suffixes=("_v010", ""))
    m = m[~m["alarm_name"].isin(curves.PUBLISHED)]  # D5 never tunes the rule alarms
    return [
        {
            "source": source,
            "alarm_name": r["alarm_name"],
            "mix": r["mix"],
            "point": f"r=1.00, fold {r['fold']}",
            "measure": "threshold",
            "v0.1.0": r["threshold_v010"],
            "curve": r["threshold"],
        }
        for _, r in m.iterrows()
    ]


def figure(summary: pd.DataFrame, mix: str, path: Path) -> None:
    """Held-out false alarms per day (compression; other causes) against level 2 sensitivity."""
    s = summary[summary["mix"] == mix]
    families = list(TITLES)
    fig, axes = plt.subplots(
        2, len(families), figsize=(2.9 * len(families), 6.2), facecolor=SURFACE, sharex=True
    )
    for j, (family, base, context) in enumerate(curves.PAIRS):
        series = {"base": base, "context": context}
        if family in PUBLISHED_OF:
            series = {"published": PUBLISHED_OF[family], **series}
        for i, (cause, label) in enumerate(
            [("false_compression_per_day", "compression"), ("false_other_per_day", "other causes")]
        ):
            ax = axes[i, j]
            for arm, name in series.items():
                g = s[(s["alarm_name"] == name) & s["retention"].notna()].sort_values("sens_l2")
                if g.empty:
                    continue
                color = ARM_COLORS[arm]
                ax.plot(g["sens_l2"], g[cause], color=color, lw=1.4, label=legend(arm, family))
                ax.fill_between(
                    g["sens_l2"], g[f"{cause}_lo"], g[f"{cause}_hi"], color=color, alpha=0.12, lw=0
                )
                for point, marker in MARKERS.items():
                    p = s[(s["alarm_name"] == name) & (s["point"] == point)]
                    if p.empty:
                        continue
                    r = p.iloc[0]
                    ax.errorbar(
                        r["sens_l2"],
                        r[cause],
                        xerr=[[r["sens_l2"] - r["sens_l2_lo"]], [r["sens_l2_hi"] - r["sens_l2"]]],
                        yerr=[[r[cause] - r[f"{cause}_lo"]], [r[f"{cause}_hi"] - r[cause]]],
                        fmt=marker,
                        ms=8 if marker == "*" else 5,
                        color=color,
                        mec=INK if point == "r=1.00" else color,
                        mew=0.8,
                        elinewidth=0.8,
                        capsize=0,
                        zorder=3,
                    )
            ax.set_facecolor(SURFACE)
            ax.grid(color=GRID, lw=0.6)
            ax.spines[["top", "right"]].set_visible(False)
            ax.tick_params(colors=MUTED, labelsize=8)
            if i == 0:
                ax.set_title(TITLES[family], loc="left", color=INK, fontsize=10)
                ax.legend(fontsize=7, frameon=False, loc="upper left")
            if j == 0:
                ax.set_ylabel(f"{label} false alarms/day", color=MUTED, fontsize=9)
            if i == 1:
                ax.set_xlabel("level 2 sensitivity (held out)", color=MUTED, fontsize=9)
    fig.suptitle(
        f"Trade-off curves, {mix} mix, PISA on every night (secondary, post hoc; amendment A11). "
        "Markers: circle r = 1.00 (pre-registered, delta = 0), square r = 0.99, triangle r = 0.95, "
        "star published rule; bars and bands: patient-bootstrap 95% CIs",
        x=0.01,
        ha="left",
        fontsize=9,
        color=INK,
    )
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(f"{path}.{ext}", dpi=130, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


A13_COLORS = {
    "baysal_gate": "#2a78d6",
    "matched_filter_causal_gate": "#1baf7a",
    "iforest_causal_gate": "#eb6834",
    "gbm": "#eda100",
}


def a13_figure(c: pd.DataFrame, a13: pd.DataFrame, path: Path) -> None:
    """Amendment A13: false alarms per day against held-out level 2 sensitivity, retuned `trend`
    as the reference line (with its 95% band), the comparison window shaded."""
    mixes = sorted(c["mix"].unique())
    fig, axes = plt.subplots(
        2, len(mixes), figsize=(4.6 * len(mixes), 6.6), facecolor=SURFACE, squeeze=False
    )
    for j, mix in enumerate(mixes):
        window = a13[a13["mix"] == mix]["sens_l2"]
        for i, (col, label) in enumerate(
            [("false_per_day", "all"), ("false_compression_per_day", "compression")]
        ):
            ax = axes[i, j]
            ax.axvspan(window.min(), window.max(), color=GRID, alpha=0.6, lw=0)
            for name in (curves.A13_REFERENCE, *curves.A13_COMPARATORS):
                g = c[(c["mix"] == mix) & (c["alarm_name"] == name)]
                if g.empty:
                    continue
                # ties averaged, as in the interpolation (curves.interpolate)
                g = g.groupby("sens_l2", as_index=False).mean(numeric_only=True)
                ref = name == curves.A13_REFERENCE
                color = INK if ref else A13_COLORS[name]
                ax.plot(
                    g["sens_l2"],
                    g[col],
                    color=color,
                    lw=2.0 if ref else 1.3,
                    label="trend, retuned (reference)" if ref else name,
                    zorder=3 if ref else 2,
                )
                if ref:
                    ax.fill_between(
                        g["sens_l2"], g[f"{col}_lo"], g[f"{col}_hi"], color=INK, alpha=0.1, lw=0
                    )
            ax.set_xlim(max(0.4, window.min() - 0.15), window.max() + 0.06)
            ax.set_facecolor(SURFACE)
            ax.grid(color=GRID, lw=0.6)
            ax.spines[["top", "right"]].set_visible(False)
            ax.tick_params(colors=MUTED, labelsize=8)
            if i == 0:
                ax.set_title(f"{mix} mix", loc="left", color=INK, fontsize=10)
            if j == 0:
                ax.set_ylabel(f"{label} false alarms/day", color=MUTED, fontsize=9)
                if i == 0:
                    ax.legend(fontsize=7, frameon=False, loc="upper left")
            if i == 1:
                ax.set_xlabel("level 2 sensitivity (held out)", color=MUTED, fontsize=9)
    fig.suptitle(
        "A13 (secondary, post hoc): CGM-only alarms against the trend alarm with its own threshold "
        "swept, PISA on every night. Shaded: the comparison window; band: trend's 95% CI",
        x=0.01,
        ha="left",
        fontsize=9,
        color=INK,
    )
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(f"{path}.{ext}", dpi=130, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def legend(arm: str, family: str) -> str:
    if arm == "published":
        return "as published"
    if family == "kalman":
        return "CGM only" if arm == "base" else "+ IOB/COB"
    return "CGM + time" if arm == "base" else "+ IOB/COB"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--workers", type=int, default=max(1, min(6, (os.cpu_count() or 2) - 1)))
    args = parser.parse_args()
    config = BenchConfig.load(REPO / "experiments" / "configs" / "curves.yaml")
    config.workers = args.workers
    if args.force:
        (OUT / "points.csv").unlink(missing_ok=True)
    curves.run_curves(config, OUT)  # sweeps only alarms not yet in points.csv
    points = pd.read_csv(OUT / "points.csv")
    chosen = curves.choices(points)
    chosen.to_csv(OUT / "choices.csv", index=False)
    pp = curves.per_patient_at(points, chosen)
    summary = curves.curve_summary(pp, n_boot=config.n_boot)
    gates = curves.first_reduction(pp, curves.GATES, n_boot=config.n_boot)
    h2 = curves.h2_on_curves(pp, n_boot=config.n_boot, sesoi=config.sesoi)
    checked = check(summary)
    a13_pp = curves.a13_points(points)
    a13 = curves.matched_comparison(a13_pp, n_boot=config.n_boot)
    a13_curves = curves.curve_summary(
        a13_pp.assign(point=a13_pp["retention"].map(str)), config.n_boot
    )
    outputs = {"summary": summary, "gates": gates, "h2": h2, "check": checked, "a13": a13}
    outputs["a13_curves"] = a13_curves
    for name, frame in outputs.items():
        frame.to_csv(OUT / f"{name}.csv", index=False)
    if not checked["reproduced"].all():
        bad = checked[~checked["reproduced"]]
        print(bad.head(20).to_string(index=False))
        print(f"{len(bad)} of {len(checked)} checks differ from v0.1.0: nothing copied (A11)")
        return 1
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    meta = {
        "amendment": "A11 (secondary, post hoc)",
        "test_level": float(points["test_level"].iloc[0]),
        "train_level": float(points["train_level"].iloc[0]),
        "retentions": [min(curves.RETENTIONS), max(curves.RETENTIONS), 0.01],
        "marked": list(curves.MARKED),
        "n_boot": config.n_boot,
        "checks": int(len(checked)),
        "checks_reproduced": int(checked["reproduced"].sum()),
        "a13": {
            "amendment": "A13 (secondary, post hoc)",
            "reference": curves.A13_REFERENCE,
            "comparators": list(curves.A13_COMPARATORS),
            "fine_retention_step": 0.0025,
            "offsets": list(curves.A13_OFFSETS),
        },
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    (OUT / "git_commit.txt").write_text(commit)
    (OUT / "figures").mkdir(exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    for mix in sorted(summary["mix"].unique()):
        figure(summary, mix, OUT / "figures" / mix)
        shutil.copy(OUT / "figures" / f"{mix}.png", FIGURES / f"curves__{mix}.png")
    a13_figure(a13_curves, a13, OUT / "figures" / "a13")
    shutil.copy(OUT / "figures" / "a13.png", FIGURES / "curves__a13.png")
    for name in ("summary", "gates", "h2", "check", "a13"):
        shutil.copy(OUT / f"{name}.csv", TABLES / f"curves__{name}.csv")
    for name in ("meta.json", "git_commit.txt"):
        shutil.copy(OUT / name, TABLES / f"curves__{name}")
    print(f"checks: {len(checked)} reproduced v0.1.0; wrote results/tables/curves__*.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
