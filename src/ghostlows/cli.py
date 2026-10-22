"""The `ghostlows` command: one command per job (DECISIONS.md D18).

    ghostlows simulate --config experiments/configs/sim_smoke.yaml
    ghostlows benchmark --config experiments/configs/smoke.yaml
    ghostlows score --alarm examples/custom_alarm.py:FallingBelow70 \\
        --config experiments/configs/smoke.yaml

`score` runs your own alarm (any class with the interface in BENCHMARK.md §1) through the same
faults, cross-validation and scoring as the built-in alarms, and prints its summary row.
Data downloads stay in `scripts/download_data.py`.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def load_alarm(spec: str):
    """Instantiate `path/to/file.py:ClassName` (or `package.module:ClassName`)."""
    target, _, cls_name = spec.partition(":")
    if not cls_name:
        raise SystemExit("--alarm must look like path/to/file.py:ClassName")
    if target.endswith(".py"):
        module_spec = importlib.util.spec_from_file_location(Path(target).stem, target)
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[module_spec.name] = module
        module_spec.loader.exec_module(module)
    else:
        module = importlib.import_module(target)
    return getattr(module, cls_name)()


# Modules each command needs beyond the core install (numpy, pandas)
NEEDS = {
    "simulate": ("yaml", "scipy", "pyarrow", "simglucose"),
    "benchmark": ("yaml", "scipy", "sklearn", "pyarrow"),
    "score": ("yaml", "scipy", "sklearn", "pyarrow"),
}


def require_extras(command: str) -> None:
    """Stop with one line, not a traceback, when an optional extra is missing."""
    missing = [m for m in NEEDS[command] if importlib.util.find_spec(m) is None]
    if missing:
        raise SystemExit(
            f"ghostlows {command} needs the bench and sim extras "
            f"(missing: {', '.join(missing)}): pip install 'ghostlows[bench,sim]'"
        )


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="ghostlows",
        description="Benchmark real-time CGM low-glucose alarms under sensor faults. The commands "
        "need the bench and sim extras and a clone of the repository (configs, data/).",
        epilog="As a library: import ghostlows (see examples/quickstart.py).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_sim = sub.add_parser("simulate", help="simulate a cohort (cached under data/sim/)")
    p_sim.add_argument("--config", required=True)
    p_sim.add_argument("--force", action="store_true")
    p_bench = sub.add_parser("benchmark", help="run the benchmark from a config")
    p_bench.add_argument("--config", required=True)
    p_bench.add_argument("--out")
    p_bench.add_argument("--workers", type=int, help="processes for fold fits (default: config)")
    p_score = sub.add_parser("score", help="score your own alarm with a benchmark config")
    p_score.add_argument("--alarm", required=True, help="path/to/file.py:ClassName")
    p_score.add_argument("--config", required=True)
    p_score.add_argument("--out")
    args = parser.parse_args(argv)
    require_extras(args.command)

    if args.command == "simulate":
        from .sim.__main__ import main as sim_main

        sim_main(["--config", args.config] + (["--force"] if args.force else []))
        return

    from datetime import UTC, datetime

    from .bench.pipeline import REPO, BenchConfig, run_benchmark

    config = BenchConfig.load(args.config)
    if getattr(args, "workers", None):
        config.workers = args.workers
    extra = []
    if args.command == "score":
        alarm = load_alarm(args.alarm)
        config.alarms = ["trend"]  # the reference, for comparison
        extra = [alarm]
        config.name = f"{config.name}-{alarm.name}"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out) if args.out else REPO / "results" / f"{config.name}-{stamp}"
    result = run_benchmark(config, out, extra_alarms=extra)
    cols = ["alarm_name", "pisa_fraction", "sens_l2", "false_per_day", "false_compression_per_day"]
    summary = result["summary"]
    print(summary[[c for c in cols if c in summary]].round(3).to_string(index=False))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
