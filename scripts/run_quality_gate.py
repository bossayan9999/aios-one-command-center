from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULT_FILE = ROOT / "quality-gate-results.json"


def run_check(
    name: str,
    command: list[str],
    *,
    required: bool = True,
    timeout: int = 300,
) -> dict[str, Any]:
    executable = command[0]
    module_name = command[2] if command[:2] == [sys.executable, "-m"] and len(command) > 2 else ""
    available = True

    if module_name:
        try:
            __import__(module_name)
        except ImportError:
            available = False
    elif shutil.which(executable) is None:
        available = False

    if not available:
        return {
            "name": name,
            "status": "failed" if required else "skipped",
            "required": required,
            "command": " ".join(command),
            "exit_code": 127,
            "stdout": "",
            "stderr": f"Required tool is not installed: {module_name or executable}",
        }

    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "name": name,
            "status": "passed" if completed.returncode == 0 else "failed",
            "required": required,
            "command": " ".join(command),
            "exit_code": completed.returncode,
            "stdout": completed.stdout[-12000:],
            "stderr": completed.stderr[-12000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "status": "failed",
            "required": required,
            "command": " ".join(command),
            "exit_code": 124,
            "stdout": (exc.stdout or "")[-12000:] if isinstance(exc.stdout, str) else "",
            "stderr": f"Timed out after {timeout} seconds.",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AIOS ONE development quality gates.")
    parser.add_argument(
        "--include-e2e",
        action="store_true",
        help="Run Playwright browser smoke tests.",
    )
    parser.add_argument(
        "--allow-missing-dev-tools",
        action="store_true",
        help="Mark missing Ruff/Mypy/Playwright installations as skipped for local diagnostics.",
    )
    args = parser.parse_args()

    allow_missing = args.allow_missing_dev_tools
    checks = [
        run_check(
            "Python compile",
            [sys.executable, "-m", "compileall", "-q", "api", "agentic", "security", "scripts"],
        ),
        run_check(
            "Ruff lint",
            [sys.executable, "-m", "ruff", "check", "."],
            required=not allow_missing,
        ),
        run_check(
            "Mypy types",
            [sys.executable, "-m", "mypy"],
            required=not allow_missing,
        ),
        run_check(
            "Pytest regression",
            [sys.executable, "-m", "pytest", "-q", "-m", "not e2e"],
        ),
    ]

    if args.include_e2e:
        checks.append(
            run_check(
                "Playwright browser smoke",
                [sys.executable, "-m", "pytest", "-q", "-m", "e2e"],
                required=not allow_missing,
                timeout=420,
            )
        )

    required_failed = any(
        item["required"] and item["status"] != "passed" for item in checks
    )
    payload: dict[str, Any] = {
        "status": "failed" if required_failed else "passed",
        "generated_at": datetime.now(UTC).isoformat(),
        "checks": checks,
        "summary": {
            "passed": sum(item["status"] == "passed" for item in checks),
            "failed": sum(item["status"] == "failed" for item in checks),
            "skipped": sum(item["status"] == "skipped" for item in checks),
            "total": len(checks),
        },
    }
    RESULT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    for item in checks:
        print(f"[{item['status'].upper():7}] {item['name']}")
        if item["status"] == "failed":
            detail = item["stderr"] or item["stdout"]
            if detail:
                print(detail[-2000:])

    quality_status = str(payload["status"])
    print(f"\nQuality gate: {quality_status.upper()}")
    print(f"Results: {RESULT_FILE}")
    return 1 if required_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
