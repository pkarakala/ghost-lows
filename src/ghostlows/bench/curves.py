"""Trade-off curves (amendment A11; D5 and BENCHMARK.md §4). Secondary and post hoc.

Per fold and scenario mix the alarms are fitted on the training patients exactly as in the
benchmark (D19). Every candidate threshold is scored on the training patients (level 2
sensitivity, false alarms per day) and on the held-out patients at one test fault level. The
curve point at retention r takes, in each fold, the threshold that the D5 rule picks with the
constraint "training level 2 sensitivity >= r x the trend alarm's"; r = 1 is the pre-registered
delta = 0 operating point. Test counts are pooled over held-out patients, with patient-bootstrap
CIs. The pre-registered H2 test stays the delta = 0 result; these curves never replace it.
"""

from __future__ import annotations

import copy
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ..faults import apply_faults
from .analysis import BASE_ARM, CONTEXT_ARM, GBM_ARMS, context_contrasts, h2_reading
from .pipeline import (
    N_CANDIDATES,
    BenchConfig,
    alarm_frame,
    fire_and_score,
    is_learned,
    per_run_metrics,
    prepare,
    reference_sensitivity,
    run_hours,
    run_tasks,
    select_alarms,
    subset,
)
from .stats import (
    MIN_L2_EVENTS,
    bootstrap_ci,
    bootstrap_ratios,
    candidate_thresholds,
    choose_threshold,
)

# ASSUMPTION: retention grid of amendment A11 (training sensitivity as a fraction of the trend
# alarm's, 0.50 to 1.00 in steps of 0.01)
RETENTIONS = tuple(round(r, 2) for r in np.arange(0.50, 1.0 + 1e-9, 0.01))
MARKED = (0.95, 0.99, 1.0)  # the points marked on the curves (amendment A11)
PUBLISHED = ("threshold", "trend")  # rule alarms: their published threshold is also a candidate
GATES = ("baysal_gate", "matched_filter_causal_gate", "iforest_causal_gate")
DETECTORS = ("threshold", "trend", "baysal", "matched_filter_causal", "iforest_causal")
# (family, CGM arm, context arm): the H2 pairs, then the Kalman pair (exploratory, A3)
PAIRS = [(d, d + BASE_ARM, d + CONTEXT_ARM) for d in DETECTORS]
PAIRS += [("gbm", GBM_ARMS[1], GBM_ARMS[0]), ("kalman", "kalman_pisa_cgm", "kalman_pisa")]
COUNTS = ["caught_l2", "events_l2", "n_false", "false_compression", "hours"]


def curve_fold(mix, fold, alarms, tr, tr_ev, tr_faults, te, te_ev, te_faults, windows):
    """Per candidate threshold of every alarm: training sensitivity and false alarms per day, and
    per held-out patient counts at the test fault level. One row per alarm x candidate x patient.
    """
    n_l2 = int((tr_ev["level"] == 2).sum()) if len(tr_ev) else 0
    level = 2 if n_l2 >= MIN_L2_EVENTS else 1  # as fit_fold (amendment A7)
    reference = reference_sensitivity(tr, tr_ev, tr_faults, windows, level=level)
    train_days = run_hours(tr)["hours"].sum() / 24
    te_hours = run_hours(te)
    rows = []
    for alarm in alarms:
        if is_learned(alarm):
            alarm.fit(alarm_frame(tr, alarm, with_label=True))
        tr_frame, te_frame = alarm_frame(tr, alarm), alarm_frame(te, alarm)
        tr_scores, te_scores = alarm.score(tr_frame), alarm.score(te_frame)
        low = getattr(alarm, "candidate_low_quantile", 0.5)
        candidates = candidate_thresholds(tr_scores.to_numpy(), n=N_CANDIDATES, low=low)
        if alarm.name in PUBLISHED:
            candidates = np.unique(np.r_[candidates, alarm.default_threshold])
        for theta in candidates:
            _, cls, scored = fire_and_score(
                alarm, tr_frame, theta, tr_ev, tr_faults, tr, windows, scores=tr_scores
            )
            lows = scored[scored["level"] == level] if len(scored) else scored
            sens = float(lows["caught"].mean()) if len(lows) else float("nan")
            fpd = float((~cls["matched"]).sum() / train_days) if len(cls) else 0.0
            _, cls, scored = fire_and_score(
                alarm, te_frame, theta, te_ev, te_faults, te, windows, scores=te_scores
            )
            m = per_run_metrics(cls, scored, te_hours, [alarm.name])
            m = m.reindex(columns=[*m.columns.difference(COUNTS), *COUNTS], fill_value=0)
            pp = m.groupby("patient_id")[COUNTS].sum().reset_index()
            rows.append(
                pp.assign(
                    mix=mix,
                    fold=fold,
                    alarm_name=alarm.name,
                    threshold=float(theta),
                    published=bool(
                        alarm.name in PUBLISHED and np.isclose(theta, alarm.default_threshold)
                    ),
                    train_sens=sens,
                    train_false_per_day=fpd,
                    reference_sens=reference,
                    match_level=level,
                )
            )
    return pd.concat(rows, ignore_index=True)


def run_curves(config: BenchConfig, out_dir: Path, test_level: float = 1.0) -> pd.DataFrame:
    """Score every candidate threshold of `config.alarms` (amendment A11) and write
    `points.csv`: training rates per candidate and held-out counts per patient."""
    t0 = time.time()
    prep = prepare(config)
    alarms = select_alarms(config.alarms)
    for alarm in alarms:
        alarm.refractory_min = config.refractory_min
    test_config = config.fault_config(test_level)
    observed, faults = apply_faults(prep["samples"], test_config, seed=config.fault_seed)
    folds, events = prep["folds"], prep["events"]
    tasks = [(mix, f) for mix in prep["mixes"] for f in sorted(set(folds.values()))]

    def args(mix, fold):
        train = [p for p, f in folds.items() if f != fold]
        test = [p for p, f in folds.items() if f == fold]
        return (
            mix,
            fold,
            copy.deepcopy(alarms),
            subset(prep["train_obs"], mix, train),
            subset(events, mix, train),
            subset(prep["train_faults"], mix, train),
            subset(observed, mix, test),
            subset(events, mix, test),
            subset(faults, mix, test),
        )

    kw = {"windows": prep["windows"]}
    points = pd.concat(
        run_tasks(curve_fold, (args(*t) for t in tasks), config.workers, kw), ignore_index=True
    )
    points["test_level"] = test_level
    points["train_level"] = prep["train_level"]
    out_dir.mkdir(parents=True, exist_ok=True)
    points.to_csv(out_dir / "points.csv", index=False)
    print(f"curves: {len(points)} rows in {time.time() - t0:.0f} s", flush=True)
    return points


# ------------------------------------------------------------------ analysis of the points


def choices(points: pd.DataFrame, retentions=RETENTIONS) -> pd.DataFrame:
    """Per mix, fold, alarm and retention r: the candidate the D5 rule picks with reference
    r x the trend alarm's training sensitivity (r = 1: the pre-registered operating point), plus
    the published threshold of the rule alarms (r = NaN, point 'published')."""
    cand = points.drop_duplicates(["mix", "fold", "alarm_name", "threshold"])
    rows = []
    for (mix, fold, name), g in cand.groupby(["mix", "fold", "alarm_name"]):
        table = g.set_index("threshold")
        ref = float(table["reference_sens"].iloc[0])
        for r in retentions:
            theta, info = choose_threshold(
                table.index.to_numpy(),
                lambda t, tb=table: tb.at[t, "train_sens"],
                lambda t, tb=table: tb.at[t, "train_false_per_day"],
                r * ref,
            )
            rows.append(
                {
                    "mix": mix,
                    "fold": fold,
                    "alarm_name": name,
                    "point": f"r={r:.2f}",
                    "retention": r,
                    "threshold": theta,
                    "feasible": info["feasible"],
                    "train_sens": table.at[theta, "train_sens"],
                    "train_false_per_day": table.at[theta, "train_false_per_day"],
                    "reference_sens": ref,
                }
            )
        published = g[g["published"].astype(bool)]
        if len(published):
            theta = float(published["threshold"].iloc[0])
            rows.append(
                {
                    "mix": mix,
                    "fold": fold,
                    "alarm_name": name,
                    "point": "published",
                    "retention": np.nan,
                    "threshold": theta,
                    "feasible": np.nan,
                    "train_sens": table.at[theta, "train_sens"],
                    "train_false_per_day": table.at[theta, "train_false_per_day"],
                    "reference_sens": ref,
                }
            )
    return pd.DataFrame(rows)


def per_patient_at(points: pd.DataFrame, chosen: pd.DataFrame) -> pd.DataFrame:
    """Held-out counts per patient at each chosen threshold (each patient is in one test fold)."""
    keys = ["mix", "fold", "alarm_name", "threshold"]
    cols = [*keys, "point", "retention", "train_sens", "train_false_per_day", "reference_sens"]
    out = chosen[cols].merge(points[[*keys, "patient_id", *COUNTS]], on=keys, how="left")
    out["false_other"] = out["n_false"] - out["false_compression"]
    out["days"] = out["hours"] / 24
    return out.sort_values(["alarm_name", "mix", "point", "patient_id"]).reset_index(drop=True)


CURVE_RATES = {
    "sens_l2": ("caught_l2", "events_l2"),
    "false_per_day": ("n_false", "days"),
    "false_compression_per_day": ("false_compression", "days"),
    "false_other_per_day": ("false_other", "days"),
}


def curve_summary(pp: pd.DataFrame, n_boot: int = 2000) -> pd.DataFrame:
    """Pooled held-out rates per alarm, mix and point, with patient-bootstrap 95% CIs."""
    rows = []
    for (name, mix, point), g in pp.groupby(["alarm_name", "mix", "point"]):
        num = np.column_stack([g[a].to_numpy(float) for a, _ in CURVE_RATES.values()])
        den = np.column_stack([g[b].to_numpy(float) for _, b in CURVE_RATES.values()])
        est, lo, hi = bootstrap_ratios(num, den, g["patient_id"].to_numpy(), n_boot=n_boot)
        folds = g.drop_duplicates("fold")
        row = {
            "alarm_name": name,
            "mix": mix,
            "point": point,
            "retention": g["retention"].iloc[0],
            "train_sens": folds["train_sens"].mean(),  # mean over folds
            "train_sens_loss": (folds["reference_sens"] - folds["train_sens"]).mean(),
            "patients": g["patient_id"].nunique(),
            "events_l2": g["events_l2"].sum(),
            "caught_l2": g["caught_l2"].sum(),
        }
        for i, n in enumerate(CURVE_RATES):
            row.update({n: est[i], f"{n}_lo": lo[i], f"{n}_hi": hi[i]})
        rows.append(row)
    return pd.DataFrame(rows)


def first_reduction(pp: pd.DataFrame, alarms, n_boot: int = 2000) -> pd.DataFrame:
    """Per alarm and mix: the largest r below 1 at which held-out compression false alarms per
    day are lower than at r = 1 with a paired patient-bootstrap CI of the ratio below 1, and the
    cost there (paired difference in level 2 sensitivity; extra missed level 2 lows)."""
    rows = []
    sweep = pp[pp["retention"].notna()]
    for (name, mix), g in sweep[sweep["alarm_name"].isin(alarms)].groupby(["alarm_name", "mix"]):
        wide = g.pivot_table(
            index="patient_id",
            columns="retention",
            values=["false_compression", "caught_l2", "events_l2"],
            aggfunc="sum",
        )
        rs = sorted((r for r in wide["false_compression"].columns if r < 1.0), reverse=True)
        fc, caught = wide["false_compression"], wide["caught_l2"]
        events = wide["events_l2"][1.0].to_numpy(float)
        # ratio of compression false alarms (r vs 1) and sensitivity difference: ratios of sums
        num = np.column_stack(
            [fc[r].to_numpy(float) for r in rs] + [(caught[r] - caught[1.0]).to_numpy() for r in rs]
        )
        den = np.column_stack([fc[1.0].to_numpy(float)] * len(rs) + [events] * len(rs))
        est, lo, hi = bootstrap_ratios(num, den, wide.index.to_numpy(), n_boot=n_boot)
        k = len(rs)
        hit = [i for i in range(k) if hi[i] < 1]
        row = {
            "alarm_name": name,
            "mix": mix,
            "compression_at_r1": float(fc[1.0].sum()),
            "events_l2": float(events.sum()),
        }
        if hit:
            i = hit[0]
            row.update(
                retention=rs[i],
                compression_ratio=est[i],
                compression_ratio_lo=lo[i],
                compression_ratio_hi=hi[i],
                sens_l2_diff=est[k + i],
                sens_l2_diff_lo=lo[k + i],
                sens_l2_diff_hi=hi[k + i],
                extra_missed_l2=float((caught[1.0] - caught[rs[i]]).sum()),
            )
        else:
            row["retention"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def h2_on_curves(pp: pd.DataFrame, n_boot: int = 2000, sesoi: float = 0.75) -> pd.DataFrame:
    """H2 restated at the marked points (secondary): context over CGM arm rate ratio of held-out
    compression false alarms per detector, paired over patients, read with the H2 rule. The six
    H2 detectors use the benchmark's own contrast code; the Kalman pair (exploratory) the same
    bootstrap."""
    marked = pp[pp["retention"].isin(MARKED)]
    frame = marked.assign(level=marked["retention"])
    h2 = context_contrasts(frame, n_boot=n_boot, sesoi=sesoi).rename(columns={"level": "retention"})
    rows = []
    a, b = "kalman_pisa", "kalman_pisa_cgm"
    for (r, mix), g in frame[frame["alarm_name"].isin([a, b])].groupby(["level", "mix"]):
        w = g.pivot_table(
            index="patient_id", columns="alarm_name", values="false_compression", aggfunc="sum"
        ).reset_index()
        if a not in w or b not in w:
            continue

        def ratio(df):
            den = df[b].sum()
            return float(df[a].sum() / den) if den > 0 else float("nan")

        est, lo, hi = bootstrap_ci(w, ratio, n_boot=n_boot)
        rows.append(
            {
                "detector": "kalman",
                "retention": r,
                "mix": mix,
                "cause": "compression",
                "count_context": float(w[a].sum()),
                "count_base": float(w[b].sum()),
                "rate_ratio": est,
                "lo": lo,
                "hi": hi,
                "reading": h2_reading(est, lo, hi, sesoi),
            }
        )
    return pd.concat([h2, pd.DataFrame(rows, columns=h2.columns)], ignore_index=True)
