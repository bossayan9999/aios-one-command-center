from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_server(port: int, timeout: float = 20.0) -> None:
    import urllib.request

    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1):
                return
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f"Server did not start: {last_error}")


def test_critical_browser_flow() -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    port = free_port()
    env = os.environ.copy()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        wait_for_server(port)
        with playwright.sync_playwright() as context:
            browser = context.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")

            assert page.locator("body").is_visible()
            assert page.locator('[data-view="roadmap"]').first.is_visible()

            page.locator('[data-view="roadmap"]').first.click()
            page.wait_for_timeout(400)
            assert page.locator("#view-roadmap").is_visible()
            assert page.locator("#roadmapPhases .roadmap-phase").count() >= 1

            page.locator('[data-view="ai-settings"]').first.click()
            page.wait_for_timeout(300)
            assert page.locator("#runModelPreflight").is_visible()

            page.locator('[data-view="connectors"]').first.click()
            page.wait_for_timeout(300)
            assert page.locator("#desktopCompanionRequests").is_visible()

            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
