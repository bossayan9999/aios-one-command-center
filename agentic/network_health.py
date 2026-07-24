from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

HEALTHY = "healthy"
DEGRADED = "degraded"
OFFLINE = "offline"
AUTH_REQUIRED = "auth_required"
MISCONFIGURED = "misconfigured"
TIMEOUT = "timeout"
ESCALATE = "escalate"


@dataclass
class HealthCheck:
    id: str
    name: str
    status: str
    latency_ms: float | None
    detail: str
    likely_cause: str
    recommended_action: str
    checked_at: str
    error_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _check_http(name: str, check_id: str, url: str, timeout: float = 3.0) -> HealthCheck:
    started = time.perf_counter()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "AIOS-Health/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(512)
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type and b"cloudflare" in body.lower():
                return HealthCheck(
                    check_id,
                    name,
                    AUTH_REQUIRED,
                    elapsed,
                    "Cloudflare Access returned HTML instead of the expected health response.",
                    "Cloudflare Access authentication may be required.",
                    "Re-authenticate to Cloudflare Access and retry.",
                    _now(),
                )
            return HealthCheck(
                check_id,
                name,
                HEALTHY,
                elapsed,
                f"HTTP {response.status}",
                "",
                "No action required.",
                _now(),
            )
    except urllib.error.HTTPError as exc:
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        status = AUTH_REQUIRED if exc.code in {301, 302, 401, 403} else DEGRADED
        cause = (
            "Authentication or access policy blocked the request."
            if status == AUTH_REQUIRED
            else "The remote endpoint returned an error."
        )
        return HealthCheck(
            check_id,
            name,
            status,
            elapsed,
            f"HTTP {exc.code}",
            cause,
            "Review the endpoint and Cloudflare Access policy.",
            _now(),
        )
    except TimeoutError:
        return HealthCheck(
            check_id,
            name,
            TIMEOUT,
            None,
            "Request timed out.",
            "The endpoint is slow or unreachable.",
            "Check the service, route, or tunnel.",
            _now(),
        )
    except Exception as exc:
        return HealthCheck(
            check_id,
            name,
            OFFLINE,
            None,
            f"{type(exc).__name__}: {exc}",
            "The endpoint could not be reached.",
            "Confirm the service is running and reachable.",
            _now(),
        )


def _default_gateway() -> str | None:
    if platform.system() != "Windows":
        return None
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | "
                "Sort-Object RouteMetric | Select-Object -First 1 "
                "-ExpandProperty NextHop)",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        value = completed.stdout.strip()
        return value or None
    except Exception:
        return None


def _ping(host: str, timeout_ms: int = 1200) -> tuple[bool, float | None]:
    count_flag = "-n" if platform.system() == "Windows" else "-c"
    wait_flag = "-w" if platform.system() == "Windows" else "-W"
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            ["ping", count_flag, "1", wait_flag, str(timeout_ms), host],
            capture_output=True,
            text=True,
            timeout=max(2, timeout_ms / 1000 + 1),
            check=False,
        )
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        return completed.returncode == 0, elapsed
    except Exception:
        return False, None


def _service_status(name: str) -> HealthCheck:
    if platform.system() != "Windows":
        return HealthCheck(
            "cloudflared-service",
            "Cloudflare service",
            MISCONFIGURED,
            None,
            "Windows service check is only available on Windows.",
            "Unsupported platform for this check.",
            "Use the platform service manager.",
            _now(),
        )
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-Service '{name}' -ErrorAction Stop).Status",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        status_text = completed.stdout.strip().lower()
        if completed.returncode == 0 and status_text == "running":
            return HealthCheck(
                "cloudflared-service",
                "Cloudflare service",
                HEALTHY,
                None,
                "cloudflared service is running.",
                "",
                "No action required.",
                _now(),
            )
        return HealthCheck(
            "cloudflared-service",
            "Cloudflare service",
            OFFLINE,
            None,
            status_text or completed.stderr.strip() or "Service is not running.",
            "The tunnel service is stopped or unavailable.",
            "Start or restart cloudflared from Administrator PowerShell.",
            _now(),
        )
    except Exception as exc:
        return HealthCheck(
            "cloudflared-service",
            "Cloudflare service",
            OFFLINE,
            None,
            str(exc),
            "The service could not be queried.",
            "Check Windows service permissions.",
            _now(),
        )


def run_network_health(root: Path, public_url: str) -> dict[str, Any]:
    checks: list[HealthCheck] = []
    checks.append(
        _check_http(
            "AIOS backend",
            "aios-local-health",
            "http://127.0.0.1:8000/health",
        )
    )
    checks.append(_service_status("cloudflared"))

    gateway = _default_gateway()
    if gateway:
        ok, latency = _ping(gateway)
        checks.append(
            HealthCheck(
                "router-gateway",
                "Router / gateway",
                HEALTHY if ok else OFFLINE,
                latency,
                f"Default gateway: {gateway}",
                "" if ok else "The local gateway did not answer the ping test.",
                "Check the router, adapter, or local network."
                if not ok
                else "No action required.",
                _now(),
            )
        )
    else:
        checks.append(
            HealthCheck(
                "router-gateway",
                "Router / gateway",
                MISCONFIGURED,
                None,
                "No default gateway detected.",
                "The active adapter may not have a route.",
                "Check Wi-Fi or Ethernet connection.",
                _now(),
            )
        )

    started = time.perf_counter()
    try:
        socket.getaddrinfo("cloudflare.com", 443)
        checks.append(
            HealthCheck(
                "dns",
                "DNS",
                HEALTHY,
                round((time.perf_counter() - started) * 1000, 1),
                "DNS resolution succeeded.",
                "",
                "No action required.",
                _now(),
            )
        )
    except Exception as exc:
        checks.append(
            HealthCheck(
                "dns",
                "DNS",
                OFFLINE,
                None,
                str(exc),
                "DNS resolution failed.",
                "Check DNS server and adapter settings.",
                _now(),
            )
        )

    checks.append(
        _check_http(
            "Internet",
            "internet",
            "https://cloudflare.com/cdn-cgi/trace",
        )
    )
    checks.append(
        _check_http(
            "Public AIOS",
            "public-aios",
            public_url.rstrip("/") + "/health",
            timeout=6.0,
        )
    )
    checks.append(
        _check_http(
            "Ollama",
            "ollama",
            "http://127.0.0.1:11434/api/tags",
            timeout=2.0,
        )
    )

    obsidian_backup = root / "data" / "obsidian_backups"
    if obsidian_backup.exists():
        files = [item for item in obsidian_backup.rglob("*") if item.is_file()]
        newest = max((item.stat().st_mtime for item in files), default=0)
        age_hours = (time.time() - newest) / 3600 if newest else None
        status = HEALTHY if age_hours is not None and age_hours <= 72 else DEGRADED
        detail = (
            f"{len(files)} backup files; newest is {age_hours:.1f} hours old."
            if age_hours is not None
            else "No backup files found."
        )
        checks.append(
            HealthCheck(
                "obsidian-backup",
                "Obsidian backup",
                status,
                None,
                detail,
                "" if status == HEALTHY else "Backups are missing or stale.",
                "Run an Obsidian export or backup.",
                _now(),
            )
        )
    else:
        checks.append(
            HealthCheck(
                "obsidian-backup",
                "Obsidian backup",
                DEGRADED,
                None,
                "Backup directory does not exist.",
                "Obsidian backup automation is not configured.",
                "Configure local backup first.",
                _now(),
            )
        )

    disk = shutil.disk_usage(root)
    memory = psutil.virtual_memory()
    process = psutil.Process(os.getpid())
    desktop = {
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": memory.percent,
        "process_memory_mb": round(process.memory_info().rss / (1024 ** 2), 1),
        "disk_free_gb": round(disk.free / (1024 ** 3), 2),
    }

    statuses = {item.status for item in checks}
    overall = HEALTHY
    if OFFLINE in statuses or ESCALATE in statuses:
        overall = DEGRADED
    if all(item.status in {OFFLINE, TIMEOUT} for item in checks[:2]):
        overall = OFFLINE

    return {
        "status": overall,
        "checked_at": _now(),
        "desktop": desktop,
        "checks": [item.as_dict() for item in checks],
    }

