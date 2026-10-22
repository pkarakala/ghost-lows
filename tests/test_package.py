"""The installable package: what the core wheel (numpy and pandas only) can import."""

import subprocess
import sys

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
