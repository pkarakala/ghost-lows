"""Simulate one shard of a cohort, for running `make results` across several machines.

    uv run python scripts/sim_shard.py --config experiments/configs/sim_full.yaml --shard 0 --of 6
    uv run python scripts/sim_shard.py --config experiments/configs/sim_full.yaml --assemble

A shard writes its patient-runs into the cohort's usual cache folder (data/sim/<name>-<key>/),
with its summary rows in `runs.shard<i>.csv`. With every shard's parts in that folder,
`--assemble` merges the rows and lets `ghostlows.sim.run` finish the cohort exactly as a single
machine would (it finds nothing pending and writes runs.csv and meta.json). The parts are the
same files a single run writes, so the cohort, and its cache key, do not depend on sharding.
Used by .github/workflows/results.yml.
"""

from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from ghostlows.sim.run import PARTS, SimConfig, _run_task, pending, run, tasks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", required=True)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--of", type=int, default=1)
    parser.add_argument("--assemble", action="store_true")
    parser.add_argument("--workers", type=int, default=os.cpu_count())
    args = parser.parse_args()
    config = SimConfig.load(args.config)
    out = config.out_dir()
    for folder in PARTS:
        (out / folder).mkdir(parents=True, exist_ok=True)
    if args.assemble:
        shards = sorted(out.glob("runs.shard*.csv"))
        rows = pd.concat([pd.read_csv(p) for p in shards], ignore_index=True)
        rows.to_csv(out / "runs.partial.csv", index=False)
        missing = pending(tasks(config, out), out)
        if missing:
            raise SystemExit(f"{len(missing)} patient-runs are missing; not assembling")
        print(run(config, workers=args.workers))
        return
    jobs = tasks(config, out)[args.shard :: args.of]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(_run_task, pending(jobs, out)))
    pd.DataFrame(rows).to_csv(out / f"runs.shard{args.shard}.csv", index=False)
    print(f"shard {args.shard} of {args.of}: {len(rows)} patient-runs into {out}")


if __name__ == "__main__":
    main()
