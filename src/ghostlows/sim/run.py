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

from .engine import PATIENTS, HypoTreatment, SimResult, Therapy, simulate
from .scenario import get_mix, make_scenario

REPO = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("GHOSTLOWS_DATA_DIR") or REPO / "data")
# Bump by hand whenever a change to ghostlows.sim changes what a simulation outputs; the cache
# key hashes it instead of the package version (docs/reference/ENGINEERING.md, Simulation cache).
SIM_CODE = 1


@dataclass
class SimConfig:
    name: str
    patients: list[str] = field(default_factory=lambda: list(PATIENTS))
    days: int = 14  # ASSUMPTION: SIMULATION.md §1
    seeds: list[int] = field(default_factory=lambda: [1, 2, 3, 4, 5])
    mixes: list[str] = field(default_factory=lambda: ["default"])
    calibration: str | None = None  # YAML with a bolus_scale per patient (D17)
    start: str = "2026-01-05"
    dia_h: float = 5.0  # ASSUMPTION: insulin action duration for IOB (SIMULATION.md §2)
    cob_h: float = 3.0  # ASSUMPTION: carbohydrate absorption time for COB (SIMULATION.md §2)
    hypo_treatment: bool = True  # the virtual person treats lows (amendment A6)

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
        """Hash of the simulation inputs: the config (seeds included), the calibration file, the
        simglucose version and SIM_CODE. Not the ghostlows version, so a release that leaves the
        simulation alone reuses the cached cohort."""
        payload = dict(self.__dict__)
        if self.calibration:
            payload["calibration_sha256"] = hashlib.sha256(
                (REPO / self.calibration).read_bytes()
            ).hexdigest()
        payload["versions"] = {"simglucose": version("simglucose")}
        payload["sim_code"] = SIM_CODE
        payload["layout"] = 2  # one Parquet part per patient-run
        blob = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:12]

    def out_dir(self) -> Path:
        return DATA / "sim" / f"{self.name}-{self.key()}"


def task_seeds(seed: int, patient: str) -> tuple[int, int, int]:
    """Meal, perturbation and noise seeds; the same in every mix, so mixes are paired."""
    state = np.random.SeedSequence([seed, PATIENTS.index(patient)]).generate_state(3)
    return tuple(int(s) % (2**31) for s in state)


PARTS = ("samples", "truth", "events")  # one part file per patient-run in each folder


def part_name(patient: str, seed: int, mix: str) -> str:
    return f"{mix}_s{seed}_{patient.replace('#', '-')}.parquet"


def pending(jobs: list[tuple], out: Path, force: bool = False) -> list[tuple]:
    """The jobs to simulate: all with `force`, else those missing any of their three parts (a
    run interrupted between two part writes is redone, not half reused)."""
    return [
        j
        for j in jobs
        if force or not all((out / sub / part_name(j[0], j[1], j[2])).exists() for sub in PARTS)
    ]


def _simulate(patient, seed, mix_name, therapy, days, start, dia_h, cob_h, treat) -> SimResult:
    meal_seed, perturb_seed, noise_seed = task_seeds(seed, patient)
    scenario = make_scenario(get_mix(mix_name), days, meal_seed, perturb_seed)
    return simulate(
        patient,
        scenario,
        therapy,
        noise_seed,
        pd.Timestamp(start),
        dia_h=dia_h,
        cob_h=cob_h,
        treatment=HypoTreatment() if treat else None,
    )


def simulate_run(config: SimConfig, patient: str, seed: int, mix: str) -> SimResult:
    """One patient-run exactly as `run` simulates it for the cohort (same seeds and therapy)."""
    therapy = config.therapy()[patient]
    return _simulate(
        patient,
        seed,
        mix,
        therapy,
        config.days,
        config.start,
        config.dia_h,
        config.cob_h,
        config.hypo_treatment,
    )


def _run_task(args):
    """Simulate one patient-run and write its three part files; return its summary row."""
    patient, seed, mix_name, therapy, days, start, dia_h, cob_h, treat, out = args
    t0 = time.time()
    result = _simulate(patient, seed, mix_name, therapy, days, start, dia_h, cob_h, treat)
    tag = {"seed": seed, "mix": mix_name}
    name = part_name(patient, seed, mix_name)
    parts = {
        "samples": result.samples.assign(**tag),
        "truth": result.truth.assign(**tag),
        "events": result.events.assign(patient_id=f"sim:{patient}", **tag),
    }
    for folder, frame in parts.items():
        # write, then rename: a killed run leaves no truncated part (dot files are not read)
        tmp = Path(out) / folder / f".{name}.tmp"
        frame.to_parquet(tmp, index=False)
        os.replace(tmp, Path(out) / folder / name)
    return {
        "patient_id": f"sim:{patient}",
        **tag,
        "valid": result.valid,
        "nadir": result.nadir,
        # SOURCE: Battelino 2019 (time below 70 and 54 mg/dL) CLINICAL-REVIEW: CR6
        "tbr70_truth_pct": 100 * float((result.truth["truth_glucose"] < 70).mean()),
        "tbr54_truth_pct": 100 * float((result.truth["truth_glucose"] < 54).mean()),
        "seconds": time.time() - t0,
    }


def tasks(config: SimConfig, out: Path) -> list[tuple]:
    therapy = config.therapy()
    return [
        (
            p,
            s,
            m,
            therapy[p],
            config.days,
            config.start,
            config.dia_h,
            config.cob_h,
            config.hypo_treatment,
            str(out),
        )
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
    """Simulate every task in `config` (or reuse the cache) and return the output folder.

    Each patient-run is written as its own part file as soon as it finishes, so memory stays
    bounded and an interrupted run resumes: finished parts are reused unless `force`.
    """
    out = config.out_dir()
    if (out / "meta.json").exists() and not force:
        return out
    for folder in PARTS:
        (out / folder).mkdir(parents=True, exist_ok=True)
    previous = (
        pd.read_csv(out / "runs.partial.csv") if (out / "runs.partial.csv").exists() else None
    )
    jobs = tasks(config, out)
    todo = pending(jobs, out, force)
    t0 = time.time()
    rows = [] if previous is None or force else previous.to_dict("records")
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(_run_task, todo):
            rows.append(row)
            pd.DataFrame(rows).to_csv(out / "runs.partial.csv", index=False)
    pd.DataFrame(rows).drop_duplicates(["patient_id", "seed", "mix"], keep="last").to_csv(
        out / "runs.csv", index=False
    )
    (out / "runs.partial.csv").unlink(missing_ok=True)
    (out / "config.yaml").write_text(yaml.safe_dump(config.__dict__, sort_keys=False))
    meta = {
        "key": config.key(),
        "git_commit": git_commit(),
        "ghostlows": version("ghostlows"),
        "simglucose": version("simglucose"),
        "tasks": len(jobs),
        "resumed_tasks": len(jobs) - len(todo),
        "wall_seconds": round(time.time() - t0, 1),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return out


def load(out: Path) -> dict[str, pd.DataFrame]:
    """The cohort's samples, 1-min truth and event log (each folder read as one dataset)."""
    return {name: pd.read_parquet(out / name) for name in PARTS}
