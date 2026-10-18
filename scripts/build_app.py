"""Build the ghostlows wheel into app/ and write app/wheel.json for app/index.html.

uv run python scripts/build_app.py            # then serve app/ (e.g. python -m http.server)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "app"


def main() -> Path:
    for old in APP.glob("ghostlows-*.whl"):
        old.unlink()
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(APP)], cwd=REPO, check=True)
    wheel = next(APP.glob("ghostlows-*.whl"))
    (APP / "wheel.json").write_text(json.dumps({"file": wheel.name}) + "\n")
    print(f"built {wheel.relative_to(REPO)}")
    return wheel


if __name__ == "__main__":
    main()
