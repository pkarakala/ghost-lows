"""The data card of scripts/package_cohort.py states the limitations of
docs/reference/RESEARCH.md §6."""

import importlib.util
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package_cohort", ROOT / "scripts/package_cohort.py")
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)


def bullets(section: str) -> list[str]:
    return [line for line in section.splitlines() if line.startswith("- ")]


def test_datacard_limitations_match_research_section_6():
    # parsed here without the script's regex, so a change to either side fails the test
    research = (ROOT / "docs" / "reference" / "RESEARCH.md").read_text()
    expected = bullets(research.split("\n## 6. ")[1].split("\n## ")[0])
    card = pc.DATACARD.format_map(defaultdict(str, limitations=pc.limitations()))
    stated = bullets(card.split("\n## Limitations\n")[1].split("\n## ")[0])
    assert len(expected) >= 10
    assert stated == expected


def test_an_incomplete_cohort_is_not_packaged(tmp_path, monkeypatch, capsys):
    """A patient-run missing a part file stops packaging (audit 2026-10), so a dataset release
    cannot silently ship without some event logs."""
    import pytest

    pytest.importorskip("simglucose")
    from ghostlows.sim import run

    monkeypatch.setattr(run, "DATA", tmp_path)
    config = tmp_path / "sim.yaml"
    config.write_text("name: t\npatients: ['adult#001']\ndays: 1\nseeds: [1]\nmixes: [default]\n")
    cohort = run.SimConfig.load(config).out_dir()
    for sub in ("samples", "truth"):
        (cohort / sub).mkdir(parents=True)
        (cohort / sub / run.part_name("adult#001", 1, "default")).write_bytes(b"")
    (cohort / "events").mkdir()
    (cohort / "meta.json").write_text("{}")
    monkeypatch.setattr("sys.argv", ["package_cohort.py", "--sim", str(config)])
    assert pc.main() == 1
    assert "cohort incomplete: 1 patient-runs" in capsys.readouterr().out
