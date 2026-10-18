"""Analyse the pilot: true-low counts, IOB leak, simulator lag, PISA-susceptible time.

Events: >=15 consecutive minutes (3 samples at 5 min) below threshold; end after >=15 minutes
(3 samples) at or above. Night: onset 23:00-07:00. IOB: bolus insulin with a linear 4 h decay
(pilot simplification). Usage: analyse_stock.py pilot.parquet
"""

import sys

import numpy as np
import pandas as pd

df = pd.read_parquet(sys.argv[1])
df["group"] = df["patient"].str.split("#").str[0]


def events(x: np.ndarray, thr: float, n: int = 3) -> list[tuple[int, int]]:
    out, start, below, above = [], None, 0, 0
    for i, v in enumerate(x):
        if start is None:
            below = below + 1 if v < thr else 0
            if below == n:
                start, above = i - n + 1, 0
        else:
            above = above + 1 if v >= thr else 0
            if above == n:
                out.append((start, i - n + 1))
                start, below = None, 0
    if start is not None:
        out.append((start, len(x)))
    return out


def iob(bolus: np.ndarray, dia_steps: int = 48) -> np.ndarray:
    kernel = np.clip(1 - np.arange(dia_steps) / dia_steps, 0, None)
    return np.convolve(bolus, kernel)[: len(bolus)]


def is_night(t: pd.Series) -> np.ndarray:
    h = t.dt.hour
    return ((h >= 23) | (h < 7)).to_numpy()


rows, onset_iob, night_iob, lags = [], [], [], []
for name, p in df.groupby("patient", sort=False):
    p = p.reset_index(drop=True)
    night = is_night(p["time"])
    p_iob = iob(p["bolus_u"].to_numpy())
    plasma = p["plasma"].to_numpy()
    rec = {"patient": name, "group": p["group"].iloc[0], "days": len(p) / 288}
    for thr, lvl in [(70, "L1"), (54, "L2")]:
        ev = events(plasma, thr)
        ev_night = [e for e in ev if night[e[0]]]
        rec[f"{lvl}"] = len(ev)
        rec[f"{lvl}_night"] = len(ev_night)
        rec[f"{lvl}_gsub"] = len(events(p["gsub"].to_numpy(), thr))
        if lvl == "L1":
            onset_iob += [p_iob[s] for s, _ in ev_night]
            for s, e in ev:
                # first Gsub sample below 70 from 30 min before plasma onset to event end
                lo = max(0, s - 6)
                below = np.nonzero(p["gsub"].to_numpy()[lo : max(e, s + 1)] < 70)[0]
                if below.size:
                    lags.append((lo + below[0] - s) * 5)
    night_iob += list(p_iob[night])
    for lo, hi in [(70, 95), (70, 118)]:
        rec[f"night_frac_{lo}_{hi}"] = np.mean((plasma[night] >= lo) & (plasma[night] < hi))
    rec["night_frac_below70"] = np.mean(plasma[night] < 70)
    rec["min_plasma"] = plasma.min()
    rows.append(rec)

r = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(r.round(3).to_string(index=False))
print("\nTotals by group (events over the simulated days):")
print(r.groupby("group")[["days", "L1", "L1_night", "L2", "L2_night", "L1_gsub", "L2_gsub"]].sum())
print("\nPatients with zero level-2 events:", int((r["L2"] == 0).sum()), "of", len(r))
print("Patients with zero nocturnal level-2 events:", int((r["L2_night"] == 0).sum()), "of", len(r))
print(
    "Median night fraction with plasma in [70,95):",
    round(r["night_frac_70_95"].median(), 3),
    "| [70,118):",
    round(r["night_frac_70_118"].median(), 3),
)

a, b = np.asarray(onset_iob), np.asarray(night_iob)
if a.size:
    # AUC = P(IOB at a nocturnal low onset > IOB at a random night sample); ties count half
    gt = (a[:, None] > b[None, :]).mean()
    eq = (a[:, None] == b[None, :]).mean()
    print(
        f"\nIOB leak: n nocturnal L1 onsets = {a.size}; "
        f"AUC(IOB, onset vs random night) = {gt + eq / 2:.3f}"
    )
    print(
        f"  share of nocturnal L1 onsets with IOB > 0: {np.mean(a > 0):.3f};"
        f" share of night samples with IOB > 0: {np.mean(b > 0):.3f}"
    )
if lags:
    lags = np.asarray(lags)
    print(
        f"\nSimulator lag, Gsub crossing 70 minus plasma onset (min): median {np.median(lags):.0f},"
        f" IQR {np.percentile(lags, 25):.0f}-{np.percentile(lags, 75):.0f}, n={lags.size}"
    )
