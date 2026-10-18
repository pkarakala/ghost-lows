"""Per-patient therapy calibration on the standard scenario (D17, SIMULATION.md §2).

For each virtual patient, find the bolus scale k (carb ratio and correction factor are
multiplied by k, so k > 1 means smaller boluses) closest to the stock value k = 1 such that, over
14 days of standard meals on calibration seeds, plasma TBR <70 lies in the target band and plasma
never falls below the nadir floor.

    uv run python -m ghostlows.sim.calibrate --out experiments/configs/calibration_v1.yaml
"""

from __future__ import annotations

import argparse
import math
import subprocess
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from importlib.metadata import version

import numpy as np
import pandas as pd
import yaml

from .engine import PATIENTS, Therapy, simulate
from .run import git_commit, task_seeds
from .scenario import STANDARD, make_scenario

# ASSUMPTION: plausible open-loop exposure; lows deeper than the floor are outside the 2008
# model's credible range (CLINICAL-REVIEW: CR15)
TBR_BAND_PCT = (1.0, 8.0)
NADIR_FLOOR = 40.0
CALIBRATION_SEED = 9001  # disjoint from benchmark seeds
DAYS = 14
# ASSUMPTION: at most 30% more insulin than stock, at most 4x less
K_MIN, K_MAX = 0.7, 4.0
ITERATIONS = 5


def evaluate(patient: str, k: float, days: int = DAYS, seed: int = CALIBRATION_SEED) -> dict:
    meal_seed, perturb_seed, noise_seed = task_seeds(seed, patient)
    scenario = make_scenario(STANDARD, days, meal_seed, perturb_seed)
    result = simulate(patient, scenario, Therapy(bolus_scale=k), noise_seed)
    plasma = result.truth["truth_glucose"].to_numpy()
    return {
        "bolus_scale": round(k, 4),
        "tbr70_pct": round(100 * float(np.mean(plasma < 70)), 3),
        "tbr54_pct": round(100 * float(np.mean(plasma < 54)), 3),
        "nadir": round(float(plasma.min()), 2),
    }


def calibrate_patient(patient: str, days: int = DAYS, seed: int = CALIBRATION_SEED) -> dict:
    evals: dict[float, dict] = {}

    def f(k: float) -> dict:
        if k not in evals:
            evals[k] = evaluate(patient, k, days, seed)
        return evals[k]

    lo_band, hi_band = TBR_BAND_PCT
    safe = lambda r: r["tbr70_pct"] <= hi_band and r["nadir"] >= NADIR_FLOOR  # noqa: E731
    enough = lambda r: r["tbr70_pct"] >= lo_band  # noqa: E731

    stock = f(1.0)
    if safe(stock) and enough(stock):
        k, status = 1.0, "stock"
    elif not safe(stock):
        # Too many or too deep lows: smallest k > 1 that is safe (bisection in log space).
        lo, hi = 1.0, K_MAX
        if not safe(f(hi)):
            k, status = hi, "infeasible"
        else:
            for _ in range(ITERATIONS):
                mid = math.sqrt(lo * hi)
                lo, hi = (lo, mid) if safe(f(mid)) else (mid, hi)
            k, status = hi, "reduced"
    else:
        # Too few lows: largest k < 1 with enough lows that stays safe.
        lo, hi = K_MIN, 1.0
        if not (enough(f(lo)) and safe(f(lo))):
            k, status = (lo, "increased-limit") if safe(f(lo)) else (1.0, "stock-few-lows")
        else:
            for _ in range(ITERATIONS):
                mid = math.sqrt(lo * hi)
                lo, hi = (mid, hi) if enough(f(mid)) and safe(f(mid)) else (lo, mid)
            k, status = lo, "increased"
    chosen = f(k)
    return {**chosen, "status": status, "evaluations": len(evals), "patient": patient}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m ghostlows.sim.calibrate", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument("--out", required=True)
    parser.add_argument("--patients", nargs="*", default=PATIENTS)
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args(argv)
    commit = git_commit()  # recorded before running, with whether the simulator code was edited
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "src/ghostlows/sim"], capture_output=True, text=True
    ).stdout.strip()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(calibrate_patient, args.patients))
    table = pd.DataFrame(rows).set_index("patient")
    doc = {
        "description": (
            "Per-patient bolus scale from python -m ghostlows.sim.calibrate (D17). "
            "Generated; do not edit."
        ),
        "method": {
            "mix": "standard",
            "days": DAYS,
            "seed": CALIBRATION_SEED,
            "tbr70_band_pct": list(TBR_BAND_PCT),
            "nadir_floor_mg_dl": NADIR_FLOOR,
            "bolus_scale_bounds": [K_MIN, K_MAX],
        },
        "generated": {
            "utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "git_commit": commit,
            "sim_code_modified": bool(dirty),
            "ghostlows": version("ghostlows"),
            "simglucose": version("simglucose"),
        },
        "patients": {
            p: {k: (v.item() if hasattr(v, "item") else v) for k, v in r.items()}
            for p, r in table.to_dict("index").items()
        },
    }
    with open(args.out, "w") as f:
        yaml.safe_dump(doc, f, sort_keys=False)
    print(table.to_string())


if __name__ == "__main__":
    main()
