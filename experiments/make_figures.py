"""Figures for a benchmark run (BENCHMARK.md §7): PNG + SVG in results/<run>/figures/.

    uv run python experiments/make_figures.py results/<run_id>

Palette: the reference categorical slots in fixed order (validated with the dataviz checker);
at most four series per panel; one y-axis per panel; CI bands from summary.csv.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from ghostlows.bench.analysis import context_contrasts  # noqa: E402

INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # categorical slots 1-4, fixed order
CAUSE_COLORS = {
    "compression": "#2a78d6",
    "other_fault": "#eb6834",
    "near_event": "#1baf7a",
    "noise": "#8a8984",
}
CGM_ONLY = ["threshold", "trend", "baysal_gate", "matched_filter_causal_gate"]


def style(ax, title):
    ax.set_title(title, loc="left", color=INK, fontsize=10)
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, lw=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=MUTED)


def save(fig, out: Path, name: str) -> None:
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(out / f"{name}.{ext}", dpi=150, facecolor=SURFACE)
    plt.close(fig)


def severity_curves(summary: pd.DataFrame, out: Path) -> None:
    mixes = sorted(summary["mix"].unique())
    fig, axes = plt.subplots(
        1, len(mixes), figsize=(4.2 * len(mixes), 3.6), facecolor=SURFACE, squeeze=False
    )
    for ax, mix in zip(axes[0], mixes, strict=True):
        s = summary[summary["mix"] == mix]
        for color, alarm in zip(SLOTS, CGM_ONLY, strict=False):
            g = s[s["alarm_name"] == alarm].sort_values("level")
            if g.empty:
                continue
            ax.fill_between(
                g["level"],
                g["false_per_day_lo"],
                g["false_per_day_hi"],
                color=color,
                alpha=0.15,
                lw=0,
            )
            ax.plot(
                g["level"],
                g["false_per_day"],
                color=color,
                lw=2,
                marker="o",
                ms=4,
                label=alarm,
            )
        style(ax, f"False alarms per day vs. PISA nights ({mix})")
        ax.set_xlabel("fraction of nights with a PISA")
        ax.set_ylabel("false alarms per day")
    axes[0][0].legend(frameon=False, fontsize=8)
    save(fig, out, "severity_curves")


def causes(summary: pd.DataFrame, out: Path, fraction: float) -> None:
    s = summary[(summary["level"] == fraction)]
    mix = "default" if "default" in set(s["mix"]) else s["mix"].iloc[0]
    s = s[s["mix"] == mix].sort_values("false_per_day")
    fig, ax = plt.subplots(figsize=(7, 0.35 * len(s) + 1.5), facecolor=SURFACE)
    left = pd.Series(0.0, index=s.index)
    for cause, color in CAUSE_COLORS.items():
        col = f"false_{cause}_per_day"
        if col in s:
            ax.barh(
                s["alarm_name"],
                s[col],
                left=left,
                color=color,
                height=0.6,
                label=cause.replace("_", " "),
                edgecolor=SURFACE,
                linewidth=1,
            )
            left = left + s[col]
    style(ax, f"False alarms per day by cause (fault level {fraction}, {mix} mix)")
    ax.set_xlabel("false alarms per day")
    ax.legend(frameon=False, fontsize=8, ncol=4, loc="upper left", bbox_to_anchor=(0, -0.12))
    save(fig, out, "false_alarms_by_cause")


def sens_vs_false(summary: pd.DataFrame, out: Path, fraction: float) -> None:
    s = summary[(summary["level"] == fraction)]
    mix = "default" if "default" in set(s["mix"]) else s["mix"].iloc[0]
    s = s[s["mix"] == mix].dropna(subset=["sens_l2"])
    fig, ax = plt.subplots(figsize=(6.5, 4.5), facecolor=SURFACE)
    ax.errorbar(
        s["false_per_day"],
        s["sens_l2"],
        xerr=[
            s["false_per_day"] - s["false_per_day_lo"],
            s["false_per_day_hi"] - s["false_per_day"],
        ],
        fmt="o",
        color=SLOTS[0],
        ecolor=GRID,
        ms=5,
    )
    for _, r in s.iterrows():
        ax.annotate(
            r["alarm_name"],
            (r["false_per_day"], r["sens_l2"]),
            fontsize=6,
            color=MUTED,
            xytext=(3, 3),
            textcoords="offset points",
        )
    style(ax, f"Level 2 sensitivity vs. false alarms (fault level {fraction}, {mix} mix)")
    ax.set_xlabel("false alarms per day")
    ax.set_ylabel("level 2 lows caught")
    save(fig, out, "sensitivity_vs_false_alarms")


def context_forest(metrics: pd.DataFrame, out: Path, n_boot: int) -> pd.DataFrame:
    c = context_contrasts(metrics, n_boot=n_boot)
    c.to_csv(out.parent / "context_contrasts.csv", index=False)
    if c.empty:  # no context arms in this run
        return c
    c = c.dropna(subset=["rate_ratio"])
    if c.empty:
        return c
    c = c[c["level"] == c["level"].max()]
    fig, ax = plt.subplots(figsize=(6.5, 0.45 * len(c) + 1.5), facecolor=SURFACE)
    labels = c["detector"] + " (" + c["mix"] + ")"
    ax.errorbar(
        c["rate_ratio"],
        range(len(c)),
        xerr=[c["rate_ratio"] - c["lo"], c["hi"] - c["rate_ratio"]],
        fmt="o",
        color=SLOTS[0],
        ecolor=SLOTS[0],
        ms=5,
        capsize=0,
    )
    ax.axvline(1.0, color=MUTED, lw=0.8)
    ax.axvline(0.75, color=MUTED, lw=0.8, ls=(0, (4, 3)))
    ax.text(0.75, len(c) - 0.4, "SESOI 0.75", color=MUTED, fontsize=7, ha="right")
    ax.set_yticks(range(len(c)), labels)
    style(ax, "H2: compression false alarms, +IOB/COB vs. CGM + time (rate ratio)")
    ax.set_xlabel("rate ratio (95% patient-bootstrap CI)")
    save(fig, out, "context_rate_ratios")
    return c


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("run", type=Path)
    parser.add_argument(
        "--fraction", type=float, default=None, help="fault level for the snapshot figures"
    )
    parser.add_argument("--n-boot", type=int, default=2000)
    args = parser.parse_args()
    summary = pd.read_csv(args.run / "summary.csv")
    metrics = pd.read_csv(args.run / "metrics.csv")
    out = args.run / "figures"
    out.mkdir(exist_ok=True)
    fraction = args.fraction if args.fraction is not None else float(summary["level"].max())
    severity_curves(summary, out)
    causes(summary, out, fraction)
    sens_vs_false(summary, out, fraction)
    context_forest(metrics, out, args.n_boot)
    print(f"figures in {out}")


if __name__ == "__main__":
    main()
