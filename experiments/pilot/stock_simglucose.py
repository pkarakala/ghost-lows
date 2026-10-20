"""Pilot: true lows, IOB leak and lag in stock simglucose (evidence for
docs/reference/DECISIONS.md).

Stock BBController, RandomScenario and a 5-min sensor (GuardianRT parameters, identical noise to
the bundled Dexcom row), seed 1. Records plasma glucose (state x[3]/Vg), simglucose's `BG`
(subcutaneous Gsub), CGM, carbs and boluses every 5 min. Not part of the benchmark.

    uv run python experiments/pilot/stock_simglucose.py 14 data/pilot/stock14.parquet
    uv run python experiments/pilot/analyse_stock.py data/pilot/stock14.parquet
"""

import logging
import sys
import time
import warnings
from datetime import datetime
from multiprocessing import Pool

import pandas as pd

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

from simglucose.actuator.pump import InsulinPump  # noqa: E402
from simglucose.controller.basal_bolus_ctrller import BBController  # noqa: E402
from simglucose.patient.t1dpatient import T1DPatient  # noqa: E402
from simglucose.sensor.cgm import CGMSensor  # noqa: E402
from simglucose.simulation.env import T1DSimEnv  # noqa: E402
from simglucose.simulation.scenario_gen import RandomScenario  # noqa: E402

DAYS = int(sys.argv[1])
NAMES = (
    [f"adolescent#{i:03d}" for i in range(1, 11)]
    + [f"adult#{i:03d}" for i in range(1, 11)]
    + [f"child#{i:03d}" for i in range(1, 11)]
)


def run(name, seed=1):
    t0 = time.time()
    patient = T1DPatient.withName(name)
    env = T1DSimEnv(
        patient,
        CGMSensor.withName("GuardianRT", seed=seed),
        InsulinPump.withName("Insulet"),
        RandomScenario(start_time=datetime(2026, 1, 1), seed=seed),
    )
    ctrl = BBController()
    obs, reward, done, info = env.reset()
    vg = patient._params.Vg
    rows = []
    for _ in range(DAYS * 288):
        act = ctrl.policy(obs, reward, done, **info)
        obs, reward, done, info = env.step(act)
        rows.append(
            (
                info["time"],
                patient.state[3] / vg,
                info["bg"],
                obs.CGM,
                info["meal"] * 5,
                act.bolus * 5,
            )
        )
        if done:
            break
    df = pd.DataFrame(rows, columns=["time", "plasma", "gsub", "cgm", "carbs_g", "bolus_u"])
    df["patient"] = name
    df["seconds"] = time.time() - t0
    return df


if __name__ == "__main__":
    from pathlib import Path

    Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True)
    names = NAMES[: int(sys.argv[3])] if len(sys.argv) > 3 else NAMES
    with Pool(min(len(names), 10)) as pool:
        out = pd.concat(pool.map(run, names), ignore_index=True)
    out.to_parquet(sys.argv[2])
    print(out.groupby("patient")["seconds"].first().describe()[["mean", "max"]])
