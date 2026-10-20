"""Package the frozen simulated cohort `ghostlows-bench v1` for a dataset release (DECISIONS.md D18).

    uv run python scripts/package_cohort.py            # writes dist/ghostlows-bench-v1.zip

The archive holds the simulated cohort exactly as the benchmark reads it (5-min samples, 1-min
plasma truth, event logs), its configuration, calibration and provenance, the fault events of
the main sweep (faults are a deterministic function of the cohort, the fault config and a seed,
so the faulted CGM is rebuilt with `ghostlows.faults.apply_faults`), a data card and a SHA-256
manifest. Uploading it (and choosing its licence) is left to the project lead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ghostlows.bench.pipeline import BENCHMARK_VERSION, BenchConfig  # noqa: E402
from ghostlows.faults import apply_faults  # noqa: E402
from ghostlows.sim.run import SimConfig, load  # noqa: E402

NAME = "ghostlows-bench-v1"

DATACARD = """# {name}: simulated CGM cohort for benchmarking low-glucose alarms

Version: `{version}`. Built by [Ghost Lows](https://github.com/pkarakala/ghost-lows) at commit
`{commit}` on {date} (simglucose {simglucose}, cohort cache key `{key}`).

## What it is

Synthetic data only. 30 virtual patients (10 adolescents, 10 adults, 10 children) of the UVA/Padova
2008 model as implemented in simglucose, 14 days each, 5 seeds, three scenario mixes (`standard`,
`default`, `high`), {runs} patient-runs in total. Open-loop basal-bolus therapy with per-patient
calibrated bolus settings (`calibration_v1.yaml`). The virtual patients treat lows with the
15-15 rule on the fault-free CGM; rescue carbohydrate is eaten but not logged.

## Files

| Path | Content |
|---|---|
| `samples/<mix>_s<seed>_<patient>.parquet` | 5-min rows: `glucose` (fault-free CGM), `glucose_flag`, `truth_glucose` (plasma), `isf_glucose` (interstitial), `cgm_noise`, `insulin_bolus`, `insulin_basal`, `carbs` (announced), `iob`, `cob` (from logged events only), `sensitivity`, `exercising`, `rescue_carbs` (eaten, never logged), `patient_id`, `seed`, `mix` |
| `truth/...parquet` | 1-min plasma glucose (`truth_glucose`) |
| `events/...parquet` | meals eaten, announced carbs, boluses, rescue treatments, exercise |
| `runs.csv` | per run: validity, nadir, time below 70 and 54 mg/dL |
| `faults/pisa_<level>.parquet` | fault events (type, start, end, size) of the main sweep: PISA on that fraction of nights, other faults at severity {severity}, seed {fault_seed} |
| `config/` | the simulation, calibration and benchmark configs |
| `MANIFEST.json` | SHA-256 and size of every file |

The faulted CGM at a sweep level is rebuilt exactly with
`ghostlows.faults.apply_faults(samples, FaultConfig(pisa_fraction=level, severity={severity}), seed={fault_seed})`.

## Limitations

Copied from `docs/RESEARCH.md` §6 of the repository on {date}. Its section (§), decision (D),
amendment (A), proposal (P) and clinical-review (CR) references point into that repository.

{limitations}

## Licence and citation

Proposed licence: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/), to be confirmed by
the project lead before release. Cite the Ghost Lows software (CITATION.cff) and simglucose.
"""


def limitations() -> str:
    """docs/RESEARCH.md §6 verbatim, so the data card cannot drift from the repository's list."""
    text = (REPO / "docs" / "RESEARCH.md").read_text()
    m = re.search(r"## 6\. Known limitations to state up front\n(.*?)\n## 7", text, flags=re.S)
    if not m:
        raise ValueError("docs/RESEARCH.md has no §6 'Known limitations to state up front'")
    return m.group(1).strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sim", default="experiments/configs/sim_full.yaml")
    parser.add_argument("--bench", default="experiments/configs/rq1_pisa_sweep.yaml")
    parser.add_argument("--out", default=str(REPO / "dist"))
    args = parser.parse_args()

    sim = SimConfig.load(REPO / args.sim)
    bench = BenchConfig.load(REPO / args.bench)
    cohort = sim.out_dir()
    if not (cohort / "meta.json").exists():
        print(f"cohort not simulated: {cohort}")
        return 1
    meta = json.loads((cohort / "meta.json").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / NAME
        for sub in ("samples", "truth", "events"):
            shutil.copytree(cohort / sub, root / sub)
        shutil.copy(cohort / "runs.csv", root / "runs.csv")
        (root / "config").mkdir()
        for path in (args.sim, args.bench, sim.calibration):
            shutil.copy(REPO / path, root / "config" / Path(path).name)
        samples = load(cohort)["samples"]
        (root / "faults").mkdir()
        for level in bench.levels:
            _, faults = apply_faults(samples, bench.fault_config(level), seed=bench.fault_seed)
            faults.to_parquet(root / "faults" / f"pisa_{level:g}.parquet", index=False)
        (root / "DATACARD.md").write_text(
            DATACARD.format(
                name=NAME,
                version=BENCHMARK_VERSION,
                commit=meta.get("git_commit", "unknown"),
                date=datetime.now(UTC).date().isoformat(),
                simglucose=meta.get("simglucose"),
                key=meta.get("key"),
                runs=meta.get("tasks"),
                severity=bench.severity,
                fault_seed=bench.fault_seed,
                limitations=limitations(),
            )
        )
        (root / "provenance.yaml").write_text(yaml.safe_dump({"cohort_meta": meta}))
        files = sorted(p for p in root.rglob("*") if p.is_file())
        manifest = {
            p.relative_to(root).as_posix(): {"bytes": p.stat().st_size, "sha256": sha256(p)}
            for p in files
        }
        (root / "MANIFEST.json").write_text(json.dumps(manifest, indent=1) + "\n")
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        archive = out / f"{NAME}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as z:
            for p in sorted(root.rglob("*")):
                if p.is_file():
                    z.write(p, Path(NAME) / p.relative_to(root))
    size = archive.stat().st_size / 1e6
    print(f"wrote {archive} ({size:.0f} MB, {len(manifest)} files), sha256 {sha256(archive)}")
    print(f"faults included for PISA levels {bench.levels}; {len(samples)} sample rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
