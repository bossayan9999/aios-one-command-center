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
    from security.app_security import hash_password
    env["AIOS_OWNER_USERNAME"] = "owner"
    env["AIOS_OWNER_PASSWORD_SALT"] = "playwright-salt"
    env["AIOS_OWNER_PASSWORD_HASH"] = hash_password(
        "correct horse battery staple",
        "playwright-salt",
    )
    env["AIOS_SECURE_COOKIES"] = "0"
    env["AIOS_SECURITY_TEST_BYPASS"] = "0"
    env["AIOS_BACKEND_URL"] = f"http://127.0.0.1:{port}"
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

    try:
        wait_for_server(port)
        with playwright.sync_playwright() as context:
            browser = context.chromium.launch(headless=True)
            file_launch = browser.new_page()
            file_launch.route(
                "http://127.0.0.1:8000/",
                lambda route: route.fulfill(
                    status=200,
                    content_type="text/html",
                    body="<title>AIOS server</title>",
                ),
            )
            file_launch.goto((ROOT / "web" / "index.html").as_uri())
            file_launch.wait_for_url("http://127.0.0.1:8000/", timeout=5_000)
            file_launch.close()

            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            root_response = page.goto(
                f"http://127.0.0.1:{port}/", wait_until="networkidle"
            )
            assert root_response is not None
            assert root_response.headers["cache-control"] == "no-store, max-age=0"

            assert page.locator("body").is_visible()
            page.locator("#securityUsername").fill("owner")
            page.locator("#securityPassword").fill("correct horse battery staple")
            page.locator("#securityLoginForm button[type=submit]").click()
            page.wait_for_timeout(500)
            assert page.locator("#securityLogin").is_hidden()
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
            assert page.locator("#iotDeviceForm").is_visible()
            page.locator(".iot-command-builder > summary").click()
            assert page.locator("#iotCommandForm").is_visible()

            page.locator('.nav-item[data-view="command-center"]').click()
            page.locator('[data-command-module="copilot"]').first.click()
            page.wait_for_timeout(300)
            assert page.locator("#copilotAvatar").is_visible()
            assert page.locator("#startCopilotListening").is_visible()
            assert page.locator("#copilotConnectivityGrid").is_hidden()
            assert not page.locator("#copilotReminderCenter").evaluate(
                "element => element.open"
            )
            assert page.locator("#managerDesktopStatus").is_visible()
            page.locator(
                '#managerDesktopStatus[data-status="healthy"]'
            ).wait_for(timeout=15_000)
            page.locator(".copilot-connectivity-center > summary").click()
            assert page.locator("#copilotConnectivityGrid").is_visible()
            page.locator(
                '#copilotConnectivityGrid [data-check="backend"][data-status="healthy"]'
            ).wait_for(timeout=20_000)
            page.locator("#testCopilotAssistantResponse").click()
            page.locator(
                '#copilotConnectivityGrid [data-check="assistant"][data-status="warning"], '
                '#copilotConnectivityGrid [data-check="assistant"][data-status="healthy"]'
            ).wait_for(timeout=30_000)

            page.locator('#view-copilot [data-command-module="projects"]').click()
            page.wait_for_timeout(300)
            assert page.locator("#projectGrid").is_visible()

            page.locator('.nav-item[data-view="copilot-search"]').click()
            page.locator("#copilotSearchInput").fill("AIOS")
            page.locator("#copilotSearchForm button[type=submit]").click()
            page.locator("#copilotSearchSummary").filter(
                has_text="RESULTS"
            ).wait_for(timeout=30_000)
            assert page.locator("#copilotSearchResults").is_visible()
            assert page.locator(".compact-copilot-avatar").is_visible()
            avatar_box = page.locator(".compact-copilot-avatar").bounding_box()
            assert avatar_box is not None
            assert avatar_box["width"] <= 80
            assert avatar_box["height"] <= 80
            assert page.locator("#copilotQuickMessageForm").is_visible()
            assert page.locator("#startCopilotQuickListening").is_visible()
            assert page.locator("#copilotQuickAutoSpeak").is_checked()
            assert page.locator("#openCopilotQuickCamera").is_visible()
            page.locator("#openCopilotQuickCamera").click()
            assert page.locator("#copilotDesktopCameraDialog").is_visible()
            page.locator("#cancelCopilotDesktopCamera").click()
            page.locator("#copilotDesktopCameraDialog").wait_for(state="hidden")

            page.locator('.nav-item[data-view="health-operations"]').click()
            page.wait_for_timeout(300)
            assert page.locator("#view-health-operations").is_visible()
            assert page.locator("#runFullHealthCheck").is_visible()
            page.locator(
                '#view-health-operations [data-operations-module="operations-terminal"]'
            ).click()
            page.locator("#operationsTerminalOutput").wait_for()
            page.locator("#operationsTerminalOutput").filter(
                has_text="[LIVENESS]"
            ).wait_for(timeout=30_000)
            page.locator(
                '#view-operations-terminal [data-operations-module="network-health"]'
            ).click()
            assert page.locator("#runNetworkHealth").is_visible()
            assert page.locator("#runCcnaAnalysis").is_visible()
            page.locator(
                '#view-network-health [data-operations-module="reliability"]'
            ).click()
            assert page.locator("#runReliabilityDiagnostics").is_visible()

            mobile = browser.new_page(viewport={"width": 390, "height": 844})
            mobile.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded")
            mobile.locator("#securityUsername").fill("owner")
            mobile.locator("#securityPassword").fill("correct horse battery staple")
            mobile.locator("#securityLoginForm button[type=submit]").click()
            mobile.wait_for_timeout(500)
            mobile.locator("#mobileMoreBtn").click()
            mobile.locator('#mobileMoreMenu [data-view="command-center"]').click()
            mobile.locator('#view-command-center [data-command-module="copilot"]').click()
            mobile.wait_for_timeout(250)
            assert mobile.locator("#copilotAvatar").is_visible()
            assert mobile.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            mobile.locator("#mobileMoreBtn").click()
            mobile.locator('#mobileMoreMenu [data-view="health-operations"]').click()
            mobile.wait_for_timeout(250)
            assert mobile.locator("#view-health-operations").is_visible()
            assert mobile.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            mobile.locator("#mobileMoreBtn").click()
            mobile.locator('#mobileMoreMenu [data-view="copilot-search"]').click()
            assert mobile.locator("#copilotSearchForm").is_visible()
            assert mobile.locator(".compact-copilot-avatar").is_visible()
            mobile_avatar_box = mobile.locator(".compact-copilot-avatar").bounding_box()
            assert mobile_avatar_box is not None
            assert mobile_avatar_box["width"] <= 54
            assert mobile_avatar_box["height"] <= 54
            assert mobile.locator("#startCopilotQuickListening").is_visible()
            assert mobile.locator("#openCopilotQuickCamera").is_visible()
            assert mobile.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            mobile.close()

            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
