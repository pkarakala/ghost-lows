"""Loader for the GlucoBench raw CSVs (docs/reference/DATA.md §1), from scripts/download_data.py."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

from .schema import finalize

log = logging.getLogger(__name__)

DATASETS = ["weinstock", "dubosson", "hall", "colas", "iglu"]
# Repository checkout by default; GHOSTLOWS_DATA_DIR points elsewhere (it replaces `data/`).
_DATA = os.environ.get("GHOSTLOWS_DATA_DIR") or Path(__file__).resolve().parents[3] / "data"
DEFAULT_DIR = Path(_DATA) / "raw" / "glucobench"

# Values that stand for readings outside the sensor's range, as (value, flag, stored value).
# ASSUMPTION: inferred from pile-ups at the extremes (docs/reference/DATA.md §1): weinstock has
# 11,924 readings of 39 vs 605 of 40 and 11,978 of 401 vs 187 of 400; dubosson piles up at 39.6
# and 399.6 (2.2 and 22.2 mmol/L x 18); colas has 75 readings of 40 vs 12 of 41.
SENTINELS = {
    "weinstock": [(39.0, "below_range", 40.0), (401.0, "above_range", 400.0)],
    "dubosson": [(39.6, "below_range", 39.6), (399.6, "above_range", 399.6)],
    "colas": [(40.0, "below_range", 40.0)],
}


def load_glucobench(name: str, data_dir: str | Path | None = None) -> pd.DataFrame:
    """One GlucoBench dataset in the common schema.

    Patient IDs are prefixed with the dataset name (e.g. `weinstock:199`). Covariates other
    than glucose are dropped: GlucoBench interpolates dubosson's insulin and calories between
    events, so those columns use future values and cannot serve as causal context.
    """
    if name not in DATASETS:
        raise ValueError(f"unknown GlucoBench dataset {name!r}; expected one of {DATASETS}")
    path = Path(data_dir or DEFAULT_DIR) / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run `uv run python scripts/download_data.py`")
    raw = pd.read_csv(path, usecols=["id", "time", "gl"])
    ids = raw["id"]
    if pd.api.types.is_float_dtype(ids):
        ids = ids.astype("Int64")
    df = pd.DataFrame(
        {
            "patient_id": f"{name}:" + ids.astype(str),
            "time": pd.to_datetime(raw["time"]),
            "glucose": raw["gl"].astype(float),
            "glucose_flag": "ok",
            "source": f"glucobench:{name}",
        }
    )
    for value, flag, stored in SENTINELS.get(name, []):
        hit = np.isclose(df["glucose"], value)
        df.loc[hit, "glucose_flag"] = flag
        df.loc[hit, "glucose"] = stored
    df = finalize(df)
    log.info(
        "loaded %s: %d rows, %d patients, %d censored",
        name,
        len(df),
        df["patient_id"].nunique(),
        int((df["glucose_flag"].isin(["below_range", "above_range"])).sum()),
    )
    return df


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for name in DATASETS:
        load_glucobench(name)


if __name__ == "__main__":
    main()
