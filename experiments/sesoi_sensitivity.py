"""Post hoc: re-read the frozen H2 table at other smallest effect sizes of interest (amendment A21).

    uv run python experiments/sesoi_sensitivity.py

No rerun: applies the pre-registered H2 reading rule (RESEARCH.md §3) to the committed rate
ratios and CIs of the PISA sweep at each SESOI. Writes results/tables/sesoi_sensitivity.csv and
prints a Markdown table: per detector and mix, how many of the PISA levels read
each way. The pre-registered SESOI stays 0.75; the other values are not.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ghostlows.bench.analysis import h2_reading

TABLES = Path(__file__).resolve().parents[1] / "results" / "tables"
# ASSUMPTION: reductions of 10%, 15%, 20%, 25% (pre-registered) and 50%; no published value exists
SESOIS = (0.90, 0.85, 0.80, 0.75, 0.50)


def main() -> None:
    h2 = pd.read_csv(TABLES / "rq1_pisa_sweep__contrasts_h2.csv").dropna(subset=["rate_ratio"])
    rows = []
    for (det, mix), g in h2.groupby(["detector", "mix"], sort=True):
        row = {"detector": det, "mix": mix, "levels": len(g)}
        for s in SESOIS:
            reads = [h2_reading(r.rate_ratio, r.lo, r.hi, s) for r in g.itertuples()]
            for name in ("meaningful reduction", "inconclusive", "no meaningful reduction"):
                row[f"{s:.2f} {name}"] = reads.count(name)
        rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(TABLES / "sesoi_sensitivity.csv", index=False)

    def cell(r: pd.Series, s: float) -> str:
        m, i = r[f"{s:.2f} meaningful reduction"], r[f"{s:.2f} inconclusive"]
        return (
            "no meaningful reduction"
            if m == i == 0
            else ", ".join(
                x for x in (f"{m} meaningful" if m else "", f"{i} inconclusive" if i else "") if x
            )
        )

    head = " | ".join(f"SESOI {s:.2f}" for s in SESOIS)
    print(f"| Detector | Mix | {head} |\n|---|---|" + "---|" * len(SESOIS))
    for _, r in out.sort_values(["mix", "detector"]).iterrows():
        print(f"| `{r.detector}` | {r.mix} | " + " | ".join(cell(r, s) for s in SESOIS) + " |")


if __name__ == "__main__":
    main()
