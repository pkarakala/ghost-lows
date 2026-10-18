"""uv run python -m ghostlows.sim --config experiments/configs/sim_smoke.yaml"""

import argparse

import pandas as pd

from .run import SimConfig, run


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ghostlows.sim", description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--force", action="store_true", help="ignore the cache")
    parser.add_argument("--workers", type=int, default=None, help="processes (default: all cores)")
    args = parser.parse_args(argv)
    config = SimConfig.load(args.config)
    out = run(config, force=args.force, workers=args.workers)
    runs = pd.read_csv(out / "runs.csv")
    print(f"output    {out}")
    summary = runs.groupby("mix")[
        ["tbr70_truth_pct", "tbr54_truth_pct", "nadir", "seconds"]
    ].median()
    print(summary.round(2).to_string())
    invalid = runs[~runs["valid"]]
    if len(invalid):
        print(f"outside model validity (plasma < 10 mg/dL): {len(invalid)} runs")


if __name__ == "__main__":
    main()
