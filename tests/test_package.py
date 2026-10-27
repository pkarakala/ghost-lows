"""The installable package: what the core wheel (numpy and pandas only) can import."""

import subprocess
import sys

import numpy as np
import pandas as pd

# The optional extras ([bench], [sim]); the core wheel and the Pyodide app have none of them.
EXTRAS = ("scipy", "sklearn", "yaml", "simglucose", "matplotlib")


def test_import_needs_only_the_core_dependencies():
    code = (
        "import sys, ghostlows, ghostlows.alarms, ghostlows.faults, ghostlows.io, "
        "ghostlows.metrics, ghostlows.retro, ghostlows.bench.scoring, ghostlows.bench.events; "
        f"print(sorted(m for m in {EXTRAS!r} if m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


def test_public_api_is_documented():
    import ghostlows

    for name in ghostlows.__all__:
        assert hasattr(ghostlows, name), name
        if name != "__version__":
            assert (getattr(ghostlows, name).__doc__ or "").strip(), f"{name} has no docstring"


def test_score_alarm_is_the_benchmark_scoring():
    """score_alarm = view -> fire_and_score -> per_run_metrics, as in the benchmark pipeline."""
    import ghostlows as gl
    from ghostlows.alarms import view
    from ghostlows.bench import pipeline, scoring

    assert pipeline.fire_and_score is scoring.fire_and_score
    trace = gl.load_clarity(gl.sample_export())
    trace = trace[trace["glucose"].notna()].assign(seed=0, mix="none")
    config = gl.FaultConfig(pisa_fraction=1.0, enabled=frozenset({"pisa"}))
    observed, faults = gl.apply_faults(trace, config, seed=1)
    lows = gl.low_events(trace)
    alarm = gl.TrendAlarm()
    got = gl.score_alarm(alarm, observed, lows, faults)
    frame = view(observed, "cgm_observed")
    _, cls, scored = scoring.fire_and_score(
        alarm, frame, alarm.default_threshold, lows, faults, observed, scoring.DEFAULT_WINDOWS
    )
    want = scoring.per_run_metrics(cls, scored, scoring.run_hours(observed), [alarm.name])
    pd.testing.assert_frame_equal(got, want)
    assert len(faults) and (faults["fault_type"] == "pisa").all()
    assert got["false_compression_per_day"].iloc[0] > 0


def test_low_events_matches_true_events_and_the_real_data_track():
    from ghostlows.bench.events import LEVEL_THRESHOLDS, detect_events, low_events, true_events

    t1 = pd.date_range("2026-01-05", periods=600, freq="1min")
    g = np.full(600, 120.0)
    g[100:140], g[300:330] = 60.0, 50.0
    truth = pd.DataFrame({"patient_id": "p", "time": t1, "truth_glucose": g})
    pd.testing.assert_frame_equal(low_events(truth, "truth_glucose"), true_events(truth))

    five = truth.iloc[::5].reset_index(drop=True).rename(columns={"truth_glucose": "glucose"})
    got = low_events(five)
    times = five["time"].to_numpy()
    want = [
        (level, times[s])
        for level, thr in LEVEL_THRESHOLDS.items()
        for s, _ in detect_events(five["glucose"].to_numpy(), thr, step_min=5)
    ]
    assert list(zip(got["level"], got["onset"].to_numpy(), strict=True)) == want
    assert len(want) == 3  # two level 1 lows, one level 2


def test_sample_export_loads():
    import ghostlows as gl

    trace = gl.load_clarity(gl.sample_export())
    assert trace["glucose"].notna().sum() > 14 * 288 * 0.9


def test_one_version():
    """The version lives in ghostlows/__init__.py (hatch dynamic version); CITATION.cff and the
    installed metadata must agree with it."""
    from importlib.metadata import version
    from pathlib import Path

    import yaml

    import ghostlows

    citation = yaml.safe_load((Path(__file__).parents[1] / "CITATION.cff").read_text())
    assert str(citation["version"]) == ghostlows.__version__ == version("ghostlows")


def test_zenodo_metadata_matches_citation():
    """Zenodo reads .zenodo.json before CITATION.cff; both must name the same work, authors and
    licence. LICENSE must be the plain MIT text so GitHub detects it."""
    import json
    from pathlib import Path

    import yaml

    root = Path(__file__).parents[1]
    citation = yaml.safe_load((root / "CITATION.cff").read_text())
    zenodo = json.loads((root / ".zenodo.json").read_text())
    assert zenodo["title"] == citation["title"]
    assert zenodo["description"] == citation["abstract"].strip()
    assert zenodo["license"] == citation["license"] == "MIT"
    assert zenodo["keywords"] == citation["keywords"]
    assert "version" not in zenodo and "doi" not in zenodo  # Zenodo sets both per release
    assert zenodo["creators"] == [
        {
            "name": f"{a['family-names']}, {a['given-names']}",
            "orcid": a["orcid"].removeprefix("https://orcid.org/"),
            "affiliation": a["affiliation"],
        }
        for a in citation["authors"]
    ]
    assert (root / "LICENSE").read_text().rstrip().endswith("OTHER DEALINGS IN THE\nSOFTWARE.")


def test_cli_help_lists_each_command_on_one_line():
    out = subprocess.run(
        [sys.executable, "-m", "ghostlows.cli", "--help"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    for command in ("simulate", "benchmark", "score"):
        assert any(line.strip().startswith(command + " ") for line in out.splitlines()), command


def test_cli_names_a_missing_extra(monkeypatch):
    import importlib.util

    import pytest

    from ghostlows import cli

    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda name: None if name == "simglucose" else real(name)
    )
    with pytest.raises(SystemExit, match=r"missing: simglucose.*ghostlows\[bench,sim\]"):
        cli.main(["simulate", "--config", "x.yaml"])
