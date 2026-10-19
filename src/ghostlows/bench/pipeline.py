"""End-to-end benchmark run (BENCHMARK.md §5-7, D19): faults, cross-validation, scoring.

    uv run python experiments/run_benchmark.py --config experiments/configs/smoke.yaml

Design (D19): for each fold and scenario mix, learned alarms are fitted and every threshold is
chosen on the training patients at one *training* fault level, then frozen. The sweep over fault
levels evaluates the frozen alarms on the test patients, as a deployed alarm would meet them.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ..alarms import BaseAlarm, TrendAlarm, benchmark_alarms, stretch_alarms, view
from ..faults import FaultConfig, apply_faults
from ..faults.calibrate import realistic_fraction
from .analysis import context_contrasts, h1_contrast, rq3_contrasts
from .events import leak_auc, low_labels, true_events
from .scoring import (
    CAUSES,
    Windows,
    classify_alarms,
    fda_rates,
    per_run_metrics,
    run_hours,
    score_events,
)
from .stats import (
    MIN_L2_EVENTS,
    age_group,
    bootstrap_ratios,
    candidate_thresholds,
    choose_threshold,
    patient_folds,
)

BENCHMARK_VERSION = "ghostlows-bench v1"
REPO = Path(__file__).resolve().parents[3]
LEARNED = ("_combined", "gbm")
N_CANDIDATES = 30  # ASSUMPTION: candidate thresholds per learned alarm (training quantiles)
RUN_KEYS = ["patient_id", "seed", "mix"]


@dataclass
class BenchConfig:
    name: str
    simulation: str  # path to a SimConfig YAML (relative to the repository or absolute)
    sweep: str = "pisa"  # "pisa": PISA fraction = level, others at `severity`; "all": both = level
    levels: list[float] = field(default_factory=lambda: [0.0, 0.1, 0.25, 0.5, 0.75, 1.0])
    severity: float = 0.5  # other faults in the PISA sweep (SIMULATION.md §4.3)
    train_level: float | str = "realistic"  # PISA fraction for fitting and thresholds (D19)
    mixes: list[str] | None = None  # default: every mix in the cohort
    pisa_tau: float | None = None  # test-time PISA time constant (generator mismatch, D8)
    # CLINICAL-REVIEW: CR8 (the 6-min arm uses Basu 2013's healthy-adult lag)
    lag_tau_min: float | None = None  # rebuild the CGM with this blood-to-ISF lag (D1 arm)
    early_min: float = 30.0  # matching windows (D12 sensitivity analysis)
    late_min: float = 15.0
    cause_min: float = 30.0  # a fault active this long before a false alarm explains it (D10)
    near_after_min: float = 60.0  # near-event: within this long after a true low ends (D10)
    near_before_min: float = 60.0  # ... or up to this long before an onset (D10)
    label_horizon_min: float = 30.0  # training label: a low ongoing or starting within this
    refractory_min: float = 30.0  # minimum time between two alarms (BENCHMARK.md §1)
    sesoi: float = 0.75  # H2 smallest effect size of interest (RESEARCH.md §3)
    fault_seed: int = 0
    alarms: list[str] | str = "all"
    n_folds: int = 5
    delta: float = 0.0  # D5 non-inferiority margin
    n_boot: int = 2000
    fold_seed: int = 0
    workers: int = 1  # processes for the fold x mix fits and evaluations (results identical)
    pisa_fractions: list[float] | None = None  # deprecated alias of `levels`

    @classmethod
    def load(cls, path) -> BenchConfig:
        config = cls(**yaml.safe_load(Path(path).read_text()))
        if config.pisa_fractions is not None:
            config.levels = list(config.pisa_fractions)
        return config

    def fault_config(self, level: float, test: bool = True) -> FaultConfig:
        """Faults at a sweep level; training (test=False) keeps other faults at `severity` and the
        nominal PISA shape whatever the sweep (D19)."""
        if not test:
            return FaultConfig(pisa_fraction=level, severity=self.severity)
        tau = {"pisa_tau": self.pisa_tau} if self.pisa_tau else {}
        if self.sweep == "all":
            return FaultConfig(pisa_fraction=level, severity=level, **tau)
        return FaultConfig(pisa_fraction=level, severity=self.severity, **tau)


def is_learned(alarm: BaseAlarm) -> bool:
    """Learned alarms are fitted and get the pre-registered operating point (D5): the combiner
    arms, gbm and the gated alarms (`learned = True`); a user alarm opts in the same way."""
    return bool(getattr(alarm, "learned", False)) or any(tag in alarm.name for tag in LEARNED)


def select_alarms(names: list[str] | str) -> list[BaseAlarm]:
    """`all` is the pre-registered set; a list may also name the stretch alarms (RQ3)."""
    if names == "all":
        return benchmark_alarms(seed=0)
    known = benchmark_alarms(seed=0) + stretch_alarms()
    unknown = set(names) - {a.name for a in known}
    if unknown:
        raise ValueError(f"unknown alarm(s) in config: {sorted(unknown)}")
    return [a for a in known if a.name in names]


def alarm_frame(df: pd.DataFrame, alarm: BaseAlarm, with_label: bool = False) -> pd.DataFrame:
    v = view(df, "cgm_observed", context=alarm.uses_context)
    return v.assign(label=df["label"]) if with_label else v


def subset(df: pd.DataFrame, mix: str, patient_ids) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    return df[(df["mix"] == mix) & df["patient_id"].isin(patient_ids)]


def fire_and_score(alarm, frame, threshold, events, faults, observed, windows, scores=None):
    """Fire `alarm` and score it: (alarm events, classified alarms, per-event results)."""
    if scores is None:
        fired = alarm.alarms(frame, threshold)
    else:
        fired = alarm.alarms_from_scores(frame, scores, threshold)
    if fired.empty:
        fired = pd.DataFrame(columns=["time", "is_floor", *RUN_KEYS, "alarm_name"])
    fired["alarm_name"] = alarm.name
    labels = observed[[*RUN_KEYS, "time", "fault_type"]]
    classified = classify_alarms(fired, events, faults, labels, windows)
    scored = score_events(fired, events, windows)
    return fired, classified, scored


def training_threshold(
    alarm, frame, train_obs, events, faults, reference_sens, delta, windows, level: int = 2
):
    """Pre-registered rule on training patients (D5): sensitivity on lows of `level` (2, or 1 on
    CGM-referenced real data, amendment A5)."""
    scores = alarm.score(frame)
    days = run_hours(train_obs)["hours"].sum() / 24
    cache: dict[float, tuple[float, float]] = {}

    def evaluate(theta):
        if theta not in cache:
            _, cls, scored = fire_and_score(
                alarm, frame, theta, events, faults, train_obs, windows, scores=scores
            )
            l2 = scored[scored["level"] == level] if len(scored) else scored
            sens = float(l2["caught"].mean()) if len(l2) else float("nan")
            fpd = float((~cls["matched"]).sum() / days) if len(cls) else 0.0
            cache[theta] = (sens, fpd)
        return cache[theta]

    low = getattr(alarm, "candidate_low_quantile", 0.5)
    candidates = candidate_thresholds(scores.to_numpy(), n=N_CANDIDATES, low=low)
    theta, info = choose_threshold(
        candidates, lambda t: evaluate(t)[0], lambda t: evaluate(t)[1], reference_sens, delta
    )
    n_l2 = int((events["level"] == 2).sum())
    sens, fpd = evaluate(theta)
    info.update(
        l2_events=n_l2, estimable=n_l2 >= MIN_L2_EVENTS, train_sens=sens, train_false_per_day=fpd
    )
    return theta, info


def rebuild_cgm(samples: pd.DataFrame, truth: pd.DataFrame, tau_min: float) -> pd.DataFrame:
    """Replace the interstitial signal by plasma passed through a first-order lag (D1 arm)."""
    from ..sim.engine import first_order_lag

    truth_by_run = dict(tuple(truth.groupby(RUN_KEYS, sort=False)))
    out = []
    for key, s in samples.groupby(RUN_KEYS, sort=False):
        tr = truth_by_run[key]
        lagged = first_order_lag(tr["truth_glucose"].to_numpy(float), tau_min)
        isf = pd.Series(lagged, index=tr["time"].to_numpy()).reindex(s["time"].to_numpy())
        new = isf.to_numpy()
        out.append(s.assign(isf_glucose=new, glucose=np.clip(new + s["cgm_noise"], 40.0, 400.0)))
    return pd.concat(out, ignore_index=True)


def reference_sensitivity(train, events, faults, windows, level: int = 2) -> float:
    """Sensitivity of the CGM-only trend alarm on training patients (D5 reference), on lows of
    `level` (2; 1 on CGM-referenced real data, amendment A5)."""
    trend = TrendAlarm()
    _, _, ref = fire_and_score(
        trend, alarm_frame(train, trend), None, events, faults, train, windows
    )
    ref_l2 = ref[ref["level"] == level] if len(ref) else ref
    return float(ref_l2["caught"].mean()) if len(ref_l2) else float("nan")


def fit_fold(mix, fold, alarms, tr, tr_ev, tr_faults, delta, windows, train_level):
    """Fit and threshold every alarm for one mix and fold on its training patients (D5, D19).
    Returns ([(alarm, threshold)], threshold rows).

    D5 matches level 2 sensitivity; a fold with fewer than MIN_L2_EVENTS level 2 lows in its
    training patients matches level 1 sensitivity instead and is flagged (amendment A7)."""
    n_l2 = int((tr_ev["level"] == 2).sum()) if len(tr_ev) else 0
    level = 2 if n_l2 >= MIN_L2_EVENTS else 1
    reference = reference_sensitivity(tr, tr_ev, tr_faults, windows, level=level)
    entries, rows = [], []
    for alarm in alarms:  # a fresh copy per fold and mix: independent models
        threshold, info = alarm.default_threshold, {"feasible": True, "estimable": True}
        if is_learned(alarm):
            alarm.fit(alarm_frame(tr, alarm, with_label=True))
            threshold, info = training_threshold(
                alarm,
                alarm_frame(tr, alarm),
                tr,
                tr_ev,
                tr_faults,
                reference,
                delta,
                windows,
                level=level,
            )
        entries.append((alarm, threshold))
        rows.append(
            {
                "mix": mix,
                "fold": fold,
                "alarm_name": alarm.name,
                "threshold": threshold,
                "train_level": train_level,
                "match_level": level,
                "reference_sens": reference,
                "feasible": info.get("feasible"),
                "estimable": info.get("estimable"),
                "l2_events_train": info.get("l2_events"),
                "train_sens": info.get("train_sens"),
                "train_false_per_day": info.get("train_false_per_day"),
                "fitted": json.dumps(alarm.describe()) if hasattr(alarm, "describe") else "",
            }
        )
    return entries, rows


def evaluate_fold(entries, te, te_ev, te_faults, te_truth, fold, windows, level, pisa_fraction):
    """Per-run metrics of every frozen alarm of one mix and fold on its test patients."""
    hours = run_hours(te)
    frames = []
    for alarm, threshold in entries:
        fired, cls, scored = fire_and_score(
            alarm, alarm_frame(te, alarm), threshold, te_ev, te_faults, te, windows
        )
        m = per_run_metrics(cls, scored, hours, [alarm.name])
        fda = fda_rates(fired, te_truth, windows=windows)
        if len(fda):
            m = m.merge(fda, on=[*RUN_KEYS, "alarm_name"], how="left")
        frames.append(m.assign(level=level, pisa_fraction=pisa_fraction, fold=fold))
    return frames


def run_tasks(func, arg_iter, workers: int, kwargs: dict):
    """func(*args, **kwargs) for each args, results in order. With workers > 1 the tasks run in
    worker processes, at most 2 x workers in flight so that their inputs are built lazily."""
    if workers <= 1:
        for args in arg_iter:
            yield func(*args, **kwargs)
        return
    import multiprocessing
    from collections import deque
    from concurrent.futures import ProcessPoolExecutor

    # spawn, not fork: a forked child of a process that has started native thread pools
    # (OpenMP in scikit-learn's gradient boosting) can die abruptly on Linux
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        pending = deque()
        for args in arg_iter:
            pending.append(pool.submit(func, *args, **kwargs))
            if len(pending) >= 2 * workers:
                yield pending.popleft().result()
        while pending:
            yield pending.popleft().result()


def prepare(config: BenchConfig) -> dict:
    """The cohort, true lows, windows, folds and the faulted, labelled training data (D19) that a
    run of `config` uses; shared by the benchmark and the trade-off curves (amendment A11)."""
    from ..sim.run import SimConfig, load, run

    sim_path = Path(config.simulation)
    data = load(run(SimConfig.load(sim_path if sim_path.is_absolute() else REPO / sim_path)))
    samples, truth = data["samples"], data["truth"]
    if config.mixes:
        samples = samples[samples["mix"].isin(config.mixes)]
        truth = truth[truth["mix"].isin(config.mixes)]
    if config.lag_tau_min:
        samples = rebuild_cgm(samples, truth, config.lag_tau_min)
    events = true_events(truth)
    windows = Windows(
        early=config.early_min,
        late=config.late_min,
        cause=config.cause_min,
        after_event=config.near_after_min,
        before_event=config.near_before_min,
    )
    patients = samples["patient_id"].unique()
    folds = patient_folds(patients, min(config.n_folds, len(patients)), config.fold_seed)
    mixes = sorted(samples["mix"].unique())

    train_level, realistic = config.train_level, None
    if train_level == "realistic":
        base_mix = "default" if "default" in mixes else mixes[0]
        realistic = realistic_fraction(samples[samples["mix"] == base_mix], seed=config.fault_seed)
        # no complete nights (very short cohorts): train without PISAs
        train_level = realistic["fraction"] if np.isfinite(realistic["fraction"]) else 0.0
    train_config = config.fault_config(train_level, test=False)
    train_obs, train_faults = apply_faults(samples, train_config, seed=config.fault_seed)
    train_obs["label"] = low_labels(train_obs, events, horizon_min=config.label_horizon_min)
    return {
        "samples": samples,
        "truth": truth,
        "events": events,
        "windows": windows,
        "patients": patients,
        "folds": folds,
        "mixes": mixes,
        "train_level": train_level,
        "realistic": realistic,
        "train_obs": train_obs,
        "train_faults": train_faults,
    }


def run_benchmark(config: BenchConfig, out_dir: Path, extra_alarms=()) -> dict[str, pd.DataFrame]:
    """Run `config` (plus any user alarms in `extra_alarms`) and write the outputs to `out_dir`."""
    t0 = time.time()
    prep = prepare(config)
    samples, truth, events, windows = (prep[k] for k in ("samples", "truth", "events", "windows"))
    patients, folds, mixes = prep["patients"], prep["folds"], prep["mixes"]
    train_level, realistic = prep["train_level"], prep["realistic"]
    train_obs, train_faults = prep["train_obs"], prep["train_faults"]

    alarms_all = select_alarms(config.alarms) + list(extra_alarms)
    for alarm in alarms_all:
        alarm.refractory_min = config.refractory_min
    fold_ids = sorted(set(folds.values()))
    tasks = [(mix, fold) for mix in mixes for fold in fold_ids]

    # ---- fit once per fold and mix at the training level, then freeze (D19)
    def fit_args(mix, fold):
        ids = [p for p, f in folds.items() if f != fold]
        train = (subset(train_obs, mix, ids), subset(events, mix, ids))
        return (mix, fold, copy.deepcopy(alarms_all), *train, subset(train_faults, mix, ids))

    fit_kw = {"delta": config.delta, "windows": windows, "train_level": train_level}
    fitted, thresholds = {}, []
    for (mix, fold), (entries, rows) in zip(
        tasks,
        run_tasks(fit_fold, (fit_args(*t) for t in tasks), config.workers, fit_kw),
        strict=True,
    ):
        fitted[(mix, fold)] = entries
        thresholds += rows

    # ---- evaluate the frozen alarms across the sweep
    metrics = []
    for level in config.levels:
        test_config = config.fault_config(level)
        observed, faults = apply_faults(samples, test_config, seed=config.fault_seed)

        def eval_args(mix, fold, observed=observed, faults=faults):
            ids = [p for p, f in folds.items() if f == fold]
            return (
                fitted[(mix, fold)],
                subset(observed, mix, ids),
                subset(events, mix, ids),
                subset(faults, mix, ids),
                subset(truth, mix, ids),
            )

        eval_kw = {
            "windows": windows,
            "level": level,
            "pisa_fraction": test_config.pisa_fraction,
        }
        args = (eval_args(*t) + (t[1],) for t in tasks)
        for frames in run_tasks(evaluate_fold, args, config.workers, eval_kw):
            metrics += frames
    metrics_df = pd.concat(metrics, ignore_index=True)
    summary = summarise(metrics_df, config.n_boot)
    thresholds_df = pd.DataFrame(thresholds)
    extras = {
        "thresholds": thresholds_df,
        "contrasts_rq3": rq3_contrasts(metrics_df, thresholds_df, n_boot=config.n_boot),
        "contrasts_h2": context_contrasts(metrics_df, n_boot=config.n_boot, sesoi=config.sesoi),
        "contrast_h1": (
            h1_contrast(metrics_df, n_boot=config.n_boot)
            if len(config.levels) > 1
            else pd.DataFrame()
        ),
    }
    meta = {
        "realistic_pisa": realistic,
        "train_level": train_level,
        "leak_auc": {  # D3: IOB/COB at nocturnal true-low onsets vs. all night samples, per mix
            mix: {
                f: leak_auc(subset(samples, mix, patients), subset(events, mix, patients), f)
                for f in ("iob", "cob")
            }
            for mix in mixes
        },
        "seconds": round(time.time() - t0, 1),
        "patients": int(len(patients)),
        "runs": int(samples.groupby(RUN_KEYS).ngroups),
    }
    write_outputs(config, out_dir, metrics_df, summary, extras, meta)
    return {"metrics": metrics_df, "summary": summary, **extras, "meta": meta}


def per_patient(metrics: pd.DataFrame) -> pd.DataFrame:
    """Sum counts over a patient's runs (seeds), keeping alarm, fault level and mix."""
    count_cols = [
        c
        for c in metrics.columns
        if c.startswith(("n_", "false_", "events_l", "caught_l")) and not c.endswith("_per_day")
    ]
    keys = ["alarm_name", "level", "mix", "patient_id"]
    out = metrics.groupby(keys)[count_cols + ["hours"]].sum().reset_index()
    out["days"] = out["hours"] / 24
    return out


SUMMARY_RATES = {
    "sens_l1": ("caught_l1", "events_l1"),
    "sens_l2": ("caught_l2", "events_l2"),
    "false_per_day": ("n_false", "days"),
    **{f"false_{c}_per_day": (f"false_{c}", "days") for c in CAUSES},
    "floor_per_day": ("n_floor", "days"),
}


def summarise(metrics: pd.DataFrame, n_boot: int) -> pd.DataFrame:
    """Pooled rates with patient-bootstrap 95% CIs, per alarm x fault level x mix."""
    pp = per_patient(metrics)
    names = [n for n, (a, b) in SUMMARY_RATES.items() if a in pp and b in pp]
    rows = []
    for key, g in pp.groupby(["alarm_name", "level", "mix"]):
        row = dict(zip(["alarm_name", "level", "mix"], key, strict=True))
        row["patients"] = g["patient_id"].nunique()
        num = np.column_stack([g[SUMMARY_RATES[n][0]].to_numpy(float) for n in names])
        den = np.column_stack([g[SUMMARY_RATES[n][1]].to_numpy(float) for n in names])
        est, lo, hi = bootstrap_ratios(num, den, g["patient_id"].to_numpy(), n_boot=n_boot)
        for i, n in enumerate(names):
            row.update({n: est[i], f"{n}_lo": lo[i], f"{n}_hi": hi[i]})
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
            m = re.search(r"(?<!`)#\s*ASSUMPTION:\s*(.+)$", line)
            if not m:
                continue
            note, code = m.group(1).strip(), line[: m.start()].strip()
            if not code:  # comment block: join continuation lines, then the next code line
                j = i + 1
                while j < len(text) and text[j].strip().startswith("#") and ":" not in text[j][:20]:
                    note += " " + text[j].strip().lstrip("#").strip()
                    j += 1
                while j < len(text) and text[j].strip().startswith("#"):  # e.g. CLINICAL-REVIEW
                    j += 1
                code = text[j].strip() if j < len(text) else ""
            where = f"{path.relative_to(REPO)}:{i + 1}"
            lines.append(f"- `{where}` `{code[:80]}`: {note}" if code else f"- `{where}`: {note}")
    return "\n".join(lines) + "\n"


def write_outputs(config, out_dir: Path, metrics, summary, extras: dict, meta: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "figures").mkdir(exist_ok=True)
    metrics.to_csv(out_dir / "metrics.csv", index=False)
    summary.to_csv(out_dir / "summary.csv", index=False)
    for name, frame in extras.items():
        frame.to_csv(out_dir / f"{name}.csv", index=False)
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
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, default=float) + "\n")
    ids = pd.Series(metrics["patient_id"].unique())
    groups = ids.map(age_group).value_counts().to_dict()
    (out_dir / "README.txt").write_text(
        f"{BENCHMARK_VERSION} run '{config.name}': {len(ids)} patients {groups}, "
        f"{metrics['alarm_name'].nunique()} alarms, {config.sweep} sweep, "
        f"levels {list(config.levels)}.\n"
    )
