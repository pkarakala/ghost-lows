"""Real-data track (ROADMAP phase 7, D16): semi-synthetic PISAs in real nights, and face validity.

    uv run python experiments/real_data.py

1. Semi-synthetic RQ1 (co-primary): PISAs from the same Facchinetti model are injected at stable
   night stretches of real CGM (Weinstock 2016 via GlucoBench). The un-injected CGM is the
   reference: its lows are the "true" lows, and false alarms caused by injected artifacts are
   attributable exactly. Real, unlabelled PISAs already in the reference bias sensitivity.
2. Face validity: simulated nocturnal lows and overnight glucose against the same real CGM.
3. H3 (AZT1D, D6, D9): the H2 contrast on semi-synthetic AZT1D nights, with IOB and COB built
   from user-entered boluses and carbs only (automatic boluses and basal respond to the CGM),
   and the realised leak AUC next to the simulated mixes' (D3).

    uv run python experiments/real_data.py --dataset azt1d   # or weinstock (default: both)

Writes results/real/ (gitignored) and copies tables and figures to results/tables and
results/figures.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ghostlows.alarms import DETECTORS, benchmark_alarms, stretch_alarms  # noqa: E402
from ghostlows.alarms.base import minutes  # noqa: E402
from ghostlows.bench.analysis import context_contrasts  # noqa: E402
from ghostlows.bench.events import (
    EVENT_MIN,
    LEVEL_THRESHOLDS,
    detect_events,
    is_night,
    leak_auc,
    low_labels,
)  # noqa: E402
from ghostlows.bench.pipeline import (  # noqa: E402
    alarm_frame,
    fire_and_score,
    is_learned,
    summarise,
    training_threshold,
)
from ghostlows.bench.scoring import Windows, fda_rates, per_run_metrics, run_hours  # noqa: E402
from ghostlows.bench.stats import patient_folds  # noqa: E402
from ghostlows.faults.suite import inject_real  # noqa: E402
from ghostlows.io import load_azt1d, load_glucobench  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "real"
ALARMS = [
    "floor_only",
    "threshold",
    "trend",
    "baysal_gate",
    "matched_filter_causal_gate",
    "iforest_causal_gate",
    "gbm",
    "gbm_time",
    "kalman_pisa_cgm",  # RQ3: does the model-based filter hold up on real CGM? (amendment A3)
]
# H3: the H2 arms (CGM + time vs. CGM + time + IOB/COB) for every detector, plus the trend
# reference and the Kalman filter with and without inputs (RQ3)
H3_ALARMS = [
    "floor_only",
    "trend",
    *[f"{d}_combined{arm}" for d in DETECTORS for arm in ("_time", "_time_ctx")],
    "gbm_time",
    "gbm_time_ctx",
    "kalman_pisa",
    "kalman_pisa_cgm",
]
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SIM_COLOR, REAL_COLOR = "#2a78d6", "#eb6834"


def to_grid(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Regular 5-min grid per patient (gaps as NaN), with the run keys the scorer expects."""
    out = []
    for pid, g in df[df["glucose"].notna()].groupby("patient_id"):
        t0 = g["time"].iloc[0]
        slot = ((g["time"] - t0) / pd.Timedelta("5min")).round().astype(int)
        g = g.assign(slot=slot).drop_duplicates("slot")
        full = pd.DataFrame({"slot": np.arange(slot.max() + 1)})
        g = full.merge(g[["slot", "glucose"]], on="slot", how="left")
        g["time"] = t0 + pd.to_timedelta(g["slot"] * 5, unit="min")
        out.append(g.assign(patient_id=pid, seed=0, mix=source).drop(columns="slot"))
    grid = pd.concat(out, ignore_index=True)
    grid["time"] = grid["time"].astype("datetime64[ns]")
    return grid


def reference_events(grid: pd.DataFrame) -> pd.DataFrame:
    """CGM-referenced lows (D11): >= 15 min below threshold on the un-injected CGM."""
    rows = []
    for key, g in grid.groupby(["patient_id", "seed", "mix"], sort=False):
        times = g["time"].to_numpy()
        for level, thr in LEVEL_THRESHOLDS.items():
            for s, e in detect_events(g["glucose"].to_numpy(float), thr, step_min=5):
                end = times[e] if e < len(times) else times[-1] + np.timedelta64(5, "m")
                rows.append(
                    {
                        "patient_id": key[0],
                        "seed": key[1],
                        "mix": key[2],
                        "level": level,
                        "onset": times[s],
                        "end": end,
                    }
                )
    return pd.DataFrame(rows).astype({"onset": "datetime64[ns]", "end": "datetime64[ns]"})


def inject(grid: pd.DataFrame, per_night: float, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    outs, faults = [], []
    for i, (pid, g) in enumerate(grid.groupby("patient_id", sort=True)):
        if per_night > 0:
            o, f = inject_real(g, per_night, seed=seed * 100_003 + i)
        else:
            o, f = g.assign(cgm_observed=g["glucose"], fault_type="none"), pd.DataFrame()
        outs.append(o)
        if len(f):
            faults.append(f.assign(patient_id=pid, seed=0, mix=g["mix"].iloc[0]))
    return pd.concat(outs, ignore_index=True), (
        pd.concat(faults, ignore_index=True) if faults else pd.DataFrame()
    )


def semi_synthetic(grid, events, levels, windows, seed=0, n_folds=2, n_boot=2000, names=None):
    """Frozen alarms (fitted on the training folds at per-night 0.5) evaluated across levels."""
    names = ALARMS if names is None else names
    alarms_all = [a for a in benchmark_alarms(seed=0) + stretch_alarms() if a.name in names]
    folds = patient_folds(grid["patient_id"].unique(), n_folds, seed)
    train_obs, train_faults = inject(grid, 0.5, seed)
    train_obs["label"] = low_labels(train_obs, events)
    import copy

    fitted = {}
    for fold in sorted(set(folds.values())):
        ids = [p for p, f in folds.items() if f != fold]
        tr = train_obs[train_obs["patient_id"].isin(ids)]
        tr_ev = events[events["patient_id"].isin(ids)]
        tr_f = (
            train_faults[train_faults["patient_id"].isin(ids)]
            if len(train_faults)
            else train_faults
        )
        from ghostlows.bench.pipeline import reference_sensitivity

        # A5: on CGM-referenced lows the ungated floor catches every level 2 low by
        # construction, so the operating point matches level 1 sensitivity instead
        ref = reference_sensitivity(tr, tr_ev, tr_f, windows, level=1)
        entries = []
        for alarm in copy.deepcopy(alarms_all):
            threshold = alarm.default_threshold
            if is_learned(alarm):
                alarm.fit(alarm_frame(tr, alarm, with_label=True))
                threshold, _ = training_threshold(
                    alarm, alarm_frame(tr, alarm), tr, tr_ev, tr_f, ref, 0.0, windows, level=1
                )
            entries.append((alarm, threshold))
        fitted[fold] = entries
    metrics = []
    for level in levels:
        observed, faults = inject(grid, level, seed + 1)
        for fold, entries in fitted.items():
            ids = [p for p, f in folds.items() if f == fold]
            te = observed[observed["patient_id"].isin(ids)]
            te_ev = events[events["patient_id"].isin(ids)]
            te_f = faults[faults["patient_id"].isin(ids)] if len(faults) else faults
            ref_truth = te[["patient_id", "seed", "mix", "time", "glucose"]].rename(
                columns={"glucose": "truth_glucose"}
            )
            for alarm, threshold in entries:
                fired, cls, scored = fire_and_score(
                    alarm, alarm_frame(te, alarm), threshold, te_ev, te_f, te, windows
                )
                m = per_run_metrics(cls, scored, run_hours(te), [alarm.name])
                fda = fda_rates(fired, ref_truth.dropna(), windows=windows)
                if len(fda):
                    m = m.merge(fda, on=["patient_id", "seed", "mix", "alarm_name"], how="left")
                metrics.append(m.assign(level=level, pisa_fraction=level, fold=fold))
    metrics = pd.concat(metrics, ignore_index=True)
    return metrics, summarise(metrics, n_boot)


def azt1d_grid() -> pd.DataFrame:
    """AZT1D on the 5-min grid with IOB and COB from user-entered boluses and carbs only (D9)."""
    from ghostlows.sim.context import cob, iob

    raw = load_azt1d()
    grid = to_grid(raw, "azt1d")
    parts = []
    for pid, g in grid.groupby("patient_id", sort=False):
        r = raw[raw["patient_id"] == pid]
        b, c = r[r["insulin_bolus"] > 0], r[r["carbs"] > 0]
        q = minutes(g["time"])
        parts.append(
            g.assign(
                iob=iob(minutes(b["time"]), b["insulin_bolus"].to_numpy(), q),
                cob=cob(minutes(c["time"]), c["carbs"].to_numpy(), q),
            )
        )
    return pd.concat(parts, ignore_index=True)


def run_azt1d(args, windows) -> dict:
    """H3 on semi-synthetic AZT1D nights (5 leave-patients-out folds), and the leak AUC (D3)."""
    grid = azt1d_grid()
    events = reference_events(grid)
    metrics, summary = semi_synthetic(
        grid, events, args.levels, windows, n_folds=5, n_boot=args.n_boot, names=H3_ALARMS
    )
    contrasts = context_contrasts(metrics, n_boot=args.n_boot)
    for name, frame in (("metrics", metrics), ("summary", summary), ("contrasts_h2", contrasts)):
        frame.to_csv(OUT / f"azt1d_{name}.csv", index=False)
    meta = {
        "dataset": "AZT1D 2025 (Mendeley gk9m674wcx v1): adults with type 1 diabetes on Control-IQ, Dexcom G6",
        "patients": int(grid["patient_id"].nunique()),
        "days": float(run_hours(grid.assign(cgm_observed=grid["glucose"]))["hours"].sum() / 24),
        "reference_l1_events": int((events["level"] == 1).sum()),
        "reference_l2_events": int((events["level"] == 2).sum()),
        "leak_auc_iob": leak_auc(grid, events, "iob"),
        "leak_auc_cob": leak_auc(grid, events, "cob"),
        "context": "IOB and COB from user-entered boluses and carbs only; automatic boluses and basal "
        "respond to the CGM and are left out (D9)",
        "labelled": "Nothing is labelled as PISA. Injected PISAs are known exactly; real compression "
        "artifacts in the reference count as true lows, and Control-IQ already suspended insulin for "
        "some of them, which the reference cannot show.",
    }
    (OUT / "azt1d_meta.json").write_text(json.dumps(meta, indent=2, default=float) + "\n")
    print(contrasts.round(3).to_string(index=False))
    return meta


def low_shapes(frame: pd.DataFrame, value: str, source: str) -> pd.DataFrame:
    """Nocturnal level 1 lows on a 5-min CGM column: fall rate before onset, nadir, duration."""
    rows = []
    for key, g in frame.groupby(["patient_id", "seed", "mix"], sort=False):
        y, t = g[value].to_numpy(float), g["time"].to_numpy()
        for s, e in detect_events(y, LEVEL_THRESHOLDS[1], step_min=5):
            if not is_night(pd.Series([t[s]]))[0] or s < 6:
                continue
            fall = (y[s] - y[s - 6]) / 30.0  # mg/dL/min over the 30 min before onset
            seg = y[s:e]
            rows.append(
                {
                    "source": source,
                    "patient_id": key[0],
                    "fall_rate": fall,
                    "nadir": np.nanmin(seg),
                    "duration_min": (e - s) * 5.0,
                }
            )
    return pd.DataFrame(rows)


def night_band(frame: pd.DataFrame, value: str, source: str) -> pd.DataFrame:
    night = frame[is_night(frame["time"])]
    v = night[value]
    share = ((v >= 70) & (v < 95)).groupby(night["patient_id"]).mean()
    tbr = (frame[value] < 70).groupby(frame["patient_id"]).mean()
    return pd.DataFrame(
        {"source": source, "night_70_95": share, "tbr70": tbr.reindex(share.index)}
    ).reset_index()


def face_validity(sim_samples: pd.DataFrame, real_grid: pd.DataFrame, out: Path) -> pd.DataFrame:
    sim = sim_samples[sim_samples["mix"] == "default"].rename(columns={"glucose": "cgm"})
    real = real_grid.rename(columns={"glucose": "cgm"})
    shapes = pd.concat(
        [
            low_shapes(sim, "cgm", "simulated (default mix)"),
            low_shapes(real, "cgm", "Weinstock 2016"),
        ]
    )
    band = pd.concat(
        [
            night_band(sim, "cgm", "simulated (default mix)"),
            night_band(real, "cgm", "Weinstock 2016"),
        ]
    )
    fig, axes = plt.subplots(1, 4, figsize=(15, 3.6), facecolor=SURFACE)
    panels = [
        (shapes, "fall_rate", "CGM fall rate in the 30 min before a nocturnal low (mg/dL/min)"),
        (shapes, "nadir", "Nadir of nocturnal lows (mg/dL)"),
        (shapes, "duration_min", "Duration of nocturnal lows (min)"),
        (band, "night_70_95", "Share of the night at 70-95 mg/dL, per person"),
    ]
    for ax, (data, col, title) in zip(axes, panels, strict=True):
        for source, color in (
            ("simulated (default mix)", SIM_COLOR),
            ("Weinstock 2016", REAL_COLOR),
        ):
            v = np.sort(data.loc[data["source"] == source, col].dropna().to_numpy())
            if v.size:
                ax.plot(
                    v,
                    np.arange(1, v.size + 1) / v.size,
                    color=color,
                    lw=2,
                    label=f"{source} (n={v.size})",
                )
        ax.set_title(title, loc="left", fontsize=8.5, color=INK)
        ax.set_facecolor(SURFACE)
        ax.grid(color=GRID, lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylabel("cumulative share", fontsize=8)
    axes[0].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(out / f"face_validity.{ext}", dpi=150, facecolor=SURFACE)
    plt.close(fig)
    summary = pd.concat(
        [
            shapes.groupby("source")[["fall_rate", "nadir", "duration_min"]].median(),
            band.groupby("source")[["night_70_95", "tbr70"]].median(),
            shapes.groupby("source").size().rename("nocturnal_lows"),
        ],
        axis=1,
    )
    return summary.reset_index()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--levels", nargs="*", type=float, default=[0.0, 0.5, 1.0])
    parser.add_argument("--n-boot", type=int, default=2000)
    parser.add_argument("--sim-config", default="experiments/configs/sim_full.yaml")
    parser.add_argument(
        "--face-only", action="store_true", help="only redo the face-validity check"
    )
    parser.add_argument("--dataset", choices=["weinstock", "azt1d", "all"], default="all")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    tables, figures = REPO / "results" / "tables", REPO / "results" / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    if args.dataset in ("azt1d", "all") and not args.face_only:
        print(json.dumps(run_azt1d(args, Windows()), indent=2, default=float))
        for name in ("azt1d_summary.csv", "azt1d_contrasts_h2.csv", "azt1d_meta.json"):
            shutil.copy(OUT / name, tables / f"real__{name}")
    if args.dataset == "azt1d":
        return
    real = to_grid(load_glucobench("weinstock"), "weinstock")
    events = reference_events(real)
    windows = Windows()
    if args.face_only:
        summary = pd.read_csv(OUT / "summary.csv")
    else:
        metrics, summary = semi_synthetic(real, events, args.levels, windows, n_boot=args.n_boot)
        metrics.to_csv(OUT / "metrics.csv", index=False)
        summary.to_csv(OUT / "summary.csv", index=False)
    meta = {
        "dataset": "Weinstock 2016 via GlucoBench (Dexcom G4, older adults, case-control for severe hypoglycaemia)",
        "patients": int(real["patient_id"].nunique()),
        "days": float(run_hours(real.assign(cgm_observed=real["glucose"]))["hours"].sum() / 24),
        "reference_l1_events": int((events["level"] == 1).sum()),
        "reference_l2_events": int((events["level"] == 2).sum()),
        "event_rule_min": EVENT_MIN,
        "labelled": "Nothing is labelled as PISA in the real data. Injected PISAs are known exactly; "
        "real compression artifacts in the reference are not, so they count as true lows.",
    }
    try:
        from ghostlows.sim.run import SimConfig, load

        cfg = SimConfig.load(REPO / args.sim_config)
        if (cfg.out_dir() / "meta.json").exists():
            fv = face_validity(load(cfg.out_dir())["samples"], real, OUT)
            fv.to_csv(OUT / "face_validity.csv", index=False)
            meta["face_validity"] = "results/tables/real__face_validity.csv"
        else:
            meta["face_validity"] = f"not run: {cfg.name} cohort not simulated yet"
    except Exception as exc:  # pragma: no cover - reported, not hidden
        meta["face_validity"] = f"not run: {exc}"
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    for name in ("summary.csv", "face_validity.csv", "meta.json"):
        if (OUT / name).exists():
            shutil.copy(OUT / name, tables / f"real__{name}")
    if (OUT / "face_validity.png").exists():
        shutil.copy(OUT / "face_validity.png", figures / "real__face_validity.png")
    print(
        summary[["alarm_name", "level", "sens_l1", "false_per_day", "false_compression_per_day"]]
        .round(3)
        .to_string(index=False)
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
