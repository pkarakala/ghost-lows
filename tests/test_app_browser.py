"""The upload dashboard in a real browser (ROADMAP phase 8; PRIVACY_AND_SAFETY.md).

Serves app/ locally, loads the stlite page in Chromium, uploads the synthetic Clarity fixture and
checks that the report renders with its flags and safety text, and that no network request
carries the file's contents; then checks the "Try it with sample data" button and the sample
download. Needs network access (stlite and Pyodide come from public CDNs):

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
SAMPLE = ROOT / "app" / "sample_clarity_export.csv"
SAMPLE_BANNER = "You are viewing synthetic sample data, not a real person's data."
FORBIDDEN = (
    "not real",
    "fake",
    "can be ignored",
    "ignore it",
    "ghost low",
    "felt real",
)  # safety 2
# Strings that occur in the uploaded file and nowhere in the app or its runtime
MARKERS = ["FIXTURE", "Synthetic G7 receiver", "2026-01-13T02:00:00"]
# Hosts the page may contact: the pinned runtime and Python packages, nothing else. stlite names
# media it serves from inside the page (the sample download) under the reserved .invalid domain;
# those requests never resolve, and the test asserts they fail.
ALLOWED_HOSTS = {"127.0.0.1", "cdn.jsdelivr.net", "pypi.org", "files.pythonhosted.org"}
IN_PAGE_HOST = "stlite.invalid"


def check_hosts(requests) -> None:
    hosts = {urlparse(r.url).hostname for r in requests if r.url.startswith("http")}
    assert hosts <= ALLOWED_HOSTS | {IN_PAGE_HOST}, hosts - ALLOWED_HOSTS
    for r in requests:
        if urlparse(r.url).hostname == IN_PAGE_HOST:
            assert r.failure and not r.post_data, r.url


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
    for phrase in FORBIDDEN:
        assert phrase not in text.lower()
    assert SAMPLE_BANNER not in text

    for request in requests:
        body = request.post_data or ""
        for marker in MARKERS:
            assert marker not in request.url and marker not in body, request.url
    check_hosts(requests)


def test_sample_data_shows_the_full_report(page_url, tmp_path):
    from playwright.sync_api import sync_playwright

    requests = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("request", lambda request: requests.append(request))
        page.goto(page_url)
        button = page.get_by_role("button", name="Try it with sample data")
        button.wait_for(timeout=300_000)
        with page.expect_download(timeout=60_000) as download:
            page.get_by_role("button", name="Download the sample file").click()
        saved = tmp_path / "download.csv"
        download.value.save_as(saved)
        button.click()
        page.get_by_text(SAMPLE_BANNER).wait_for(timeout=180_000)
        page.get_by_text("Possible compression artifact on the night of").first.wait_for(
            timeout=180_000
        )
        page.get_by_text("Time in range 70-180 mg/dL").wait_for(timeout=60_000)
        page.wait_for_timeout(2_000)  # let the script run finish rendering
        charts = page.locator("[data-testid='stVegaLiteChart']")
        # the AGP is the first chart; it is drawn once its canvas (or SVG) has a size
        agp = charts.first.locator("canvas, svg").first
        agp_box = agp.bounding_box()
        n_charts = charts.count()
        page.get_by_text("What really happened in this sample").click()
        page.get_by_text("compression artifact (injected)").first.wait_for(timeout=30_000)
        text = page.inner_text("body")
        browser.close()

    assert saved.read_bytes() == SAMPLE.read_bytes()
    assert text.index(SAMPLE_BANNER) < text.index("Consensus metrics")
    assert "Research software, not a medical device" in text
    assert "If you are unsure whether a low is real, check with a fingerstick" in text
    for metric in ("Time in range 70-180 mg/dL", "GMI", "Time below 70 mg/dL"):
        assert metric in text
    assert "Ambulatory glucose profile" in text
    assert agp_box is not None and agp_box["height"] > 100 and agp_box["width"] > 200
    assert n_charts >= 3  # AGP, daily traces and at least one flagged night
    assert "Without possible compression artifacts" in text
    assert "real low: true glucose below 70 mg/dL" in text
    for phrase in FORBIDDEN:
        assert phrase not in text.lower()
    check_hosts(requests)
