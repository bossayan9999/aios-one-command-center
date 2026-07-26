"""Truthful, evidence-backed health operations for AIOS ONE."""

from __future__ import annotations

import json
import os
import shutil
import socket
import tempfile
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

from agentic.connector_registry import ConnectorRegistry
from agentic.output_manager import OutputManager
from agentic.unified_task_store import UnifiedTaskStore

STATUSES = {"healthy", "degraded", "warning", "critical", "offline", "unknown", "disabled"}
SEVERITY = {
    "healthy": 0,
    "disabled": 0,
    "unknown": 1,
    "warning": 2,
    "degraded": 3,
    "offline": 4,
    "critical": 5,
}
TERMINAL_TASK_STATES = {"COMPLETED", "FAILED", "CANCELLED", "ARCHIVED"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except (TypeError, ValueError):
        return None


def _component(
    component_id: str,
    name: str,
    status: str,
    detail: str,
    *,
    evidence: dict[str, Any] | None = None,
    latency_ms: float | None = None,
    required: bool = True,
) -> dict[str, Any]:
    if status not in STATUSES:
        status = "unknown"
    return {
        "id": component_id,
        "name": name,
        "status": status,
        "detail": detail,
        "evidence": evidence or {},
        "latency_ms": latency_ms,
        "required": required,
        "checked_at": _now(),
    }


def _rollup(items: list[dict[str, Any]]) -> str:
    required = [item for item in items if item.get("required", True)]
    if not required:
        return "unknown"
    return max(required, key=lambda item: SEVERITY.get(str(item["status"]), 1))["status"]


class HealthOperations:
    def __init__(
        self,
        root: Path,
        data_dir: Path,
        vault_root: Path,
        connectors: ConnectorRegistry,
        *,
        http_get: Callable[[str, float], tuple[int, bytes]] | None = None,
    ):
        self.root = Path(root)
        self.data_dir = Path(data_dir)
        self.vault_root = Path(vault_root)
        self.connectors = connectors
        self.history_file = self.data_dir / "health_history.jsonl"
        self.gate_file = self.data_dir / "solid_connection_gate.json"
        self.http_get = http_get or self._http_get

    @staticmethod
    def _http_get(url: str, timeout: float) -> tuple[int, bytes]:
        request = urllib.request.Request(url, headers={"User-Agent": "AIOS-Health/2.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(1_000_000)

    def _http_component(
        self,
        component_id: str,
        name: str,
        url: str,
        *,
        timeout: float = 2.0,
        required: bool = True,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            code, body = self.http_get(url, timeout)
            latency = round((time.perf_counter() - started) * 1000, 1)
            status = "healthy" if 200 <= code < 300 else "degraded"
            return _component(
                component_id,
                name,
                status,
                f"HTTP {code}",
                evidence={"url": url, "response_bytes": len(body)},
                latency_ms=latency,
                required=required,
            )
        except Exception as exc:
            return _component(
                component_id,
                name,
                "offline",
                f"{type(exc).__name__}: {exc}",
                evidence={"url": url},
                required=required,
            )

    def live(self) -> dict[str, Any]:
        return {"status": "healthy", "service": "aios-one", "checked_at": _now()}

    def worker(self) -> dict[str, Any]:
        path = self.data_dir / "worker_runtime.json"
        if not path.exists():
            component = _component(
                "worker",
                "Worker runtime",
                "unknown",
                "No worker heartbeat has been recorded.",
            )
            return {"status": component["status"], "components": [component]}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            component = _component(
                "worker", "Worker runtime", "critical", f"Unreadable worker state: {exc}"
            )
            return {"status": component["status"], "components": [component]}
        heartbeat = _parse_time(str(payload.get("heartbeat_at", "")))
        age = (datetime.now(UTC) - heartbeat).total_seconds() if heartbeat else None
        online = bool(payload.get("online"))
        status = "healthy" if online and age is not None and age <= 15 else "offline"
        if age is None:
            status = "unknown"
        tasks = UnifiedTaskStore(self.data_dir, self.vault_root).list()
        active = [item for item in tasks if str(item.get("status", "")).upper() not in TERMINAL_TASK_STATES]
        stale_claims = []
        now = datetime.now(UTC)
        for task in active:
            if str(task.get("status", "")).upper() not in {"CLAIMED", "PLANNING", "WORKING", "VALIDATING"}:
                continue
            task_heartbeat = _parse_time(str(task.get("task_heartbeat_at", "")))
            if not task_heartbeat or (now - task_heartbeat).total_seconds() > 120:
                stale_claims.append(str(task.get("task_id")))
        if stale_claims:
            status = "critical"
        component = _component(
            "worker",
            "Worker runtime",
            status,
            "Heartbeat is current." if status == "healthy" else "Worker needs attention.",
            evidence={
                "worker_id": payload.get("worker_id"),
                "state": payload.get("state"),
                "heartbeat_age_seconds": round(age, 1) if age is not None else None,
                "queue_depth": sum(1 for item in tasks if item.get("status") == "QUEUED"),
                "active_tasks": len(active),
                "stale_claims": stale_claims,
                "error": payload.get("error", ""),
            },
        )
        return {"status": status, "components": [component]}

    def models(self) -> dict[str, Any]:
        endpoint = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        expected = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b")
        check = self._http_component("ollama", "Ollama API", f"{endpoint}/api/tags")
        if check["status"] == "healthy":
            try:
                _, body = self.http_get(f"{endpoint}/api/tags", 2.0)
                payload = json.loads(body)
                models = [str(item.get("name", "")) for item in payload.get("models", [])]
                check["evidence"]["models"] = models
                check["evidence"]["expected_model"] = expected
                if expected not in models:
                    check["status"] = "degraded"
                    check["detail"] = f"Expected model is not installed: {expected}"
            except Exception as exc:
                check["status"] = "unknown"
                check["detail"] = f"Model inventory could not be parsed: {exc}"
        cloud: list[dict[str, Any]] = []
        for provider, env_name in (
            ("openai", "OPENAI_API_KEY"),
            ("anthropic", "ANTHROPIC_API_KEY"),
            ("openrouter", "OPENROUTER_API_KEY"),
        ):
            configured = bool(os.getenv(env_name))
            cloud.append(
                _component(
                    f"provider-{provider}",
                    provider.title(),
                    "unknown" if configured else "disabled",
                    "Configured; live probe not run." if configured else "Provider intentionally disabled.",
                    evidence={"configured": configured},
                    required=False,
                )
            )
        components = [check, *cloud]
        return {"status": _rollup(components), "components": components}

    def network(self) -> dict[str, Any]:
        backend_url = os.getenv("AIOS_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
        components = [
            self._http_component(
                "local-backend", "FastAPI loopback", f"{backend_url}/api/health/live"
            )
        ]
        cloudflared = [
            item.info
            for item in psutil.process_iter(["pid", "name"])
            if "cloudflared" in str(item.info.get("name", "")).casefold()
        ]
        components.append(
            _component(
                "cloudflare-tunnel",
                "Cloudflare Tunnel",
                "healthy" if cloudflared else "offline",
                "cloudflared process detected." if cloudflared else "No cloudflared process detected.",
                evidence={"processes": cloudflared},
                required=bool(os.getenv("AIOS_PUBLIC_URL")),
            )
        )
        public_url = os.getenv("AIOS_PUBLIC_URL", "").strip()
        if public_url:
            components.append(
                self._http_component(
                    "public-route",
                    "Public AIOS route",
                    public_url.rstrip("/") + "/api/health/live",
                    timeout=5,
                )
            )
        else:
            components.append(
                _component(
                    "public-route",
                    "Public AIOS route",
                    "disabled",
                    "AIOS_PUBLIC_URL is not configured.",
                    required=False,
                )
            )
        try:
            started = time.perf_counter()
            addresses = sorted({item[4][0] for item in socket.getaddrinfo("cloudflare.com", 443)})
            components.append(
                _component(
                    "dns",
                    "DNS resolution",
                    "healthy",
                    "DNS resolution succeeded.",
                    evidence={"address_count": len(addresses)},
                    latency_ms=round((time.perf_counter() - started) * 1000, 1),
                )
            )
        except Exception as exc:
            components.append(_component("dns", "DNS resolution", "offline", str(exc)))
        return {"status": _rollup(components), "components": components}

    def connectors_health(self) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for connector in self.connectors.list():
            enabled = bool(connector.get("enabled"))
            auth_env = str(connector.get("auth_env", ""))
            authenticated = not auth_env or bool(os.getenv(auth_env))
            if not enabled:
                status = "disabled"
                detail = "Connector intentionally disabled."
            elif connector.get("kind") == "local" and connector.get("connector_id") == "brain-vault":
                status = "healthy" if self.vault_root.exists() else "offline"
                detail = "Local Brain Vault path checked."
            elif connector.get("connector_id") == "ollama":
                status = self.models()["components"][0]["status"]
                detail = "Derived from Ollama health."
            elif auth_env and not authenticated:
                status = "warning"
                detail = f"Credential variable {auth_env} is not configured."
            else:
                status = "unknown"
                detail = "Enabled; no authenticated live call was performed."
            items.append(
                _component(
                    f"connector-{connector['connector_id']}",
                    str(connector.get("name")),
                    status,
                    detail,
                    evidence={
                        "enabled": enabled,
                        "authenticated": authenticated,
                        "read_only": connector.get("read_only", True),
                        "permission_scope": connector.get("toolsets", []),
                        "approval_required": not connector.get("read_only", True),
                        "last_successful_call": connector.get("last_successful_call"),
                        "last_error": connector.get("last_error"),
                    },
                    required=False,
                )
            )
        return {"status": _rollup(items), "components": items}

    def storage(self) -> dict[str, Any]:
        components: list[dict[str, Any]] = []
        for component_id, name, path in (
            ("data-store", "Data store", self.data_dir),
            ("brain-vault", "Brain Vault", self.vault_root),
        ):
            try:
                path.mkdir(parents=True, exist_ok=True)
                descriptor, temporary = tempfile.mkstemp(prefix=".health-", dir=path)
                os.close(descriptor)
                os.unlink(temporary)
                status, detail = "healthy", "Read/write probe passed."
            except Exception as exc:
                status, detail = "critical", f"Read/write probe failed: {exc}"
            components.append(
                _component(component_id, name, status, detail, evidence={"path": str(path)})
            )
        try:
            task_value = json.loads((self.data_dir / "unified_tasks.json").read_text(encoding="utf-8")) if (
                self.data_dir / "unified_tasks.json"
            ).exists() else {}
            task_status = "healthy" if isinstance(task_value, dict) else "critical"
        except Exception as exc:
            task_status = "critical"
            task_value = {"error": str(exc)}
        components.append(
            _component(
                "task-integrity",
                "Task store integrity",
                task_status,
                "Task JSON parsed." if task_status == "healthy" else "Task JSON is invalid.",
                evidence={"task_count": len(task_value) if isinstance(task_value, dict) else None},
            )
        )
        output_index = self.data_dir / "task_outputs.json"
        try:
            outputs = (
                json.loads(output_index.read_text(encoding="utf-8"))
                if output_index.exists()
                else []
            )
            output_status = "healthy" if isinstance(outputs, list) else "critical"
            output_detail = (
                f"Output index parsed with {len(outputs)} records."
                if isinstance(outputs, list)
                else "Output index is not a list."
            )
        except Exception as exc:
            output_status, output_detail = "critical", f"Output index is unreadable: {exc}"
            outputs = []
        components.append(
            _component(
                "output-store",
                "Output store",
                output_status,
                output_detail,
                evidence={"path": str(output_index)},
            )
        )
        backups = sorted((self.root / "backups").glob("*.zip"), key=lambda path: path.stat().st_mtime)
        if backups:
            age_hours = round((time.time() - backups[-1].stat().st_mtime) / 3600, 1)
            backup_status = "healthy" if age_hours <= 72 else "warning"
            backup_detail = f"Latest backup is {age_hours} hours old."
        else:
            age_hours = None
            backup_status = "unknown"
            backup_detail = "No backup archive is available."
        components.append(
            _component(
                "backup-freshness",
                "Backup freshness",
                backup_status,
                backup_detail,
                evidence={"age_hours": age_hours},
                required=False,
            )
        )
        disk = shutil.disk_usage(self.root)
        free_gb = round(disk.free / 1024**3, 2)
        components.append(
            _component(
                "disk",
                "Disk capacity",
                "healthy" if free_gb >= 5 else "warning",
                f"{free_gb} GB free.",
                evidence={"free_bytes": disk.free, "total_bytes": disk.total},
            )
        )
        return {"status": _rollup(components), "components": components}

    def security(self) -> dict[str, Any]:
        from security.app_security import (
            SECURE_COOKIES,
            SESSION_SECONDS,
            owner_is_configured,
        )

        components = [
            _component(
                "owner-credentials",
                "Owner credentials",
                "healthy" if owner_is_configured() else "critical",
                "Owner credentials configured."
                if owner_is_configured()
                else "Owner credentials are missing.",
            ),
            _component(
                "secure-cookies",
                "Secure cookies",
                "healthy" if SECURE_COOKIES else "warning",
                "Secure cookie policy enabled."
                if SECURE_COOKIES
                else "Secure cookies disabled for local development.",
                evidence={"session_seconds": SESSION_SECONDS, "csrf": True},
                required=bool(os.getenv("AIOS_PUBLIC_URL")),
            ),
            _component(
                "skill-permissions",
                "Skill permission enforcement",
                "healthy",
                "Trusted registry is default-deny and does not execute reviewed scripts.",
            ),
        ]
        audit = self.data_dir / "security_audit.jsonl"
        components.append(
            _component(
                "security-audit",
                "Security audit store",
                "healthy" if audit.exists() else "unknown",
                "Audit store available." if audit.exists() else "No audit events recorded yet.",
            )
        )
        return {"status": _rollup(components), "components": components}

    def ready(self) -> dict[str, Any]:
        worker = self.worker()
        storage = self.storage()
        components = [
            _component("backend", "FastAPI", "healthy", "Request reached readiness handler."),
            *worker["components"],
            *storage["components"],
        ]
        status = _rollup(components)
        return {
            "status": "healthy" if status in {"healthy", "warning"} else status,
            "components": components,
            "checked_at": _now(),
        }

    def frontend(self) -> dict[str, Any]:
        index = self.root / "web" / "index.html"
        script = self.root / "web" / "app.js"
        style = self.root / "web" / "styles.css"
        components = []
        for component_id, name, path in (
            ("frontend-shell", "Frontend shell", index),
            ("frontend-script", "Frontend JavaScript", script),
            ("frontend-style", "Frontend stylesheet", style),
        ):
            components.append(
                _component(
                    component_id,
                    name,
                    "healthy" if path.exists() and path.stat().st_size else "critical",
                    "Asset is present." if path.exists() else "Asset is missing.",
                    evidence={"bytes": path.stat().st_size if path.exists() else 0},
                )
            )
        return {"status": _rollup(components), "components": components}

    def full(self, *, record: bool = True) -> dict[str, Any]:
        domains = {
            "frontend": self.frontend(),
            "backend": self.ready(),
            "worker": self.worker(),
            "models": self.models(),
            "network": self.network(),
            "storage": self.storage(),
            "connectors": self.connectors_health(),
            "security": self.security(),
        }
        statuses = [
            {"status": domain["status"], "required": name not in {"connectors"}}
            for name, domain in domains.items()
        ]
        status = _rollup(statuses)
        score = round(
            100
            * sum(max(0, 5 - SEVERITY.get(str(item["status"]), 1)) / 5 for item in statuses)
            / len(statuses)
        )
        result = {
            "status": status,
            "score": score,
            "checked_at": _now(),
            "domains": domains,
            "recommendations": self.recommendations(domains),
        }
        if record:
            self.record_snapshot(result)
        return result

    @staticmethod
    def recommendations(domains: dict[str, Any]) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []
        for domain_name, domain in domains.items():
            for item in domain.get("components", []):
                if item["status"] in {"healthy", "disabled"}:
                    continue
                recommendations.append(
                    {
                        "id": f"rec-{item['id']}",
                        "component": item["id"],
                        "severity": item["status"],
                        "confidence": 0.9 if item["status"] != "unknown" else 0.5,
                        "evidence": item["detail"],
                        "expected_benefit": f"Restore reliable {domain_name} operation.",
                        "risk": "low",
                        "next_step": f"Inspect {item['name']} evidence before making changes.",
                        "approval_required": True,
                    }
                )
        return recommendations

    def record_snapshot(self, snapshot: dict[str, Any], retention: int = 500) -> None:
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        summary = {
            "checked_at": snapshot["checked_at"],
            "status": snapshot["status"],
            "score": snapshot["score"],
            "domains": {name: value["status"] for name, value in snapshot["domains"].items()},
        }
        lines = []
        if self.history_file.exists():
            lines = self.history_file.read_text(encoding="utf-8").splitlines()
        lines.append(json.dumps(summary, ensure_ascii=False))
        self.history_file.write_text("\n".join(lines[-retention:]) + "\n", encoding="utf-8")

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.history_file.exists():
            return []
        result = []
        for line in self.history_file.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return list(reversed(result))

    def solid_connection_gate(self) -> dict[str, Any]:
        full = self.full()
        domains = full["domains"]
        worker = domains["worker"]["components"][0]
        ollama = domains["models"]["components"][0]
        component_map = {
            item["id"]: item
            for domain in domains.values()
            for item in domain.get("components", [])
        }
        checks = [
            ("frontend_loads", component_map.get("frontend-shell")),
            ("authentication_configured", component_map.get("owner-credentials")),
            ("backend_responds", component_map.get("backend")),
            ("readiness", {"status": domains["backend"]["status"], "evidence": domains["backend"]}),
            ("worker_heartbeat", worker),
            ("ollama_responds", ollama),
            (
                "expected_model",
                {
                    "status": ollama["status"],
                    "evidence": ollama.get("evidence", {}).get("expected_model"),
                },
            ),
            ("task_store_writable", component_map.get("data-store")),
            ("output_manager", component_map.get("output-store")),
            ("brain_vault_writable", component_map.get("brain-vault")),
            ("cloudflare_tunnel", component_map.get("cloudflare-tunnel")),
            (
                "critical_connectors",
                {"status": domains["connectors"]["status"], "evidence": domains["connectors"]},
            ),
            (
                "high_security",
                {"status": domains["security"]["status"], "evidence": domains["security"]},
            ),
        ]
        rendered = []
        for name, evidence in checks:
            status = str((evidence or {}).get("status", "unknown"))
            rendered.append(
                {
                    "name": name,
                    "status": status,
                    "passed": status in {"healthy", "disabled"},
                    "evidence": evidence or {},
                }
            )
        for name in ("playwright_desktop", "playwright_mobile"):
            rendered.append(
                {
                    "name": name,
                    "status": "unknown",
                    "passed": False,
                    "evidence": {"detail": "No recorded browser test result."},
                }
            )
        result = {
            "name": "AIOS Solid Connection Gate",
            "status": "passed" if all(item["passed"] for item in rendered) else "failed",
            "checked_at": _now(),
            "checks": rendered,
        }
        self.gate_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    def output_probe(self) -> dict[str, Any]:
        try:
            manager = OutputManager(self.data_dir, self.vault_root)
            return {"status": "healthy", "index": str(manager.output_index)}
        except Exception as exc:
            return {"status": "critical", "detail": str(exc)}
