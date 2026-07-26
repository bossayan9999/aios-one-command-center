from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from security.app_security import hash_password  # noqa: E402

SCREENSHOTS = ROOT / "docs" / "screenshots"
PASSWORD = "correct horse battery staple"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_server(port: int, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1):
                return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError("Screenshot server did not start")


def sign_in(page: Page, port: int) -> None:
    page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded")
    page.locator("#securityUsername").fill("owner")
    page.locator("#securityPassword").fill(PASSWORD)
    page.locator("#securityLoginForm button[type=submit]").click()
    page.locator("#securityLogin").wait_for(state="hidden")


def main() -> None:
    port = free_port()
    env = os.environ.copy()
    env.update(
        {
            "AIOS_OWNER_USERNAME": "owner",
            "AIOS_OWNER_PASSWORD_SALT": "screenshot-salt",
            "AIOS_OWNER_PASSWORD_HASH": hash_password(PASSWORD, "screenshot-salt"),
            "AIOS_SECURE_COOKIES": "0",
            "AIOS_SECURITY_TEST_BYPASS": "0",
            "AIOS_BACKEND_URL": f"http://127.0.0.1:{port}",
        }
    )
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
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    try:
        wait_for_server(port)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)

            desktop = browser.new_page(viewport={"width": 1440, "height": 1000})
            sign_in(desktop, port)
            desktop.locator('.nav-item[data-view="command-center"]').click()
            desktop.locator(
                '#view-command-center [data-command-module="copilot"]'
            ).click()
            desktop.locator("#copilotAvatar").wait_for()
            desktop.screenshot(
                path=SCREENSHOTS / "copilot-desktop.png",
                full_page=True,
            )

            mobile = browser.new_page(viewport={"width": 390, "height": 844})
            sign_in(mobile, port)
            mobile.locator("#mobileMoreBtn").click()
            mobile.locator('#mobileMoreMenu [data-view="health-operations"]').click()
            mobile.locator("#view-health-operations").wait_for()
            mobile.locator("#healthDomainGrid .health-domain-card").first.wait_for(
                timeout=30_000
            )
            mobile.screenshot(
                path=SCREENSHOTS / "health-operations-mobile.png",
                full_page=True,
            )

            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    main()
