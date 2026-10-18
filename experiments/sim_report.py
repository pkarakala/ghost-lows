"""Summarise a simulated cohort: hypoglycaemia exposure, true-low counts, leak and lag (D3, D17).

    uv run python experiments/sim_report.py --config experiments/configs/sim_full.yaml

Prints Markdown tables (used in docs/SIMULATION_NOTES.md).
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from ghostlows.bench.events import is_night, leak_auc, true_events
from ghostlows.sim.run import SimConfig, load, run


def lag_minutes(samples: pd.DataFrame, events: pd.DataFrame) -> np.ndarray:
    """Minutes from each level-1 plasma onset to the first interstitial sample below 70."""
    keys = ["patient_id", "seed", "mix"]
    out = []
    grouped = {k: g for k, g in samples.groupby(keys, sort=False)}
    for _, ev in events[events["level"] == 1].iterrows():
        g = grouped[tuple(ev[k] for k in keys)]
        window = g[(g["time"] >= ev["onset"] - pd.Timedelta("30min")) & (g["time"] <= ev["end"])]
        below = window[window["isf_glucose"] < 70]
        if len(below):
            out.append((below["time"].iloc[0] - ev["onset"]) / pd.Timedelta("1min"))
    return np.asarray(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    config = SimConfig.load(args.config)
    out = run(config)
    data = load(out)
    samples, truth = data["samples"], data["truth"]
    runs = pd.read_csv(out / "runs.csv")
    events = true_events(truth)
    group = lambda pid: pid.split(":")[1].split("#")[0]  # noqa: E731

    print(
        f"Cohort `{config.name}` ({out.name}): {len(runs)} patient-runs, {config.days} days each.\n"
    )
    print(
        "| Mix | Runs outside model validity | Median TBR <70 (plasma) | Median TBR <54 | "
        "Level-1 events | Level-2 events | Nocturnal level-2 | Patients with no level-2 event | "
        "Leak AUC (IOB) | Leak AUC (COB) | Night share 70–95 mg/dL |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for mix in config.mixes:
        r = runs[runs["mix"] == mix]
        ev = events[events["mix"] == mix]
        s = samples[samples["mix"] == mix]
        l2 = ev[ev["level"] == 2]
        per_patient_l2 = (
            l2.groupby("patient_id").size().reindex(r["patient_id"].unique(), fill_value=0)
        )
        night = s[is_night(s["time"])]
        band = (
            ((night["truth_glucose"] >= 70) & (night["truth_glucose"] < 95))
            .groupby(night["patient_id"])
            .mean()
        )
        print(
            f"| {mix} | {int((~r['valid']).sum())} | {r['tbr70_truth_pct'].median():.1f}% | "
            f"{r['tbr54_truth_pct'].median():.1f}% | {int((ev['level'] == 1).sum())} | {len(l2)} | "
            f"{int(is_night(l2['onset']).sum())} | "
            f"{int((per_patient_l2 == 0).sum())} of {len(per_patient_l2)} | "
            f"{leak_auc(s, ev, 'iob'):.2f} | {leak_auc(s, ev, 'cob'):.2f} | {band.median():.0%} |"
        )

    print("\nLevel-2 events by age group (all mixes):\n")
    l2 = events[events["level"] == 2].assign(group=lambda d: d["patient_id"].map(group))
    table = l2.groupby(["mix", "group"]).size().unstack(fill_value=0)
    print("| Mix | " + " | ".join(table.columns) + " |")
    print("|---|" + "---|" * len(table.columns))
    for mix, row in table.iterrows():
        print(f"| {mix} | " + " | ".join(str(int(v)) for v in row) + " |")

    lags = lag_minutes(samples, events)
    print(
        "\nLag from plasma level-1 onset to interstitial glucose <70: "
        f"median {np.median(lags):.0f} min "
        f"(IQR {np.percentile(lags, 25):.0f}–{np.percentile(lags, 75):.0f}), n = {len(lags)}."
    )


if __name__ == "__main__":
    main()
