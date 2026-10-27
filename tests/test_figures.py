"""The publication figures and their captions in results/README.md (`make figures`)."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
README = RESULTS / "README.md"
FIGURE_LINK_RE = re.compile(r"\]\((figures/[^)\s]+)\)")


def experiment(name: str):
    """Import a script from experiments/, where the scripts import each other by bare name."""
    folder = str(ROOT / "experiments")
    sys.path.insert(0, folder)
    try:
        spec = importlib.util.spec_from_file_location(name, ROOT / "experiments" / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(folder)
    return module


def test_every_figure_listed_in_the_results_readme_exists():
    listed = FIGURE_LINK_RE.findall(README.read_text())
    assert len(listed) > 20
    assert [f for f in listed if not (RESULTS / f).is_file()] == []


def test_each_publication_figure_is_shown_with_its_vector_files():
    text = README.read_text()
    stems = experiment("make_paper_figures").FIGURE_STEMS
    for stem in stems:
        for ext in ("png", "svg", "pdf"):
            assert f"](figures/{stem}.{ext})" in text, f"{stem}.{ext} not in results/README.md"
    assert {p.stem for p in (RESULTS / "figures").glob("fig*.png")} == set(stems)


def test_robustness_figures_are_in_the_appendix():
    figures = RESULTS / "figures"
    assert list(figures.glob("robust_*")) == []
    assert len(list((figures / "appendix").glob("robust_*.png"))) == 28


def test_results_readme_is_what_the_generator_writes():
    """The captions are generated from the tables, so a hand edit, or a table changed without
    regenerating, shows up here. Fix: uv run python experiments/make_results_readme.py."""
    assert experiment("make_results_readme").build() == README.read_text()


def test_social_preview_is_the_size_github_asks_for():
    with Image.open(ROOT / "docs" / "figures" / "social_preview.png") as image:
        assert image.size == (1280, 640)
