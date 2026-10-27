"""Shared style of the publication figures (`experiments/make_paper_figures.py`).

Sized for one journal column (89 mm), readable when printed at that size. Categorical colours
are the reference slots in a fixed order: blue, orange, aqua, yellow. The palette was checked
with the dataviz validator: any three slots for any chart form, four only in stacks and other
adjacent forms. Grids and axes are hairlines, one y-axis per panel, and 95% CIs are always
drawn. Output is SVG and PDF (vector) plus a 300 dpi PNG, without timestamps, so redrawing
unchanged tables gives unchanged files.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLUMN_IN = 3.5  # one journal column (89 mm)
INK, SECONDARY, MUTED = "#0b0b0b", "#52514e", "#898781"  # text tokens
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#ffffff"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
SLOTS = (BLUE, ORANGE, AQUA, YELLOW)
BAND_ALPHA = 0.12  # CI bands: a wash of the series colour
RC = {
    "font.family": "DejaVu Sans",
    "font.size": 7,
    "axes.titlesize": 7,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.labelsize": 7,
    "axes.labelcolor": SECONDARY,
    "axes.edgecolor": AXIS,
    "axes.linewidth": 0.6,
    "axes.facecolor": SURFACE,
    "axes.grid": True,
    "axes.axisbelow": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "grid.color": GRID,
    "grid.linewidth": 0.5,
    "xtick.color": AXIS,
    "ytick.color": AXIS,
    "xtick.labelcolor": SECONDARY,
    "ytick.labelcolor": SECONDARY,
    "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "legend.fontsize": 6.5,
    "legend.frameon": False,
    "legend.handlelength": 1.4,
    "lines.linewidth": 1.25,
    "lines.markersize": 3.5,
    "figure.facecolor": SURFACE,
    "figure.dpi": 100,
    "savefig.dpi": 300,
    "savefig.facecolor": SURFACE,
    "pdf.fonttype": 42,  # embedded TrueType: text stays editable
    "svg.fonttype": "path",  # glyphs as paths: renders the same without the font installed
    "svg.hashsalt": "ghostlows",  # stable element ids
}
METADATA = {
    "svg": {"Date": None},
    "pdf": {"CreationDate": None, "ModDate": None},
    "png": {"Software": None},
}


def use() -> None:
    plt.rcParams.update(RC)


def save(fig, out_dir: Path, stem: str) -> list[Path]:
    """Write `stem`.svg, .pdf and .png into `out_dir`; returns the paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext, meta in METADATA.items():
        path = out_dir / f"{stem}.{ext}"
        fig.savefig(path, metadata=meta, bbox_inches="tight", pad_inches=0.03)
        paths.append(path)
    plt.close(fig)
    return paths
