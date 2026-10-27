"""The publication figures, drawn from the committed tables in results/tables/ only.

    uv run python experiments/make_paper_figures.py      # or: make figures

Writes results/figures/fig1_*.{svg,pdf,png} to fig5_*, and the 1280 x 640 GitHub social preview
docs/figures/social_preview.png (from figure 1). The style is experiments/figstyle.py. The
captions are generated with results/README.md by experiments/make_results_readme.py.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from figstyle import (
    AQUA,
    AXIS,
    BAND_ALPHA,
    BLUE,
    COLUMN_IN,
    GRID,
    INK,
    MUTED,
    ORANGE,
    SECONDARY,
    SLOTS,
    SURFACE,
    YELLOW,
    save,
    use,
)
from matplotlib import pyplot as plt
from matplotlib.ticker import FixedLocator, NullLocator, PercentFormatter

REPO = Path(__file__).resolve().parents[1]
TABLES = REPO / "results" / "tables"
FIGURES = REPO / "results" / "figures"
SOCIAL = REPO / "docs" / "figures" / "social_preview.png"
MAIN = "rq1_pisa_sweep"
# (summary column, legend label), bottom to top, in the attribution order of BENCHMARK.md §4
CAUSES = [
    ("false_compression_per_day", "Compression (PISA)"),
    ("false_other_fault_per_day", "Other sensor fault"),
    ("false_near_event_per_day", "Near a true low"),
    ("false_noise_per_day", "Noise, nothing nearby"),
]
DETECTORS = {
    "threshold": "Threshold",
    "trend": "Trend",
    "baysal": "Baysal",
    "matched_filter_causal": "Matched filter",
    "iforest_causal": "Isolation forest",
    "gbm": "Gradient boosting",
}
COMPARATORS = {  # the A13 comparators in the code's order: (label, colour, marker)
    "baysal_gate": ("Baysal gate", BLUE, "o"),
    "matched_filter_causal_gate": ("Matched-filter gate", ORANGE, "s"),
    "iforest_causal_gate": ("Isolation-forest gate", AQUA, "D"),
    "gbm": ("Gradient boosting (CGM)", YELLOW, "^"),
}
FIGURE_STEMS = (
    "fig1_false_alarms_by_cause",
    "fig2_h1_trend_vs_threshold",
    "fig3_context_h2_h3",
    "fig4_tradeoff_matched_sensitivity",
    "fig5_real_cgm_check",
)


def table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES / name)


def whiskers(ax, x, y, lo, hi, color, marker="o", filled=True, label=None, horizontal=False):
    """Points with 95% CI whiskers (no caps) and a surface ring; when not `filled`, hollow,
    smaller and with fainter whiskers, so the points that are not read recede."""
    x, y, lo, hi = (np.asarray(v, float) for v in (x, y, lo, hi))
    err = [x - lo, hi - x] if horizontal else [y - lo, hi - y]
    _, _, (bars,) = ax.errorbar(
        x,
        y,
        xerr=err if horizontal else None,
        yerr=None if horizontal else err,
        fmt=marker,
        color=color,
        markerfacecolor=color if filled else SURFACE,
        markeredgecolor=SURFACE if filled else color,
        markeredgewidth=0.6 if filled else 0.7,
        elinewidth=0.9,
        markersize=4 if filled else 3,
        capsize=0,
        label=label,
        zorder=3,
    )
    if not filled:
        bars.set_alpha(0.45)


def percent_axis(axis) -> None:
    axis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))


def log_ticks(axis, ticks) -> None:
    axis.set_major_locator(FixedLocator(ticks))
    axis.set_minor_locator(NullLocator())
    axis.set_major_formatter(lambda v, _: f"{v:g}")


def causes_panel(ax, summary: pd.DataFrame, fontsize: float = 6.5) -> None:
    """Figure 1's chart: the trend alarm's false alarms per day by cause at each PISA level."""
    d = summary[(summary["alarm_name"] == "trend") & (summary["mix"] == "default")]
    d = d.sort_values("level").reset_index(drop=True)
    x = np.arange(len(d))
    bottom = np.zeros(len(d))
    for (col, label), color in zip(CAUSES, SLOTS, strict=True):
        h = d[col].to_numpy(float)
        ax.bar(x, h, 0.62, bottom=bottom, color=color, edgecolor=SURFACE, lw=0.8, label=label)
        bottom += h
    total = d["false_per_day"].to_numpy(float)
    ax.errorbar(
        x,
        total,
        yerr=[total - d["false_per_day_lo"], d["false_per_day_hi"] - total],
        fmt="none",
        ecolor=INK,
        elinewidth=0.8,
        capsize=0,
        zorder=3,
    )
    last, top = d.iloc[-1], x[-1]
    compression = last["false_compression_per_day"]
    ax.text(top, compression / 2, f"{compression:.2f}", ha="center", va="center",
            fontsize=fontsize, color=SURFACE, fontweight="bold")  # fmt: skip
    ax.text(top + 0.36, last["false_per_day"], f"{last['false_per_day']:.2f}", ha="left",
            va="center", fontsize=fontsize, color=INK)  # fmt: skip
    ax.set_xticks(x, [f"{v:.0%}" for v in d["level"]])
    ax.set_xlim(-0.5, len(d) - 0.05)
    ax.grid(axis="x", visible=False)
    ax.set_xlabel("Nights with a compression artifact (PISA)")
    ax.set_ylabel("False alarms per day, trend alarm")
    ax.set_ylim(0, None)


def fig1(summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(COLUMN_IN, 2.35))
    causes_panel(ax, summary)
    ax.legend(ncol=2, loc="lower left", bbox_to_anchor=(-0.02, 1.0), borderaxespad=0.2)
    save(fig, FIGURES, FIGURE_STEMS[0])


def fig2(summary: pd.DataFrame, h1: pd.DataFrame) -> None:
    d = summary[summary["mix"] == "default"]
    fig, ax = plt.subplots(figsize=(COLUMN_IN, 2.3))
    for alarm, color, label in (
        ("trend", BLUE, "Trend alarm (predicted < 55 mg/dL in 20 min)"),
        ("threshold", ORANGE, "Threshold alarm (< 70 mg/dL)"),
    ):
        g = d[d["alarm_name"] == alarm].sort_values("level")
        ax.fill_between(
            g["level"],
            g["false_per_day_lo"],
            g["false_per_day_hi"],
            color=color,
            alpha=BAND_ALPHA,
            lw=0,
        )
        ax.plot(
            g["level"],
            g["false_per_day"],
            color=color,
            marker="o",
            label=label,
            markeredgecolor=SURFACE,
            markeredgewidth=0.6,
        )
    r = h1.set_index("mix").loc["default"]
    ax.text(
        0.98,
        0.06,
        f"H1, trend − threshold: +{r['median_slope_diff']:.2f} ({r['lo']:.2f}–{r['hi']:.2f})\n"
        "false alarms/day from no PISA nights to all",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=6.5,
        color=INK,
    )
    percent_axis(ax.xaxis)
    ax.set_xlabel("Nights with a compression artifact (PISA)")
    ax.set_ylabel("False alarms per day")
    ax.set_ylim(0, None)
    ax.set_xlim(-0.03, 1.03)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.02, 1.0), borderaxespad=0.2)
    save(fig, FIGURES, FIGURE_STEMS[1])


def forest(ax, rows: list[tuple[str, pd.DataFrame, str, str]], title: str) -> None:
    """rows: (label, contrasts indexed by detector, colour, marker), dodged within each row."""
    names = list(DETECTORS)
    lo, hi = 0.6, 1.3
    ax.set_xscale("log")
    log_ticks(ax.xaxis, [0.6, 0.75, 0.9, 1.0, 1.1, 1.25])
    ax.set_xlim(lo, hi)
    ax.axvspan(lo, 0.75, color=GRID, alpha=0.45, lw=0, zorder=0)  # below the SESOI
    ax.axvline(1.0, color=AXIS, lw=0.8, zorder=1)
    offsets = np.linspace(-0.22, 0.22, len(rows))
    for (label, c, color, marker), off in zip(rows, offsets, strict=True):
        c = c.reindex(names)
        y = np.arange(len(names)) + off
        ok = c["rate_ratio"].notna().to_numpy()
        whiskers(
            ax,
            c["rate_ratio"][ok],
            y[ok],
            c["lo"][ok],
            c["hi"][ok],
            color,
            marker=marker,
            label=label,
            horizontal=True,
        )
    ax.set_yticks(np.arange(len(names)), [DETECTORS[n] for n in names])
    ax.set_ylim(len(names) - 0.5, -0.5)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.set_title(title, pad=13)
    ax.legend(
        loc="lower left",
        bbox_to_anchor=(-0.02, 0.99),
        ncol=len(rows),
        borderaxespad=0.0,
        handletextpad=0.2,
        columnspacing=0.9,
    )


def fig3(h2: pd.DataFrame, azt: pd.DataFrame) -> None:
    sim = h2[(h2["level"] == 1.0) & (h2["cause"] == "compression")]
    by_mix = {m: g.set_index("detector") for m, g in sim.groupby("mix")}
    real = azt[(azt["level"] == 1.0) & (azt["cause"] == "compression")].set_index("detector")
    fig, (a, b) = plt.subplots(
        2, 1, figsize=(COLUMN_IN, 4.0), sharex=True, gridspec_kw={"hspace": 0.45}
    )
    forest(
        a,
        [
            ("Default mix", by_mix["default"], BLUE, "o"),
            ("High mix", by_mix["high"], ORANGE, "s"),
            ("Standard mix", by_mix["standard"], AQUA, "D"),
        ],
        "a  Simulation, 30 virtual patients (H2)",
    )
    forest(
        b,
        [
            ("AZT1D, 25 people", real, INK, "o"),
            ("Simulation, matched mix (high)", by_mix["high"], ORANGE, "s"),
        ],
        "b  Real nights with injected PISAs (H3)",
    )
    a.text(0.61, -0.4, "≥ 25%\nfewer", fontsize=6, color=SECONDARY, va="top")  # the SESOI
    b.set_xlabel("Compression false alarms, with ÷ without IOB/COB (log)")
    save(fig, FIGURES, FIGURE_STEMS[2])


def fig4(curves: pd.DataFrame, a13: pd.DataFrame) -> None:
    d = curves[(curves["mix"] == "default") & curves["retention"].notna()]
    fig = plt.figure(figsize=(COLUMN_IN, 4.6))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.15, 1], hspace=0.55, wspace=0.1)
    a = fig.add_subplot(grid[0, :])
    b = fig.add_subplot(grid[1, 0])
    c = fig.add_subplot(grid[1, 1], sharey=b)
    t = d[d["alarm_name"] == "trend"].sort_values("sens_l2")
    a.fill_between(
        t["sens_l2"], t["false_per_day_lo"], t["false_per_day_hi"], color=MUTED, alpha=0.18, lw=0
    )
    a.plot(t["sens_l2"], t["false_per_day"], color=MUTED, lw=2.0, label="Trend, threshold lowered")
    for name, (label, color, marker) in COMPARATORS.items():
        g = d[d["alarm_name"] == name].sort_values("retention")
        a.plot(g["sens_l2"], g["false_per_day"], color=color)
        a.plot([], [], color=color, marker=marker, markersize=3.5, label=label)  # legend: b, c
    r1 = t[np.isclose(t["retention"], 1.0)].iloc[0]
    a.plot(
        r1["sens_l2"],
        r1["false_per_day"],
        "o",
        color=INK,
        markersize=4.5,
        zorder=4,
        markeredgecolor=SURFACE,
        markeredgewidth=0.8,
    )
    a.annotate(
        "pre-registered\noperating point",
        xy=(r1["sens_l2"], r1["false_per_day"]),
        xytext=(r1["sens_l2"] - 0.07, r1["false_per_day"] + 0.03),
        ha="right",
        va="center",
        fontsize=6,
        color=INK,
        arrowprops={"arrowstyle": "-", "color": SECONDARY, "lw": 0.6},
    )
    percent_axis(a.xaxis)
    a.set_xlabel("Severe lows caught (level 2 sensitivity, held out)")
    a.set_ylabel("False alarms per day")
    a.set_ylim(0, None)
    a.set_title("a  Trade-off curves, default mix (A11)")
    a.legend(loc="upper left", borderaxespad=0.2)

    offsets = dict(zip(COMPARATORS, np.linspace(-0.0045, 0.0045, len(COMPARATORS)), strict=True))
    for ax, mix, title in (
        (b, "default", "b  Default mix (A13)"),
        (c, "high", "c  High mix (A13)"),
    ):
        m = a13[a13["mix"] == mix]
        for name, (_, color, marker) in COMPARATORS.items():
            g = m[(m["comparator"] == name) & m["total_ratio"].notna()]
            for unstable, part in g.groupby("unstable"):
                whiskers(
                    ax,
                    part["sens_l2"] + offsets[name],
                    part["total_ratio"],
                    part["total_ratio_lo"],
                    part["total_ratio_hi"],
                    color,
                    marker=marker,
                    filled=not unstable,
                )
        ax.axhline(1.0, color=AXIS, lw=0.8, zorder=1)
        sens = np.sort(m["sens_l2"].unique())
        ax.set_xticks(sens[::2])
        percent_axis(ax.xaxis)
        ax.set_xlim(sens[0] - 0.01, sens[-1] + 0.01)
        ax.set_title(title)
    b.set_yscale("log")
    log_ticks(b.yaxis, [0.75, 1.0, 1.25, 1.5])
    b.set_ylim(0.68, 1.75)
    c.tick_params(labelleft=False)
    c.text(
        0.97,
        0.97,
        "markers as in a\nhollow: unstable",
        transform=c.transAxes,
        ha="right",
        va="top",
        fontsize=6,
        color=SECONDARY,
    )
    b.set_xlabel("Matched severe-low sensitivity (held out)")
    b.xaxis.set_label_coords(1.05, -0.2)  # centred under b and c
    b.set_ylabel("False alarms, ratio to the\nretuned trend alarm (log)")
    save(fig, FIGURES, FIGURE_STEMS[3])


def fig5(summary: pd.DataFrame, real: pd.DataFrame) -> None:
    fig, (a, b) = plt.subplots(
        1, 2, figsize=(COLUMN_IN, 2.2), sharey=True, gridspec_kw={"wspace": 0.25}
    )
    sim = summary[summary["mix"] == "default"]
    for ax, d, title in ((a, sim, "a  Simulation"), (b, real, "b  Real CGM (Weinstock)")):
        for alarm, color, label in (("trend", BLUE, "Trend"), ("threshold", ORANGE, "Threshold")):
            g = d[d["alarm_name"] == alarm].sort_values("level")
            ax.fill_between(
                g["level"],
                g["false_compression_per_day_lo"],
                g["false_compression_per_day_hi"],
                color=color,
                alpha=BAND_ALPHA,
                lw=0,
            )
            ax.plot(
                g["level"],
                g["false_compression_per_day"],
                color=color,
                marker="o",
                label=label,
                markeredgecolor=SURFACE,
                markeredgewidth=0.6,
            )
        percent_axis(ax.xaxis)
        ax.set_xticks([0, 0.5, 1.0])
        ax.set_xlim(-0.05, 1.05)
        ax.set_title(title)
        ax.set_xlabel("Nights with a PISA")
    a.set_ylabel("Compression false alarms per day")
    a.set_ylim(0, None)
    a.legend(loc="upper left", borderaxespad=0.2)
    save(fig, FIGURES, FIGURE_STEMS[4])


def social_preview(summary: pd.DataFrame) -> None:
    """1280 x 640 px for GitHub (Settings > Social preview): name, scope and figure 1."""
    fig = plt.figure(figsize=(12.8, 6.4), dpi=100)
    fig.text(0.05, 0.78, "Ghost Lows", fontsize=46, fontweight="bold", color=INK)
    fig.text(
        0.05,
        0.66,
        "An open benchmark for real-time\nCGM low-glucose alarms\nunder sensor faults",
        fontsize=22,
        color=INK,
        va="top",
        linespacing=1.25,
    )
    fig.text(
        0.05,
        0.1,
        "Simulation: 30 virtual patients (UVA/Padova 2008).\n"
        "Research software, not a medical device.\n"
        "github.com/pkarakala/ghost-lows",
        fontsize=15,
        color=SECONDARY,
        linespacing=1.5,
    )
    ax = fig.add_axes((0.58, 0.16, 0.37, 0.6))
    causes_panel(ax, summary, fontsize=13)
    ax.tick_params(labelsize=13)
    ax.xaxis.label.set_size(14)
    ax.yaxis.label.set_size(14)
    ax.set_ylabel("False alarms per day, trend alarm")
    ax.legend(ncol=2, loc="lower left", bbox_to_anchor=(-0.02, 1.0), fontsize=12)
    SOCIAL.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(SOCIAL, dpi=100, metadata={"Software": None})
    plt.close(fig)


def main() -> None:
    use()
    summary = table(f"{MAIN}__summary.csv")
    fig1(summary)
    fig2(summary, table(f"{MAIN}__contrast_h1.csv"))
    fig3(table(f"{MAIN}__contrasts_h2.csv"), table("real__azt1d_contrasts_h2.csv"))
    fig4(table("curves__summary.csv"), table("curves__a13.csv"))
    fig5(summary, table("real__summary.csv"))
    social_preview(summary)
    print(f"wrote {len(FIGURE_STEMS)} figures to results/figures/ and {SOCIAL.relative_to(REPO)}")


if __name__ == "__main__":
    main()
