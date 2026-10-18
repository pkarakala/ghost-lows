"""Write the synthetic sample behind the upload app's "Try it with sample data" button.

    uv run python scripts/make_sample_export.py                   # app/sample_clarity_export.csv
    uv run python scripts/make_sample_export.py --survey <cohort> # the selection rule on a cohort

`--survey` also writes results/tables/flag_survey.json, the flag performance the app quotes.

The export is fully synthetic. One virtual patient of simglucose (the UVA/Padova 2008 model) is
simulated for 14 days exactly as in the benchmark cohort (`sim_full.yaml`). The benchmark's fault
suite is then applied as in its PISA sweep at the 25% level (other faults moderate, fault seed 0).
No real person's data is used. `app/sample_answer_key.json` records what really happened: the
injected compression artifacts, the real lows and the true (plasma) glucose. The app uses it to
show which flags fall on an injected artifact.

The run is the first, in the benchmark's order (seed, then patient), that shows each kind of
event the report explains (`conditions`):
- at least two nights with an injected compression artifact that the report flags, at least one
  of them a ghost low (the faulted CGM goes below 70 mg/dL while the fault-free CGM does not);
- at least one real nocturnal low (plasma glucose below 70 mg/dL for 15 min or more, starting at
  night) that shows on the CGM, is not flagged and does not overlap an injected artifact.
There is no condition on the report's other flags, so they appear as they come. `--survey`
applies the rule to every run of a simulated cohort and summarises how the flags do.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ghostlows import io as gio  # noqa: E402
from ghostlows import retro  # noqa: E402
from ghostlows.bench.events import EVENT_MIN, LEVEL_THRESHOLDS, is_night, true_events  # noqa: E402
from ghostlows.bench.pipeline import BenchConfig  # noqa: E402
from ghostlows.faults import apply_faults  # noqa: E402
from ghostlows.io.clarity import EXPORT_COLUMNS  # noqa: E402

APP = REPO / "app"
SAMPLE_CSV = APP / "sample_clarity_export.csv"
ANSWER_KEY = APP / "sample_answer_key.json"
SURVEY = REPO / "results" / "tables" / "flag_survey.json"
SIM_CONFIG = "experiments/configs/sim_full.yaml"
BENCH_CONFIG = "experiments/configs/rq1_pisa_sweep.yaml"

# ASSUMPTION: the first run that meets the conditions in the docstring (found with --survey)
PATIENT, SEED, MIX = "adult#006", 1, "default"
# ASSUMPTION: a level of the benchmark's PISA sweep with a few compressed nights (about 3 of 13),
# so the sample report stays readable
PISA_LEVEL = 0.25
# ASSUMPTION: what the sample must show (docstring)
MIN_FLAGGED_ARTIFACTS, MIN_GHOST_LOWS, MIN_REAL_LOWS = 2, 1, 1
LOW = LEVEL_THRESHOLDS[1]
VISIBLE_READINGS = EVENT_MIN // 5  # a low "shows on the CGM": 15 min of 5-min readings below 70
DEVICE = "synthetic"


def stamp(t) -> str:
    return pd.Timestamp(t).strftime("%Y-%m-%dT%H:%M:%S")


def clarity_csv(observed: pd.DataFrame, events: pd.DataFrame, patient: str) -> str:
    """The faulted CGM and the logged boluses and carbs as a Dexcom Clarity CSV export. Rescue
    carbs are not logged, as in the benchmark; readings lost to dropout have no row."""
    ts, et = "Timestamp (YYYY-MM-DDThh:mm:ss)", "Event Type"
    rows = []

    def add(**cells):
        row = [""] * len(EXPORT_COLUMNS)
        for key, value in cells.items():
            row[EXPORT_COLUMNS.index(key)] = str(value)
        rows.append(row)

    add(**{et: "FirstName", "Patient Info": "SYNTHETIC"})
    add(**{et: "LastName", "Patient Info": "SAMPLE - simulated data, not a real person"})
    add(
        **{
            et: "Device",
            "Device Info": f"Simulated CGM: Ghost Lows synthetic sample (simglucose virtual "
            f"patient {patient} with injected sensor faults)",
            "Source Device ID": DEVICE,
        }
    )
    shown = observed[observed["cgm_observed_flag"] != "missing"]
    for t, value, flag in zip(
        shown["time"], shown["cgm_observed"], shown["cgm_observed_flag"], strict=True
    ):
        text = {"below_range": "Low", "above_range": "High"}.get(flag, f"{value:.0f}")
        add(**{ts: stamp(t), et: "EGV", "Source Device ID": DEVICE, "Glucose Value (mg/dL)": text})
    for _, e in events[events["kind"] == "bolus"].iterrows():
        add(
            **{
                ts: stamp(e["time"]),
                et: "Insulin",
                "Event Subtype": "Fast-Acting",
                "Source Device ID": DEVICE,
                "Insulin Value (u)": f"{e['value']:.1f}",
            }
        )
    for _, e in events[events["kind"] == "carbs_announced"].iterrows():
        add(
            **{
                ts: stamp(e["time"]),
                et: "Carbs",
                "Source Device ID": DEVICE,
                "Carb Value (grams)": f"{e['value']:.0f}",
            }
        )
    rows.sort(key=lambda r: (r[1] != "", r[1]))  # metadata first, then time order
    for i, row in enumerate(rows, 1):
        row[0] = str(i)
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows([EXPORT_COLUMNS, *rows])
    return buffer.getvalue()


def answer_key(observed, faults, truth, config_meta) -> dict:
    """What really happened: injected artifacts, real lows (level 1, from 1-min plasma glucose)
    and the true glucose every 5 min."""
    artifacts = []
    pisas = faults[faults["fault_type"] == "pisa"] if len(faults) else pd.DataFrame()
    for _, p in pisas.iterrows():
        seg = observed[(observed["time"] >= p["start"]) & (observed["time"] <= p["end"])]
        ghost = (seg["cgm_observed"] < LOW).any() and (seg["glucose"] >= LOW).all()
        artifacts.append(
            {
                "start": stamp(p["start"].floor("min")),
                "end": stamp(p["end"].ceil("min")),
                "depth_mg_dl": round(float(p["size"]), 1),
                "ghost_low": bool(ghost),
            }
        )
    lows = []
    events = true_events(truth.assign(patient_id="sample"), levels=(1,))
    for _, e in events.iterrows():
        tr = truth[(truth["time"] >= e["onset"]) & (truth["time"] < e["end"])]
        lows.append(
            {
                "start": stamp(e["onset"]),
                "end": stamp(e["end"]),
                "night": bool(is_night(pd.Series([e["onset"]]))[0]),
                "lowest_true_mg_dl": round(float(tr["truth_glucose"].min()), 1),
            }
        )
    true_5min = truth.set_index("time")["truth_glucose"].resample("5min").first()
    return {
        "about": "What really happened in sample_clarity_export.csv, a synthetic export written by "
        "scripts/make_sample_export.py. Times are local clock times, as in the file.",
        **config_meta,
        "artifacts": artifacts,
        "real_lows": lows,
        "true_glucose": {
            "start": stamp(true_5min.index[0]),
            "step_min": 5,
            "mg_dl": [round(float(v)) for v in true_5min],
        },
    }


def overlaps(start, end, frame: pd.DataFrame) -> np.ndarray:
    if frame.empty:
        return np.zeros(0, bool)
    return ((frame["start"] <= end) & (frame["end"] >= start)).to_numpy()


def conditions(key: dict, data: pd.DataFrame, flags: pd.DataFrame) -> dict:
    """Counts behind the sample conditions, from the answer key and what the app computes on the
    export (`data` loaded as the app loads it, `flags` as the app flags it)."""
    arts = pd.DataFrame(key["artifacts"], columns=["start", "end", "depth_mg_dl", "ghost_low"])
    arts[["start", "end"]] = arts[["start", "end"]].apply(pd.to_datetime)
    flagged = np.array([overlaps(a.start, a.end, flags).any() for a in arts.itertuples()], bool)
    readings = data[data["glucose"].notna()]
    real_ok = 0
    for low in key["real_lows"]:
        start, end = pd.Timestamp(low["start"]), pd.Timestamp(low["end"])
        cgm = readings[(readings["time"] >= start) & (readings["time"] < end)]["glucose"]
        real_ok += bool(
            low["night"]
            and (cgm < LOW).sum() >= VISIBLE_READINGS
            and not overlaps(start, end, flags).any()
            and not overlaps(start, end, arts).any()
        )
    on_artifact = [overlaps(f.start, f.end, arts).any() for f in flags.itertuples()]
    real = pd.DataFrame(key["real_lows"], columns=["start", "end"]).apply(pd.to_datetime)
    on_real_low = [overlaps(f.start, f.end, real).any() for f in flags.itertuples()]
    return {
        "artifacts": len(arts),
        "flagged_artifacts": int(flagged.sum()),
        "flagged_ghost_lows": int((flagged & arts["ghost_low"].to_numpy(bool)).sum()),
        "unflagged_real_night_lows": real_ok,
        "flags": len(flags),
        "flags_elsewhere": int(len(flags) - sum(on_artifact)),
        "flags_on_real_lows": int(sum(on_real_low)),
    }


def meets(counts: dict) -> bool:
    return (
        counts["flagged_artifacts"] >= MIN_FLAGGED_ARTIFACTS
        and counts["flagged_ghost_lows"] >= MIN_GHOST_LOWS
        and counts["unflagged_real_night_lows"] >= MIN_REAL_LOWS
    )


def build(samples, truth, events, patient, seed, mix, bench) -> tuple[str, dict, dict]:
    """The export, its answer key and the condition counts for one simulated run."""
    run = samples.assign(seed=seed, mix=mix).sort_values("time").reset_index(drop=True)
    observed, faults = apply_faults(run, bench.fault_config(PISA_LEVEL), seed=bench.fault_seed)
    text = clarity_csv(observed, events, patient)
    meta = {
        "simulation": {"patient": patient, "seed": seed, "mix": mix, "config": SIM_CONFIG},
        "faults": {
            "pisa_fraction": PISA_LEVEL,
            "severity": bench.severity,
            "fault_seed": bench.fault_seed,
            "injected": faults["fault_type"].value_counts().sort_index().to_dict()
            if len(faults)
            else {},
        },
    }
    key = answer_key(observed, faults, truth, meta)
    data = gio.load_export(text.encode())
    counts = conditions(key, data, retro.flag_possible_artifacts(data))
    return text, key, counts


def survey(cohort: Path, bench: BenchConfig) -> int:
    """The conditions on every default-mix run of a simulated cohort, in the benchmark's order."""
    from ghostlows.sim.engine import PATIENTS
    from ghostlows.sim.run import part_name

    rows = []
    for seed in (1, 2, 3, 4, 5):
        for patient in PATIENTS:
            name = part_name(patient, seed, MIX)
            parts = {k: pd.read_parquet(cohort / k / name) for k in ("samples", "truth", "events")}
            samples = parts["samples"].drop(columns=["seed", "mix"], errors="ignore")
            _, _, counts = build(
                samples, parts["truth"], parts["events"], patient, seed, MIX, bench
            )
            rows.append({"seed": seed, "patient": patient, **counts, "meets": meets(counts)})
    table = pd.DataFrame(rows)
    first = table[table["meets"]].head(1)
    print(table[table["meets"]].to_string(index=False))
    print(f"\n{int(table['meets'].sum())} of {len(table)} runs meet the conditions; first:")
    print(first[["seed", "patient"]].to_string(index=False))
    n_art = table["artifacts"].sum()
    print(
        f"all runs: {n_art} injected artifacts, {table['flagged_artifacts'].sum() / n_art:.0%} "
        f"flagged; flags elsewhere per run: mean {table['flags_elsewhere'].mean():.2f}, median "
        f"{table['flags_elsewhere'].median():.0f}; flags on real lows per run: mean "
        f"{table['flags_on_real_lows'].mean():.2f} ({(table['flags_on_real_lows'] > 0).mean():.0%}"
        " of runs have one)"
    )
    # the flag performance the app quotes next to the flags (amendment A12)
    on_real = table["flags_on_real_lows"] > 0
    record = {
        "about": "How the upload report's flags do on simulated data: make_sample_export.py "
        "--survey on every default-mix run of the benchmark cohort, faults as in the PISA sweep.",
        "cohort": cohort.name,
        "mix": MIX,
        "pisa_fraction": PISA_LEVEL,
        "severity": bench.severity,
        "fault_seed": bench.fault_seed,
        "runs": len(table),
        "injected_artifacts": int(n_art),
        "flagged_artifacts": int(table["flagged_artifacts"].sum()),
        "flagged_artifact_share": round(float(table["flagged_artifacts"].sum() / n_art), 3),
        "flags_elsewhere_per_run_mean": round(float(table["flags_elsewhere"].mean()), 2),
        "flags_elsewhere_per_run_median": float(table["flags_elsewhere"].median()),
        "runs_with_a_flag_on_a_real_low": int(on_real.sum()),
        "share_of_runs_with_a_flag_on_a_real_low": round(float(on_real.mean()), 3),
    }
    SURVEY.write_text(json.dumps(record, indent=1) + "\n")
    print(f"wrote {SURVEY.relative_to(REPO)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--survey", type=Path, help="a simulated cohort folder (data/sim/...)")
    args = parser.parse_args()
    bench = BenchConfig.load(REPO / BENCH_CONFIG)
    if args.survey:
        return survey(args.survey, bench)

    from ghostlows.sim.run import SimConfig, simulate_run

    result = simulate_run(SimConfig.load(REPO / SIM_CONFIG), PATIENT, SEED, MIX)
    text, key, counts = build(
        result.samples, result.truth, result.events, PATIENT, SEED, MIX, bench
    )
    print(counts)
    if not meets(counts):
        print("the run no longer meets the sample conditions; rerun --survey to choose another")
        return 1
    SAMPLE_CSV.write_text(text)
    ANSWER_KEY.write_text(json.dumps(key, indent=1) + "\n")
    print(f"wrote {SAMPLE_CSV.relative_to(REPO)} and {ANSWER_KEY.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
