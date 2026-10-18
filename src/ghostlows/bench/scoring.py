"""Alarm scoring per patient-run (BENCHMARK.md §4, D10, D12).

Inputs are alarm events (`ghostlows.alarms`), true low events (`events.true_events`), fault
instances (`ghostlows.faults.apply_faults`) and per-sample fault labels. Everything is computed
per run (patient, seed, mix) and per alarm, then aggregated across patients elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

RUN_KEYS = ("patient_id", "seed", "mix")


# ASSUMPTION: matching and attribution windows (D10, D12); early/late are swept in robustness arms
@dataclass(frozen=True)
class Windows:
    """Matching and attribution windows, in minutes (BENCHMARK.md §4)."""

    early: float = 30.0  # an alarm up to this long before onset catches the event
    late: float = 15.0  # ... or up to this long after onset
    cause: float = 30.0  # a fault active in [t - cause, t] explains a false alarm
    after_event: float = 60.0  # "near-event": within this long after a true low ends
    before_event: float = 60.0  # ... or between `early` and this long before an onset
    fda: float = 15.0  # SOURCE: 21 CFR 862.1355 (alert evaluated within 15 min of a reference)
    fda_reference_every: float = 15.0  # ASSUMPTION: reference sampling like YSI every 15 min


DEFAULT_WINDOWS = Windows()


def _minutes(values) -> np.ndarray:
    return pd.DatetimeIndex(values).as_unit("ns").asi8 / 6e10


def classify_alarms(
    alarms: pd.DataFrame,
    events: pd.DataFrame,
    faults: pd.DataFrame,
    labels: pd.DataFrame | None,
    windows: Windows = DEFAULT_WINDOWS,
) -> pd.DataFrame:
    """One row per alarm with `matched` (true low), `cause` of unmatched alarms and the onset.

    Alarms are matched against level 1 events: the first event with alarm time in
    [onset - early, end] (D12). Unmatched alarms are attributed (D10): compression if a PISA was
    active in [t - cause, t], else another fault (sample labels), else near-event, else noise.
    Vectorised per run with sorted searches.
    """
    keys = [k for k in RUN_KEYS if k in alarms]
    if alarms.empty:
        return alarms.assign(
            matched=pd.Series(dtype=bool),
            cause=pd.Series(dtype=object),
            event_onset_min=pd.Series(dtype=float),
        )
    level1 = events[events["level"] == 1] if len(events) else events
    ev_by = _by_run(level1, keys)
    pisa_by = _by_run(faults[faults["fault_type"] == "pisa"], keys) if len(faults) else {}
    other_by = {}
    if labels is not None and len(labels):
        other_by = _by_run(labels[~labels["fault_type"].isin(["none", "pisa"])], keys)
    out = []
    for key, a in alarms.groupby(keys, sort=False):
        key = key if isinstance(key, tuple) else (key,)
        t = _minutes(a["time"])
        ev = ev_by.get(key)
        on = np.sort(_minutes(ev["onset"])) if ev is not None else np.array([])
        end = (
            _minutes(ev["end"])[np.argsort(_minutes(ev["onset"]))]
            if ev is not None
            else np.array([])
        )
        matched = np.zeros(len(t), bool)
        onset_of = np.full(len(t), np.nan)
        if on.size:
            # earliest event whose window [onset - early, end] contains t
            first = np.searchsorted(end, t, side="left")  # events ending at or after t
            ok = first < on.size
            idx = np.where(ok, first, 0)
            hit = ok & (on[idx] - windows.early <= t)
            matched, onset_of = hit, np.where(hit, on[idx], np.nan)
        cause = np.full(len(t), "", dtype=object)
        free = ~matched
        compression = np.zeros(len(t), bool)
        p = pisa_by.get(key)
        if p is not None and len(p):
            order = np.argsort(_minutes(p["start"]))
            starts = _minutes(p["start"])[order]
            reach = np.maximum.accumulate(_minutes(p["end"])[order])
            j = np.searchsorted(starts, t, side="right") - 1
            compression = (j >= 0) & (reach[np.clip(j, 0, None)] >= t - windows.cause)
        other = np.zeros(len(t), bool)
        o = other_by.get(key)
        if o is not None and len(o):
            o_t = np.sort(_minutes(o["time"]))
            other = np.searchsorted(o_t, t, side="right") > np.searchsorted(
                o_t, t - windows.cause, side="left"
            )
        near = np.zeros(len(t), bool)
        if on.size:
            ends = np.sort(end)
            k = np.searchsorted(ends, t, side="left") - 1  # last event ending before t
            near |= (k >= 0) & (t - ends[np.clip(k, 0, None)] <= windows.after_event)
            near |= np.searchsorted(on, t + windows.early, side="right") < np.searchsorted(
                on, t + windows.before_event, side="right"
            )
        cause[free & compression] = "compression"
        cause[free & ~compression & other] = "other_fault"
        cause[free & ~compression & ~other & near] = "near_event"
        cause[free & ~compression & ~other & ~near] = "noise"
        out.append(a.assign(matched=matched, cause=cause, event_onset_min=onset_of))
    return pd.concat(out, ignore_index=True)


def _by_run(df: pd.DataFrame, keys: list[str]) -> dict:
    """Rows of `df` grouped by run key (missing key columns match any run)."""
    if df is None or df.empty:
        return {}
    present = [k for k in keys if k in df]
    if present != keys:
        raise ValueError(f"table lacks run keys {sorted(set(keys) - set(present))}")
    return {k if isinstance(k, tuple) else (k,): g for k, g in df.groupby(keys, sort=False)}


def _select(df: pd.DataFrame, sel: dict) -> pd.DataFrame:
    mask = np.ones(len(df), bool)
    for k, v in sel.items():
        if k in df:
            mask &= (df[k] == v).to_numpy()
    return df[mask]


def score_events(
    alarms: pd.DataFrame, events: pd.DataFrame, windows: Windows = DEFAULT_WINDOWS
) -> pd.DataFrame:
    """Per true event and alarm: caught, warning time and late announcement.

    Caught = an alarm in [onset - early, onset + late]. Warning = onset - first catching alarm
    (minutes, positive means before onset). For events not caught by a non-floor alarm, `late_min`
    is the time from onset to the first alarm of any kind within the event (D4).
    """
    keys = [k for k in RUN_KEYS if k in events]
    names = list(alarms["alarm_name"].unique()) if len(alarms) else []
    a_by = _by_run(alarms, keys) if len(alarms) else {}
    rows = []
    for key, ev in events.groupby(keys, sort=False):
        key = key if isinstance(key, tuple) else (key,)
        sel = dict(zip(keys, key, strict=True))
        on, end = _minutes(ev["onset"]), _minutes(ev["end"])
        run_alarms = a_by.get(key)
        for name in names:
            if run_alarms is not None:
                a = run_alarms[run_alarms["alarm_name"] == name]
                order = np.argsort(_minutes(a["time"]))
                t = _minutes(a["time"])[order]
                floor = a["is_floor"].to_numpy(bool)[order]
            else:
                t, floor = np.array([]), np.array([], bool)
            tn = t[~floor]
            lo = np.searchsorted(t, on - windows.early, side="left")
            hi = np.searchsorted(t, on + windows.late, side="right")
            caught = hi > lo
            warning = np.where(
                caught, on - t[np.clip(lo, 0, max(len(t) - 1, 0))] if len(t) else np.nan, np.nan
            )
            nf = np.searchsorted(tn, on + windows.late, side="right") > np.searchsorted(
                tn, on - windows.early, side="left"
            )
            first = np.searchsorted(t, on, side="left")
            has = first < len(t)
            first_t = (
                t[np.clip(first, 0, max(len(t) - 1, 0))] if len(t) else np.full(len(on), np.inf)
            )
            in_event = has & (first_t <= end)
            late = np.where(~nf & in_event, first_t - on, np.nan)
            rows.append(
                pd.DataFrame(
                    {
                        **sel,
                        "alarm_name": name,
                        "level": ev["level"].to_numpy(),
                        "onset": ev["onset"].to_numpy(),
                        "caught": caught,
                        "warning_min": warning,
                        "late_min": late,
                    }
                )
            )
    return (
        pd.concat(rows, ignore_index=True)
        if rows
        else pd.DataFrame(
            columns=keys + ["alarm_name", "level", "onset", "caught", "warning_min", "late_min"]
        )
    )


def fda_rates(
    alarms: pd.DataFrame,
    truth: pd.DataFrame,
    threshold: float = 70.0,  # SOURCE: IHSG 2017 CLINICAL-REVIEW: CR6
    windows: Windows = DEFAULT_WINDOWS,
) -> pd.DataFrame:
    """True alert rate and detection rate against reference glucose (iCGM style, BENCHMARK.md §4).

    True alert: reference below `threshold` within +/- fda minutes of the alert. Detection: a
    reference value below `threshold`, taken every `fda_reference_every` minutes, has an alert
    within +/- fda minutes. SOURCE: 21 CFR 862.1355; FDA K212132
    """
    rows = []
    keys = [k for k in RUN_KEYS if k in truth]
    for key, tr in truth.groupby(keys, sort=False):
        key = key if isinstance(key, tuple) else (key,)
        sel = dict(zip(keys, key, strict=True))
        tt = _minutes(tr["time"])
        g = tr["truth_glucose"].to_numpy(float)
        spacing = float(np.median(np.diff(tt))) if len(tt) > 1 else 1.0  # 1 min sim, 5 min real
        step = max(1, int(round(windows.fda_reference_every / spacing)))
        ref_t, ref_low = tt[::step], g[::step] < threshold
        low_t = tt[g < threshold]
        for name, a in _select(alarms, sel).groupby("alarm_name"):
            at = _minutes(a["time"])
            true_alert = (
                np.array([np.any(np.abs(low_t - x) <= windows.fda) for x in at])
                if at.size
                else np.array([])
            )
            detected = np.array([np.any(np.abs(at - x) <= windows.fda) for x in ref_t[ref_low]])
            rows.append(
                {
                    **sel,
                    "alarm_name": name,
                    "n_alerts": int(at.size),
                    "n_true_alerts": int(true_alert.sum()),
                    "n_reference_lows": int(ref_low.sum()),
                    "n_detected": int(detected.sum()),
                }
            )
    return pd.DataFrame(rows)


def run_hours(samples: pd.DataFrame) -> pd.DataFrame:
    """Hours of wear per run (sample span plus one interval)."""
    keys = [k for k in RUN_KEYS if k in samples]
    return (
        samples.groupby(keys)["time"]
        .agg(lambda t: (t.max() - t.min()) / pd.Timedelta("1h") + 5 / 60)
        .rename("hours")
        .reset_index()
    )


CAUSES = ("compression", "other_fault", "near_event", "noise")


def per_run_metrics(
    classified: pd.DataFrame, scored: pd.DataFrame, hours: pd.DataFrame, alarm_names
) -> pd.DataFrame:
    """One row per run x alarm (every pair, zeros included): counts, rates per day, sensitivity."""
    keys = [k for k in RUN_KEYS if k in hours]
    grid = hours.merge(pd.DataFrame({"alarm_name": list(alarm_names)}), how="cross")
    a = classified
    if len(a):  # counts must be integers even when an empty frame made is_floor an object column
        a = a.assign(false=~a["matched"].astype(bool), is_floor=a["is_floor"].astype(bool))
        counts = a.groupby(keys + ["alarm_name"]).agg(
            n_alarms=("time", "size"), n_floor=("is_floor", "sum"), n_false=("false", "sum")
        )
        causes = a[a["false"]].groupby(keys + ["alarm_name", "cause"]).size().unstack("cause")
        causes = causes.reindex(columns=list(CAUSES)).add_prefix("false_")
        m = grid.merge(counts.join(causes).reset_index(), on=keys + ["alarm_name"], how="left")
    else:
        m = grid.assign(n_alarms=0, n_floor=0, n_false=0, **{f"false_{c}": 0 for c in CAUSES})
    fill = ["n_alarms", "n_floor", "n_false"] + [f"false_{c}" for c in CAUSES]
    m[fill] = m[fill].fillna(0).astype(int)
    if len(scored):
        lev = scored.groupby(keys + ["alarm_name", "level"]).agg(
            events=("caught", "size"),
            caught=("caught", "sum"),
            warning_median_min=("warning_min", "median"),
        )
        lev = lev.unstack("level")
        lev.columns = [f"{name}_l{level}" for name, level in lev.columns]
        m = m.merge(lev.reset_index(), on=keys + ["alarm_name"], how="left")
        for level in (1, 2):
            for col in (f"events_l{level}", f"caught_l{level}"):
                if col in m:
                    m[col] = m[col].fillna(0)
    days = m["hours"] / 24
    m["false_per_day"] = m["n_false"] / days
    for c in CAUSES:
        m[f"false_{c}_per_day"] = m[f"false_{c}"] / days
    return m
