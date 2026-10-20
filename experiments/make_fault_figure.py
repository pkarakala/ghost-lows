"""Figure of example faults on a simulated patient: docs/figures/faults_examples.png (Phase 3).

    uv run python experiments/make_fault_figure.py

One 10-day run of adolescent#002 (standard meals, stock therapy). Each panel applies one fault
type alone at severity 1 (a PISA every night) and shows one instance; shading marks where the
fault is labelled active. Palette: first three categorical slots of the reference palette
(validated all-pairs, light mode); line style is the secondary encoding.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from ghostlows.faults.suite import FaultConfig, apply_faults  # noqa: E402
from ghostlows.sim.engine import Therapy, simulate  # noqa: E402
from ghostlows.sim.scenario import STANDARD, make_scenario  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "figures" / "faults_examples.png"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
TRUTH, OBSERVED, CLEAN = "#2a78d6", "#eb6834", "#1baf7a"
SHADE = "#d8d7d2"


def main() -> None:
    scenario = make_scenario(STANDARD, 10, meal_seed=31, perturb_seed=32)
    sim = simulate("adolescent#002", scenario, Therapy(), noise_seed=33)
    base = sim.samples.assign(seed=1, mix="standard")

    def only(kind: str):
        """Apply a single fault type, so each panel shows that fault alone."""
        config = FaultConfig(pisa_fraction=1.0, severity=1.0, enabled=frozenset({kind}))
        return apply_faults(base, config, seed=7)

    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "font.family": "sans-serif",
        }
    )
    fig, axes = plt.subplots(3, 2, figsize=(10, 9), facecolor=SURFACE)
    panels = [
        ("pisa", "Compression (PISA)"),
        ("dropout", "Dropout"),
        ("stale", "Stale readings"),
        ("spike", "Noise burst"),
    ]
    for ax, (kind, title) in zip(axes.flat[:4], panels, strict=True):
        samples, faults = only(kind)
        inst = faults[faults["fault_type"] == kind]
        if kind == "pisa":
            # the deepest artifact that starts while the clean CGM is in range, i.e. a false low
            at_onset = pd.merge_asof(
                inst.sort_values("start"),
                samples[["time", "glucose"]],
                left_on="start",
                right_on="time",
            )
            in_range = at_onset["glucose"].between(85, 130).to_numpy()
            inst = inst.sort_values("start")[in_range]
            inst = inst.loc[inst["size"].idxmax()]
        else:
            inst = inst.loc[(inst["end"] - inst["start"]).idxmax()]
        lo, hi = inst["start"] - pd.Timedelta("150min"), inst["end"] + pd.Timedelta("150min")
        w = samples[(samples["time"] >= lo) & (samples["time"] <= hi)]
        ax.axvspan(inst["start"], inst["end"], color=SHADE, lw=0)
        ax.plot(w["time"], w["truth_glucose"], color=TRUTH, lw=1.6, label="Plasma glucose (truth)")
        ax.plot(w["time"], w["glucose"], color=CLEAN, lw=1.6, ls=(0, (2, 1.5)), label="CGM, clean")
        ax.plot(w["time"], w["cgm_observed"], color=OBSERVED, lw=2.0, label="CGM, with fault")
        ax.axhline(70, color=MUTED, lw=0.8, ls=(0, (4, 3)))
        ax.text(w["time"].iloc[0], 71, "70 mg/dL", color=MUTED, fontsize=8, va="bottom")
        ax.set_title(title, loc="left", color=INK, fontsize=10)
        ax.set_ylabel("mg/dL")
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M"))

    ax = axes.flat[4]
    samples, faults = only("drift")
    raw = samples["isf_glucose"] + samples["cgm_noise"]
    in_range = raw.between(40, 400) & samples["cgm_observed"].between(40, 400, inclusive="neither")
    ratio = (samples["cgm_observed"] / raw).where(in_range)
    days = (samples["time"] - samples["time"].iloc[0]) / pd.Timedelta("1D")
    drift = faults[faults["fault_type"] == "drift"]
    for _, d in drift.iterrows():
        ax.axvline(
            (d["start"] - samples["time"].iloc[0]) / pd.Timedelta("1D"),
            color=MUTED,
            lw=0.8,
            ls=(0, (4, 3)),
        )
    ax.plot(days, ratio, color=OBSERVED, lw=2.0)
    ax.axhline(1, color=MUTED, lw=0.8)
    ax.set_title(
        "Sensor drift (observed / clean CGM, in-range readings)", loc="left", color=INK, fontsize=10
    )
    ax.set_xlabel("days of wear")
    ax.set_ylabel("ratio")

    legend_ax = axes.flat[5]
    legend_ax.axis("off")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    handles.append(plt.Rectangle((0, 0), 1, 1, color=SHADE))
    labels.append("Fault labelled active")
    legend_ax.legend(handles, labels, loc="upper left", frameon=False, fontsize=9)
    legend_ax.text(
        0.0,
        0.35,
        "Simulated adolescent#002; one fault type per panel, severity 1.\n"
        "PISA: first-order response to a rectangular input [Facchinetti 2016],\n"
        "tau = 10 min (assumption). Faults never change the truth.",
        color=MUTED,
        fontsize=8,
        va="top",
        transform=legend_ax.transAxes,
    )

    for ax in axes.flat[:5]:
        ax.set_facecolor(SURFACE)
        ax.grid(color=GRID, lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150, facecolor=SURFACE)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
