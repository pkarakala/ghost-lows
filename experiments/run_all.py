"""Regenerate every benchmark table and figure from one command (ROADMAP phase 6).

    uv run python experiments/run_all.py            # skips runs whose outputs exist
    uv run python experiments/run_all.py --force    # recompute everything

Runs the configs below into results/<name>/ (gitignored), draws their figures, copies the
headline figures and tables into results/figures/ (robustness arms: results/figures/appendix/)
and results/tables/ (committed), runs the trade-off curves (run_curves.py, amendment A11), draws
the publication figures (make_paper_figures.py) and writes results/README.md.
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

from ghostlows.bench.analysis import RQ3_MODELS, h1_contrast, rq3_contrasts, warning_times
from ghostlows.bench.pipeline import BenchConfig, run_benchmark, summarise
from ghostlows.bench.stats import age_group

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
    for name in names:
        by_age_group(REPO / "results" / name)
        warnings_table(REPO / "results" / name)
    figures, tables = REPO / "results" / "figures", REPO / "results" / "tables"
    figures.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    for name in names:
        out = REPO / "results" / name
        if not (out / "summary.csv").exists():
            continue
        dest = figures / "appendix" if name.startswith("robust_") else figures
        dest.mkdir(exist_ok=True)
        for fig in HEADLINE_FIGURES:
            src = out / "figures" / f"{fig}.png"
            if src.exists():
                shutil.copy(src, dest / f"{name}__{fig}.png")
        for table in (
            "summary.csv",
            "contrasts_h2.csv",
            "contrast_h1.csv",
            "contrasts_rq3.csv",
            "summary_by_age_group.csv",
            "warning.csv",
            "contrast_h1_by_age_group.csv",
            "thresholds.csv",
            "meta.json",
            "git_commit.txt",
        ):
            if (out / table).exists():
                shutil.copy(out / table, tables / f"{name}__{table}")
    if not args.only:  # trade-off curves (amendment A11), same cohort and folds
        subprocess.run(
            [
                sys.executable,
                str(REPO / "experiments" / "run_curves.py"),
                "--workers",
                str(args.workers),
            ]
            + (["--force"] if args.force else []),
            check=True,
        )
    for script in ("make_paper_figures.py", "make_results_readme.py"):
        subprocess.run([sys.executable, str(REPO / "experiments" / script)], check=True)


def by_age_group(out: Path) -> None:
    """Results by age group as well as pooled (D14): the summary and the H1 contrast per group,
    written next to the run's other outputs (patient-bootstrap CIs within each group)."""
    if not (out / "metrics.csv").exists() or (out / "summary_by_age_group.csv").exists():
        return
    m = pd.read_csv(out / "metrics.csv")
    m["age_group"] = m["patient_id"].map(age_group)
    n_boot = BenchConfig.load(out / "config.yaml").n_boot
    summaries, h1 = [], []
    for group, g in m.groupby("age_group"):
        summaries.append(summarise(g, n_boot).assign(age_group=group))
        if g["level"].nunique() > 1:
            h1.append(h1_contrast(g, n_boot=n_boot).assign(age_group=group))
    pd.concat(summaries).to_csv(out / "summary_by_age_group.csv", index=False)
    if h1:
        pd.concat(h1).to_csv(out / "contrast_h1_by_age_group.csv", index=False)
    print(f"by age    {out.name}", flush=True)


def warnings_table(out: Path) -> None:
    """Minutes of warning with the miss rate (BENCHMARK.md §4), next to the run's outputs."""
    if not (out / "metrics.csv").exists() or (out / "warning.csv").exists():
        return
    n_boot = BenchConfig.load(out / "config.yaml").n_boot
    warning_times(pd.read_csv(out / "metrics.csv"), n_boot=n_boot).to_csv(
        out / "warning.csv", index=False
    )
    print(f"warning   {out.name}", flush=True)


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
