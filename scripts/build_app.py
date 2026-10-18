"""Build the ghostlows wheel into app/ and write app/wheel.json for app/index.html.

uv run python scripts/build_app.py            # then serve app/ (e.g. python -m http.server)
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "app"


def main() -> Path:
    """Build into a temporary folder (uv writes a catch-all .gitignore into its output folder,
    which must not land in app/) and copy only the wheel next to the page."""
    for old in APP.glob("ghostlows-*.whl"):
        old.unlink()
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["uv", "build", "--wheel", "--out-dir", tmp], cwd=REPO, check=True)
        built = next(Path(tmp).glob("ghostlows-*.whl"))
        wheel = APP / built.name
        shutil.copy(built, wheel)
    (APP / "wheel.json").write_text(json.dumps({"file": wheel.name}) + "\n")
    print(f"built {wheel.relative_to(REPO)}")
    return wheel


if __name__ == "__main__":
    main()
