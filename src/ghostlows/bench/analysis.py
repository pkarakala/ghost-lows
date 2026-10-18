"""Pre-registered contrasts for H1-H2 (RESEARCH.md §3, D6) and the exploratory RQ3 contrasts.

H2: rate ratio of compression false alarms per night, [CGM + time + IOB/COB] over [CGM + time],
per detector and scenario mix, with a paired patient bootstrap (same patients, faults and seeds
in both arms). H1: per-patient least-squares slope of false alarms per day against the fraction
of compressed nights, trend minus threshold. RQ3 (amendment A3): each Kalman alarm against the
discriminative alarm with the same inputs that had the fewest false alarms on the training
patients of each fold, plus the two ablations of the Kalman filter.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .stats import bootstrap_ci

SESOI_RATE_RATIO = 0.75  # ASSUMPTION: smallest effect size of interest for H2 (CR9, CR16)
CONTEXT_ARM, BASE_ARM = "_combined_time_ctx", "_combined_time"


def h2_reading(estimate: float, lo: float, hi: float, sesoi: float = SESOI_RATE_RATIO) -> str:
    """The pre-registered reading of a rate ratio and its CI (RESEARCH.md §3)."""
    if not np.isfinite(estimate):
        return "not estimable"
    if hi < 1 and estimate <= sesoi:
        return "meaningful reduction"
    if lo > sesoi:
        return "no meaningful reduction"
    return "inconclusive"


def context_contrasts(
    metrics: pd.DataFrame, n_boot: int = 2000, cause: str = "compression"
) -> pd.DataFrame:
    """H2 rate ratios per detector x fault level x mix, paired over patients."""
    col = f"false_{cause}" if cause else "n_false"
    rows = []
    detectors = sorted(
        {n[: -len(CONTEXT_ARM)] for n in metrics["alarm_name"] if n.endswith(CONTEXT_ARM)}
    )
    for det in detectors:
        a, b = det + CONTEXT_ARM, det + BASE_ARM
        sub = metrics[metrics["alarm_name"].isin([a, b])]
        for key, g in sub.groupby(["level", "mix"]):
            pp = g.pivot_table(
                index="patient_id", columns="alarm_name", values=col, aggfunc="sum"
            ).reset_index()
            if a not in pp or b not in pp:
                continue

            def ratio(df, a=a, b=b):
                den = df[b].sum()
                return float(df[a].sum() / den) if den > 0 else float("nan")

            est, lo, hi = bootstrap_ci(pp, ratio, n_boot=n_boot)
            rows.append(
                {
                    "detector": det,
                    "level": key[0],
                    "mix": key[1],
                    "cause": cause or "all",
                    "count_context": float(pp[a].sum()),
                    "count_base": float(pp[b].sum()),
                    "rate_ratio": est,
                    "lo": lo,
                    "hi": hi,
                    "reading": h2_reading(est, lo, hi),
                }
            )
    columns = [
        "detector",
        "level",
        "mix",
        "cause",
        "count_context",
        "count_base",
        "rate_ratio",
        "lo",
        "hi",
        "reading",
    ]
    return pd.DataFrame(rows, columns=columns)


def severity_slopes(metrics: pd.DataFrame, rate: str = "false_per_day") -> pd.DataFrame:
    """Per patient and alarm: least-squares slope of `rate` against the fault level (H1)."""
    rows = []
    agg = metrics.groupby(["alarm_name", "mix", "patient_id", "level"])[[rate]].mean().reset_index()
    for (alarm, mix, pid), g in agg.groupby(["alarm_name", "mix", "patient_id"]):
        if g["level"].nunique() < 2:
            continue
        slope = np.polyfit(g["level"].to_numpy(float), g[rate].to_numpy(float), 1)[0]
        rows.append({"alarm_name": alarm, "mix": mix, "patient_id": pid, "slope": slope})
    return pd.DataFrame(rows)


def h1_contrast(
    metrics: pd.DataFrame, n_boot: int = 2000, a: str = "trend", b: str = "threshold"
) -> pd.DataFrame:
    """Median paired slope difference (a - b) per mix with a patient bootstrap CI."""
    slopes = severity_slopes(metrics)
    rows = []
    for mix, g in slopes.groupby("mix"):
        wide = g.pivot_table(index="patient_id", columns="alarm_name", values="slope").reset_index()
        if a not in wide or b not in wide:
            continue
        wide["diff"] = wide[a] - wide[b]
        est, lo, hi = bootstrap_ci(wide, lambda df: float(np.median(df["diff"])), n_boot=n_boot)
        rows.append(
            {
                "mix": mix,
                "contrast": f"{a} - {b}",
                "median_slope_diff": est,
                "lo": lo,
                "hi": hi,
                "supported": bool(lo > 1e-9),  # strictly above 0, not a rounding epsilon
            }
        )
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ RQ3 (exploratory, A3)

RQ3_MODELS = {"kalman_pisa": "_ctx", "kalman_nopisa": "_ctx", "kalman_pisa_cgm": ""}
RQ3_ABLATIONS = {
    "compressed state": ("kalman_pisa", "kalman_nopisa"),
    "insulin and carb inputs": ("kalman_pisa", "kalman_pisa_cgm"),
}
RQ3_COUNTS = ["n_false", "false_compression", "caught_l2", "events_l2"]


def discriminative_pool(names, inputs: str) -> list[str]:
    """Discriminative alarms with the given inputs ('' = CGM only, '_ctx' = CGM + IOB/COB, no
    time of day): the five combiner arms and gbm."""
    return sorted(n for n in set(names) if n.endswith("_combined" + inputs) or n == "gbm" + inputs)


def select_comparators(thresholds: pd.DataFrame, pool: list[str]) -> pd.DataFrame:
    """Per mix and fold, the pool alarm with the fewest training false alarms per day at its
    operating point, among those meeting the D5 sensitivity constraint (all if none does);
    ties go to the higher training sensitivity, then the name. Test results are not used."""
    t = thresholds[thresholds["alarm_name"].isin(pool)].copy()
    rows = []
    for (mix, fold), g in t.groupby(["mix", "fold"]):
        ok = g[g["feasible"].astype(bool)] if g["feasible"].astype(bool).any() else g
        best = ok.sort_values(
            ["train_false_per_day", "train_sens_l2", "alarm_name"], ascending=[True, False, True]
        ).iloc[0]
        rows.append({"mix": mix, "fold": fold, "comparator": best["alarm_name"]})
    return pd.DataFrame(rows, columns=["mix", "fold", "comparator"])


def _paired(metrics: pd.DataFrame, a: pd.DataFrame, b: pd.DataFrame, n_boot: int) -> list[dict]:
    """Ratios of false alarms (all, compression) and the difference in level 2 sensitivity,
    a versus b, per fault level and mix, with a paired patient bootstrap."""
    keys = ["level", "mix", "patient_id"]
    pa = a.groupby(keys)[RQ3_COUNTS].sum().add_suffix("_a")
    pb = b.groupby(keys)[RQ3_COUNTS].sum().add_suffix("_b")
    both = pa.join(pb, how="inner").reset_index()

    def ratio(col):
        def f(df):
            den = df[f"{col}_b"].sum()
            return float(df[f"{col}_a"].sum() / den) if den > 0 else float("nan")

        return f

    def sens_diff(df):
        ea, eb = df["events_l2_a"].sum(), df["events_l2_b"].sum()
        if ea == 0 or eb == 0:
            return float("nan")
        return float(df["caught_l2_a"].sum() / ea - df["caught_l2_b"].sum() / eb)

    rows = []
    for (level, mix), g in both.groupby(["level", "mix"]):
        g = g.drop(columns=["level", "mix"])
        for measure, stat in (
            ("false alarms, ratio", ratio("n_false")),
            ("compression false alarms, ratio", ratio("false_compression")),
            ("level 2 sensitivity, difference", sens_diff),
        ):
            est, lo, hi = bootstrap_ci(g, stat, n_boot=n_boot)
            rows.append(
                {
                    "level": level,
                    "mix": mix,
                    "measure": measure,
                    "estimate": est,
                    "lo": lo,
                    "hi": hi,
                }
            )
    return rows


def rq3_contrasts(
    metrics: pd.DataFrame, thresholds: pd.DataFrame, n_boot: int = 2000
) -> pd.DataFrame:
    """Exploratory RQ3 contrasts (amendment A3): Kalman alarm versus the training-selected best
    discriminative alarm with the same inputs, and the Kalman ablations. Empty without Kalman
    alarms."""
    columns = ["contrast", "a", "b", "level", "mix", "measure", "estimate", "lo", "hi"]
    names = set(metrics["alarm_name"])
    rows = []
    for model, inputs in RQ3_MODELS.items():
        pool = discriminative_pool(names, inputs)
        if model not in names or not pool or "train_false_per_day" not in thresholds:
            continue
        chosen = select_comparators(thresholds, pool)
        b = metrics.merge(
            chosen.rename(columns={"comparator": "alarm_name"}), on=["mix", "fold", "alarm_name"]
        )
        picks = "; ".join(f"{k}: {v}" for k, v in chosen["comparator"].value_counts().items())
        for r in _paired(metrics, metrics[metrics["alarm_name"] == model], b, n_boot):
            rows.append(
                {
                    "contrast": "versus best discriminative",
                    "a": model,
                    "b": f"best of {inputs or 'CGM-only'} pool ({picks})",
                    **r,
                }
            )
    for label, (a, b) in RQ3_ABLATIONS.items():
        if a in names and b in names:
            for r in _paired(
                metrics,
                metrics[metrics["alarm_name"] == a],
                metrics[metrics["alarm_name"] == b],
                n_boot,
            ):
                rows.append({"contrast": f"ablation: {label}", "a": a, "b": b, **r})
    return pd.DataFrame(rows, columns=columns)
