"""End-to-end benchmark run (BENCHMARK.md §5-7): faults, cross-validation, operating point, scoring.

uv run python experiments/run_benchmark.py --config experiments/configs/smoke.yaml
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ..alarms import BaseAlarm, TrendAlarm, benchmark_alarms, view
from ..faults import FaultConfig, apply_faults
from .events import low_labels, true_events
from .scoring import (
    CAUSES,
    classify_alarms,
    fda_rates,
    per_run_metrics,
    run_hours,
    score_events,
)
from .stats import (
    MIN_L2_EVENTS,
    age_group,
    bootstrap_ci,
    candidate_thresholds,
    choose_threshold,
    patient_folds,
    ratio_of_sums,
)

BENCHMARK_VERSION = "ghostlows-bench v1"
REPO = Path(__file__).resolve().parents[3]
REFERENCE_ALARM = "trend"  # D5: level 2 sensitivity reference
LEARNED = ("_combined", "gbm")


@dataclass
class BenchConfig:
    name: str
    simulation: str  # path to a SimConfig YAML
    pisa_fractions: list[float] = field(default_factory=lambda: [0.0, 0.1, 0.25, 0.5, 0.75, 1.0])
    severity: float = 0.5  # other faults, moderate (SIMULATION.md §4.3)
    fault_seed: int = 0
    alarms: list[str] | str = "all"
    n_folds: int = 5
    delta: float = 0.0  # D5 non-inferiority margin
    n_boot: int = 2000
    fold_seed: int = 0

    @classmethod
    def load(cls, path) -> BenchConfig:
        raw = yaml.safe_load(Path(path).read_text())
        return cls(**raw)


def is_learned(alarm: BaseAlarm) -> bool:
    """Learned alarms are fitted and get the pre-registered operating point; a user alarm opts in
    with `learned = True`."""
    return bool(getattr(alarm, "learned", False)) or any(tag in alarm.name for tag in LEARNED)


def alarm_frame(df: pd.DataFrame, alarm: BaseAlarm, with_label: bool = False) -> pd.DataFrame:
    v = view(df, "cgm_observed", context=alarm.uses_context)
    return v.assign(label=df["label"]) if with_label else v


def fire_and_score(alarm, frame, threshold, events, faults, observed):
    """Fire `alarm` and score it: (alarm events, classified alarms, per-event results).

    False alarms are judged against level 1 events; per-event results cover every level given.
    """
    fired = alarm.alarms(frame, threshold)
    if fired.empty:
        fired = pd.DataFrame(
            columns=["time", "is_floor", "patient_id", "seed", "mix", "alarm_name"]
        )
    fired["alarm_name"] = alarm.name
    labels = observed[["patient_id", "seed", "mix", "time", "fault_type"]]
    classified = classify_alarms(fired, events, faults, labels)
    scored = score_events(fired, events)
    return fired, classified, scored


def training_threshold(alarm, frame, train_obs, events, faults, reference_sens, delta):
    """Pre-registered rule on training patients (D5): fewest false alarms per day with level 2
    sensitivity at least the reference's."""
    scores = alarm.score(frame)
    days = run_hours(train_obs)["hours"].sum() / 24
    cache: dict[float, tuple[float, float]] = {}

    def evaluate(theta):
        if theta not in cache:
            _, classified, scored = fire_and_score(alarm, frame, theta, events, faults, train_obs)
            l2 = scored[scored["level"] == 2] if len(scored) else scored
            sens = float(l2["caught"].mean()) if len(l2) else float("nan")
            fpd = float((~classified["matched"]).sum() / days) if len(classified) else 0.0
            cache[theta] = (sens, fpd)
        return cache[theta]

    theta, info = choose_threshold(
        candidate_thresholds(scores.to_numpy()),
        lambda t: evaluate(t)[0],
        lambda t: evaluate(t)[1],
        reference_sens,
        delta,
    )
    n_l2 = int((events["level"] == 2).sum())
    info.update(l2_events=n_l2, estimable=n_l2 >= MIN_L2_EVENTS)
    return theta, info


def run_benchmark(config: BenchConfig, out_dir: Path, extra_alarms=()) -> dict[str, pd.DataFrame]:
    """Run `config` (plus any user alarms in `extra_alarms`) and write the outputs to `out_dir`."""
    from ..sim.run import SimConfig, load, run

    sim_config = SimConfig.load(REPO / config.simulation)
    data = load(run(sim_config))
    samples, truth = data["samples"], data["truth"]
    events = true_events(truth)
    folds = patient_folds(
        samples["patient_id"].unique(),
        min(config.n_folds, samples["patient_id"].nunique()),
        config.fold_seed,
    )
    alarms_all = benchmark_alarms(seed=0)
    if config.alarms != "all":
        alarms_all = [a for a in alarms_all if a.name in config.alarms]
    alarms_all += list(extra_alarms)

    metrics, thresholds = [], []
    for fraction in config.pisa_fractions:
        fault_config = FaultConfig(pisa_fraction=fraction, severity=config.severity)
        observed, faults = apply_faults(samples, fault_config, seed=config.fault_seed)
        observed["label"] = low_labels(observed, events)
        observed["fold"] = observed["patient_id"].map(folds)
        for fold in sorted(set(folds.values())):
            train_obs = observed[observed["fold"] != fold]
            test_obs = observed[observed["fold"] == fold]
            train_ev = events[events["patient_id"].isin(train_obs["patient_id"].unique())]
            test_ev = events[events["patient_id"].isin(test_obs["patient_id"].unique())]
            # reference: the CGM-only trend alarm's level 2 sensitivity on the training patients
            trend = TrendAlarm()
            _, _, ref = fire_and_score(
                trend, alarm_frame(train_obs, trend), None, train_ev, faults, train_obs
            )
            ref_l2 = ref[ref["level"] == 2] if len(ref) else ref
            reference = float(ref_l2["caught"].mean()) if len(ref_l2) else np.nan
            for alarm in alarms_all:
                threshold, info = alarm.default_threshold, {"feasible": True, "estimable": True}
                if is_learned(alarm):
                    alarm.fit(alarm_frame(train_obs, alarm, with_label=True))
                    threshold, info = training_threshold(
                        alarm,
                        alarm_frame(train_obs, alarm),
                        train_obs,
                        train_ev,
                        faults,
                        reference,
                        config.delta,
                    )
                thresholds.append(
                    {
                        "pisa_fraction": fraction,
                        "fold": fold,
                        "alarm_name": alarm.name,
                        "threshold": threshold,
                        "reference_sens_l2": reference,
                        "feasible": info.get("feasible"),
                        "estimable": info.get("estimable"),
                    }
                )
                fired, classified, scored = fire_and_score(
                    alarm, alarm_frame(test_obs, alarm), threshold, test_ev, faults, test_obs
                )
                m = per_run_metrics(classified, scored, run_hours(test_obs), [alarm.name])
                fda = fda_rates(
                    fired, truth[truth["patient_id"].isin(test_obs["patient_id"].unique())]
                )
                if len(fda):
                    m = m.merge(fda, on=["patient_id", "seed", "mix", "alarm_name"], how="left")
                metrics.append(
                    m.assign(pisa_fraction=fraction, severity=config.severity, fold=fold)
                )
    metrics_df = pd.concat(metrics, ignore_index=True)
    summary = summarise(metrics_df, config.n_boot)
    write_outputs(config, out_dir, metrics_df, summary, pd.DataFrame(thresholds))
    return {"metrics": metrics_df, "summary": summary, "thresholds": pd.DataFrame(thresholds)}


def per_patient(metrics: pd.DataFrame) -> pd.DataFrame:
    """Sum counts over a patient's runs (seeds), keeping alarm, fault level and mix."""
    count_cols = [
        c
        for c in metrics.columns
        if c.startswith(("n_", "false_", "events_l", "caught_l")) and not c.endswith("_per_day")
    ]
    keys = ["alarm_name", "pisa_fraction", "mix", "patient_id"]
    out = metrics.groupby(keys)[count_cols + ["hours"]].sum().reset_index()
    out["days"] = out["hours"] / 24
    return out


SUMMARY_RATES = {
    "sens_l1": ("caught_l1", "events_l1"),
    "sens_l2": ("caught_l2", "events_l2"),
    "false_per_day": ("n_false", "days"),
    **{f"false_{c}_per_day": (f"false_{c}", "days") for c in CAUSES},
}


def summarise(metrics: pd.DataFrame, n_boot: int) -> pd.DataFrame:
    """Pooled rates with patient-bootstrap 95% CIs, per alarm x PISA fraction x mix."""
    pp = per_patient(metrics)
    rows = []
    for key, g in pp.groupby(["alarm_name", "pisa_fraction", "mix"]):
        row = dict(zip(["alarm_name", "pisa_fraction", "mix"], key, strict=True))
        row["patients"] = g["patient_id"].nunique()
        for name, (num, den) in SUMMARY_RATES.items():
            if num in g and den in g:
                est, lo, hi = bootstrap_ci(g, ratio_of_sums(num, den), n_boot=n_boot)
                row.update({name: est, f"{name}_lo": lo, f"{name}_hi": hi})
        rows.append(row)
    return pd.DataFrame(rows)


def collect_assumptions() -> str:
    """Every `# ASSUMPTION:` comment in the package with its location and the code it qualifies.

    A trailing comment is shown with the code on its line; a comment block is joined with its
    continuation lines and shown with the next line of code.
    """
    lines = ["# Assumptions collected from the code", ""]
    for path in sorted((REPO / "src" / "ghostlows").rglob("*.py")):
        text = path.read_text().splitlines()
        for i, line in enumerate(text):
            m = re.search(r"#\s*ASSUMPTION:\s*(.+)$", line)
            if not m:
                continue
            note, code = m.group(1).strip(), line[: m.start()].strip()
            if not code:  # comment block: join continuation lines, then the next code line
                j = i + 1
                while j < len(text) and text[j].strip().startswith("#") and ":" not in text[j][:20]:
                    note += " " + text[j].strip().lstrip("#").strip()
                    j += 1
                code = text[j].strip() if j < len(text) else ""
            where = f"{path.relative_to(REPO)}:{i + 1}"
            lines.append(f"- `{where}` `{code[:80]}`: {note}" if code else f"- `{where}`: {note}")
    return "\n".join(lines) + "\n"


def write_outputs(config, out_dir: Path, metrics, summary, thresholds) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "figures").mkdir(exist_ok=True)
    metrics.to_csv(out_dir / "metrics.csv", index=False)
    summary.to_csv(out_dir / "summary.csv", index=False)
    thresholds.to_csv(out_dir / "thresholds.csv", index=False)
    (out_dir / "config.yaml").write_text(yaml.safe_dump(asdict(config), sort_keys=False))
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown\n"
    (out_dir / "git_commit.txt").write_text(commit)
    (out_dir / "benchmark_version.txt").write_text(BENCHMARK_VERSION + "\n")
    (out_dir / "assumptions.md").write_text(collect_assumptions())
    ids = pd.Series(metrics["patient_id"].unique())
    groups = ids.map(age_group).value_counts().to_dict()
    patients = metrics["patient_id"].nunique()
    fractions = [float(f) for f in sorted(metrics["pisa_fraction"].unique())]
    (out_dir / "README.txt").write_text(
        f"{BENCHMARK_VERSION} run '{config.name}': {patients} patients {groups}, "
        f"{metrics['alarm_name'].nunique()} alarms, PISA fractions {fractions}.\n"
    )
