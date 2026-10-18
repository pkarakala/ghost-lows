"""Run a simulation config across patients, seeds and scenario mixes, with a Parquet cache.

uv run python -m ghostlows.sim --config experiments/configs/sim_smoke.yaml
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .engine import PATIENTS, Therapy, simulate
from .scenario import get_mix, make_scenario

REPO = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("GHOSTLOWS_DATA_DIR") or REPO / "data")


@dataclass
class SimConfig:
    name: str
    patients: list[str] = field(default_factory=lambda: list(PATIENTS))
    days: int = 14  # ASSUMPTION: SIMULATION.md §1
    seeds: list[int] = field(default_factory=lambda: [1, 2, 3, 4, 5])
    mixes: list[str] = field(default_factory=lambda: ["default"])
    calibration: str | None = None  # YAML with a bolus_scale per patient (D17)
    start: str = "2026-01-05"
    dia_h: float = 5.0
    cob_h: float = 3.0

    @classmethod
    def load(cls, path: str | Path) -> SimConfig:
        raw = yaml.safe_load(Path(path).read_text())
        if raw.get("patients") == "all":
            raw["patients"] = list(PATIENTS)
        unknown = set(raw) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        return cls(**raw)

    def therapy(self) -> dict[str, Therapy]:
        if not self.calibration:
            return {p: Therapy() for p in self.patients}
        table = yaml.safe_load((REPO / self.calibration).read_text())["patients"]
        return {p: Therapy(bolus_scale=float(table[p]["bolus_scale"])) for p in self.patients}

    def key(self) -> str:
        """Hash of everything that changes the output."""
        payload = dict(self.__dict__)
        if self.calibration:
            payload["calibration_sha256"] = hashlib.sha256(
                (REPO / self.calibration).read_bytes()
            ).hexdigest()
        payload["versions"] = {
            "ghostlows": version("ghostlows"),
            "simglucose": version("simglucose"),
        }
        blob = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:12]

    def out_dir(self) -> Path:
        return DATA / "sim" / f"{self.name}-{self.key()}"


def task_seeds(seed: int, patient: str) -> tuple[int, int, int]:
    """Meal, perturbation and noise seeds; the same in every mix, so mixes are paired."""
    state = np.random.SeedSequence([seed, PATIENTS.index(patient)]).generate_state(3)
    return tuple(int(s) % (2**31) for s in state)


def _run_task(args):
    patient, seed, mix_name, therapy, days, start, dia_h, cob_h = args
    t0 = time.time()
    meal_seed, perturb_seed, noise_seed = task_seeds(seed, patient)
    scenario = make_scenario(get_mix(mix_name), days, meal_seed, perturb_seed)
    result = simulate(
        patient, scenario, therapy, noise_seed, pd.Timestamp(start), dia_h=dia_h, cob_h=cob_h
    )
    tag = {"seed": seed, "mix": mix_name}
    run = {
        "patient_id": f"sim:{patient}",
        **tag,
        "valid": result.valid,
        "nadir": result.nadir,
        "tbr70_truth_pct": 100 * float((result.truth["truth_glucose"] < 70).mean()),
        "tbr54_truth_pct": 100 * float((result.truth["truth_glucose"] < 54).mean()),
        "seconds": time.time() - t0,
    }
    return (
        result.samples.assign(**tag),
        result.truth.assign(**tag),
        result.events.assign(patient_id=f"sim:{patient}", **tag),
        run,
    )


def tasks(config: SimConfig) -> list[tuple]:
    therapy = config.therapy()
    return [
        (p, s, m, therapy[p], config.days, config.start, config.dia_h, config.cob_h)
        for m in config.mixes
        for s in config.seeds
        for p in config.patients
    ]


def git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run(config: SimConfig, force: bool = False, workers: int | None = None) -> Path:
    """Simulate every task in `config` (or reuse the cache) and return the output folder."""
    out = config.out_dir()
    if (out / "meta.json").exists() and not force:
        return out
    out.mkdir(parents=True, exist_ok=True)
    jobs = tasks(config)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_run_task, jobs))
    samples, truth, events, runs = (list(x) for x in zip(*results, strict=True))
    pd.concat(samples, ignore_index=True).to_parquet(out / "samples.parquet", index=False)
    pd.concat(truth, ignore_index=True).to_parquet(out / "truth.parquet", index=False)
    pd.concat(events, ignore_index=True).to_parquet(out / "events.parquet", index=False)
    pd.DataFrame(runs).to_csv(out / "runs.csv", index=False)
    (out / "config.yaml").write_text(yaml.safe_dump(config.__dict__, sort_keys=False))
    meta = {
        "key": config.key(),
        "git_commit": git_commit(),
        "ghostlows": version("ghostlows"),
        "simglucose": version("simglucose"),
        "tasks": len(jobs),
        "wall_seconds": round(time.time() - t0, 1),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return out


def load(out: Path) -> dict[str, pd.DataFrame]:
    return {
        name: pd.read_parquet(out / f"{name}.parquet") for name in ("samples", "truth", "events")
    }
