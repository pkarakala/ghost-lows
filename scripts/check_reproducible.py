"""Check that committed results reproduce from a clean checkout (ROADMAP phase 10).

    uv run python scripts/check_reproducible.py --config rq1_pisa_sweep [--resimulate 3]

1. Clones the repository at the commit that produced `results/tables/<config>__*` (recorded in
   `results/tables/<config>__git_commit.txt`) into a temporary folder and installs it with
   `uv sync --locked`.
2. Runs the benchmark config in the clone, sharing this checkout's `data/` (raw data and the
   cached simulated cohort) through GHOSTLOWS_DATA_DIR, and compares its tables with the
   committed ones.
3. With --resimulate N, re-simulates N randomly chosen patient-runs of the cohort in the clone
   and compares them with the cached parts, so the cohort itself is shown to be deterministic.

Prints what matched and exits non-zero on any difference.
"""

from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
TABLES = REPO / "results" / "tables"
COMPARED = (
    "summary.csv",
    "contrasts_h2.csv",
    "contrast_h1.csv",
    "contrasts_rq3.csv",
    "thresholds.csv",
)


def sh(cmd: list[str], cwd: Path, env: dict | None = None) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def same_table(a: Path, b: Path) -> tuple[bool, str]:
    x, y = pd.read_csv(a), pd.read_csv(b)
    if list(x.columns) != list(y.columns) or len(x) != len(y):
        return False, f"shape or columns differ: {x.shape} vs {y.shape}"
    try:
        pd.testing.assert_frame_equal(x, y, check_exact=False, rtol=1e-9, atol=1e-12)
    except AssertionError as exc:
        return False, str(exc).splitlines()[0]
    return True, f"{len(x)} rows identical"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", required=True, help="a config name in experiments/configs/")
    parser.add_argument("--resimulate", type=int, default=0, help="patient-runs to re-simulate")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    commit_file = TABLES / f"{args.config}__git_commit.txt"
    if not commit_file.exists():
        print(f"no {commit_file.relative_to(REPO)}: run experiments/run_all.py first")
        return 2
    commit = commit_file.read_text().strip()
    env = dict(os.environ, GHOSTLOWS_DATA_DIR=str(REPO / "data"), OMP_NUM_THREADS="2")
    ok = True
    with tempfile.TemporaryDirectory(prefix="ghostlows-clean-") as tmp:
        clone = Path(tmp) / "ghost-lows"
        sh(["git", "clone", "--quiet", str(REPO), str(clone)], Path(tmp))
        sh(["git", "checkout", "--quiet", commit], clone)
        sh(["uv", "sync", "--locked", "--quiet"], clone, env)
        out = Path(tmp) / "out"
        sh(
            [
                "uv",
                "run",
                "python",
                "experiments/run_benchmark.py",
                "--config",
                f"experiments/configs/{args.config}.yaml",
                "--out",
                str(out),
                "--workers",
                str(args.workers),
            ],
            clone,
            env,
        )
        for name in COMPARED:
            committed = TABLES / f"{args.config}__{name}"
            if not committed.exists():
                continue
            match, detail = same_table(committed, out / name)
            ok &= match
            print(f"{'same' if match else 'DIFFERENT'}  {name}: {detail}")
        if args.resimulate:
            ok &= resimulate(clone, env, args.resimulate)
    print("reproduced" if ok else "NOT reproduced", f"(commit {commit[:12]})")
    return 0 if ok else 1


def resimulate(clone: Path, env: dict, n: int) -> bool:
    """Re-simulate n cached patient-runs in the clean clone and compare them part by part."""
    sys.path.insert(0, str(REPO / "src"))
    from ghostlows.sim.run import SimConfig

    config = SimConfig.load(REPO / "experiments" / "configs" / "sim_full.yaml")
    cached = config.out_dir()
    parts = sorted((cached / "samples").glob("*.parquet"))
    picks = random.Random(0).sample(parts, min(n, len(parts)))
    code = (
        "import sys, pandas as pd; from ghostlows.sim.run import SimConfig, _run_task; "
        "from ghostlows.sim.engine import PATIENTS; "
        "c = SimConfig.load('experiments/configs/sim_full.yaml'); t = c.therapy(); "
        "mix, seed, patient = sys.argv[1], int(sys.argv[2]), sys.argv[3]; "
        "_run_task((patient, seed, mix, t[patient], c.days, c.start, c.dia_h, c.cob_h, "
        "c.hypo_treatment, sys.argv[4]))"
    )
    ok = True
    for part in picks:
        mix, seed, patient = part.stem.split("_", 2)
        patient = patient.replace("-", "#")
        with tempfile.TemporaryDirectory() as out:
            for sub in ("samples", "truth", "events"):
                (Path(out) / sub).mkdir()
            run_env = dict(env, GHOSTLOWS_DATA_DIR=out)
            sh(["uv", "run", "python", "-c", code, mix, seed[1:], patient, out], clone, run_env)
            for sub in ("samples", "truth", "events"):
                a = pd.read_parquet(cached / sub / part.name)
                b = pd.read_parquet(Path(out) / sub / part.name)
                same = a.equals(b)
                ok &= same
                print(f"{'same' if same else 'DIFFERENT'}  {sub}/{part.name}")
    return ok


if __name__ == "__main__":
    sys.exit(main())
