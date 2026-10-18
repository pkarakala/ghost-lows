"""Regenerate every benchmark table and figure from one command (ROADMAP phase 6).

    uv run python experiments/run_all.py            # skips runs whose outputs exist
    uv run python experiments/run_all.py --force    # recompute everything

Runs the configs below into results/<name>/ (gitignored), draws their figures, copies the
headline figures and tables into results/figures/ and results/tables/ (committed) and writes
results/README.md.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

from ghostlows.bench.analysis import RQ3_MODELS, rq3_contrasts
from ghostlows.bench.pipeline import BenchConfig, run_benchmark

REPO = Path(__file__).resolve().parents[1]
CONFIGS = [
    "rq1_pisa_sweep",
    "rq3_kalman",
    "rq1_all_faults",
    "robust_lag6",
    "robust_tau5",
    "robust_tau20",
    "robust_early20",
    "robust_early45",
    "robust_late30",
    "robust_delta05",
]
HEADLINE_FIGURES = [
    "severity_curves",
    "false_alarms_by_cause",
    "sensitivity_vs_false_alarms",
    "context_rate_ratios",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--only", nargs="*", help="subset of config names")
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(6, (os.cpu_count() or 2) - 1)),
        help="processes for fold fits and evaluations (results do not depend on it)",
    )
    args = parser.parse_args()
    names = args.only or CONFIGS
    for name in names:
        out = REPO / "results" / name
        if (out / "summary.csv").exists() and not args.force:
            print(f"skip      {name} (outputs exist)")
            continue
        t0 = time.time()
        print(f"run       {name}", flush=True)
        config = BenchConfig.load(REPO / "experiments" / "configs" / f"{name}.yaml")
        config.workers = args.workers
        run_benchmark(config, out)
        subprocess.run(
            [sys.executable, str(REPO / "experiments" / "make_figures.py"), str(out)], check=True
        )
        print(f"done      {name} in {time.time() - t0:.0f} s", flush=True)

    pair_rq3()
    figures, tables = REPO / "results" / "figures", REPO / "results" / "tables"
    figures.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    for name in names:
        out = REPO / "results" / name
        if not (out / "summary.csv").exists():
            continue
        for fig in HEADLINE_FIGURES:
            src = out / "figures" / f"{fig}.png"
            if src.exists():
                shutil.copy(src, figures / f"{name}__{fig}.png")
        for table in (
            "summary.csv",
            "contrasts_h2.csv",
            "contrast_h1.csv",
            "contrasts_rq3.csv",
            "thresholds.csv",
            "meta.json",
            "git_commit.txt",
        ):
            if (out / table).exists():
                shutil.copy(out / table, tables / f"{name}__{table}")
    subprocess.run(
        [sys.executable, str(REPO / "experiments" / "make_results_readme.py")], check=True
    )


def pair_rq3(base: str = "rq1_pisa_sweep", kalman: str = "rq3_kalman") -> None:
    """RQ3 contrasts from the Kalman run and the main run's discriminative alarms (same cohort,
    folds, faults and training level), written into the Kalman run's folder."""
    a, b = REPO / "results" / base, REPO / "results" / kalman
    if not ((a / "metrics.csv").exists() and (b / "metrics.csv").exists()):
        return
    m_base, m_kal = pd.read_csv(a / "metrics.csv"), pd.read_csv(b / "metrics.csv")
    t_base, t_kal = pd.read_csv(a / "thresholds.csv"), pd.read_csv(b / "thresholds.csv")
    keep = ~m_base["alarm_name"].isin(set(m_kal["alarm_name"]))
    metrics = pd.concat([m_base[keep], m_kal[m_kal["alarm_name"].isin(RQ3_MODELS)]])
    thresholds = pd.concat([t_base, t_kal])
    n_boot = BenchConfig.load(REPO / "experiments" / "configs" / f"{kalman}.yaml").n_boot
    rq3_contrasts(metrics, thresholds, n_boot=n_boot).to_csv(b / "contrasts_rq3.csv", index=False)
    print(f"paired    {kalman} with {base} for RQ3", flush=True)


if __name__ == "__main__":
    main()
