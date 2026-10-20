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
