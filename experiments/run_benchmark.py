"""Run the benchmark from one config and write results/<run_id>/ (BENCHMARK.md §7).

uv run python experiments/run_benchmark.py --config experiments/configs/smoke.yaml
"""

import argparse
import time
from datetime import UTC, datetime
from pathlib import Path

from ghostlows.bench.pipeline import BenchConfig, run_benchmark

REPO = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", help="output folder (default: results/<name>-<UTC time>)")
    args = parser.parse_args()
    config = BenchConfig.load(args.config)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out) if args.out else REPO / "results" / f"{config.name}-{stamp}"
    t0 = time.time()
    result = run_benchmark(config, out)
    summary = result["summary"]
    cols = ["alarm_name", "pisa_fraction", "sens_l2", "false_per_day", "false_compression_per_day"]
    print(summary[[c for c in cols if c in summary]].round(3).to_string(index=False))
    print(f"\nwrote {out} in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
