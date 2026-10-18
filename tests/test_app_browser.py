"""The upload dashboard in a real browser (ROADMAP phase 8; PRIVACY_AND_SAFETY.md).

Serves app/ locally, loads the stlite page in Chromium, uploads the synthetic Clarity fixture and
checks that the report renders with its flags and safety text, and that no network request
carries the file's contents. Needs network access (stlite and Pyodide come from public CDNs):

    uv sync --group browser && uv run playwright install chromium
    uv run pytest -m browser
"""

import functools
import http.server
import threading
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.browser

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "clarity_sample.csv"
# Strings that occur in the uploaded file and nowhere in the app or its runtime
MARKERS = ["FIXTURE", "Synthetic G7 receiver", "2026-01-13T02:00:00"]
# Hosts the page may contact: the pinned runtime and Python packages, nothing else
ALLOWED_HOSTS = {"127.0.0.1", "cdn.jsdelivr.net", "pypi.org", "files.pythonhosted.org"}


@pytest.fixture(scope="module")
def page_url():
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_app", ROOT / "scripts" / "build_app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "app"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/index.html"
    server.shutdown()


def test_upload_renders_report_and_keeps_the_file_local(page_url):
    from playwright.sync_api import sync_playwright

    requests = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("request", lambda request: requests.append(request))
        page.goto(page_url)
        page.wait_for_selector("input[type=file]", state="attached", timeout=300_000)
        page.set_input_files("input[type=file]", str(FIXTURE))
        page.get_by_text("Nights with possible compression artifacts").wait_for(timeout=180_000)
        page.get_by_text("Why it was flagged").first.wait_for(timeout=60_000)
        page.get_by_text("Time in range 70-180 mg/dL").wait_for(timeout=60_000)
        page.wait_for_timeout(2_000)  # let the script run finish rendering
        text = page.inner_text("body")
        browser.close()

    assert "Research software, not a medical device" in text
    assert "If you are unsure whether a low is real, check with a fingerstick" in text
    assert "Time in range 70-180 mg/dL" in text
    assert "Without possible compression artifacts" in text
    assert "Possible compression artifact on the night of" in text
    for phrase in ("not real", "fake", "can be ignored"):
        assert phrase not in text.lower()

    for request in requests:
        body = request.post_data or ""
        for marker in MARKERS:
            assert marker not in request.url and marker not in body, request.url
    hosts = {urlparse(r.url).hostname for r in requests if r.url.startswith("http")}
    assert hosts <= ALLOWED_HOSTS, hosts - ALLOWED_HOSTS
