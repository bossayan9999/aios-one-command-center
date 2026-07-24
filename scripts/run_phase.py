from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "phase-runs"

FORBIDDEN_EXACT = {
    ".env",
    ".env.security",
    "quality-gate-results.json",
}
FORBIDDEN_PREFIXES = (
    "data/",
    "logs/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    "backups/",
)
FORBIDDEN_FRAGMENTS = (
    "backup",
    ".bak",
    ".tmp",
    "installer",
    "fragments/",
)

PHASE_FOCUSED_TESTS: dict[str, list[str]] = {
    "phase-1d": [
        "tests/test_governance.py",
        "tests/test_governance_integration.py",
        "tests/test_governance_rules_page.py",
        "tests/test_auth_frontend_resilience.py",
    ],
    "phase-1e": [
        "tests/test_reliability_registry.py",
        "tests/test_mission_lifecycle.py",
        "tests/test_reliability_api.py",
        "tests/test_reliability_frontend.py",
    ],
}


@dataclass
class StepResult:
    name: str
    command: list[str]
    status: str
    exit_code: int
    duration_seconds: float
    stdout: str
    stderr: str


def run(command: Sequence[str], *, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], timeout=120)


def ensure_repo() -> None:
    if not (ROOT / ".git").exists():
        raise SystemExit(f"Not a Git repository: {ROOT}")
    if not (ROOT / "scripts" / "run_quality_gate.py").exists():
        raise SystemExit("Missing scripts/run_quality_gate.py")


def current_branch() -> str:
    result = git("branch", "--show-current")
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "Unable to read current branch.")
    return result.stdout.strip()


def changed_paths(staged: bool = False) -> list[str]:
    args = ["diff", "--name-only"]
    if staged:
        args.append("--cached")
    result = git(*args)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "Unable to inspect Git changes.")
    paths = [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]
    if not staged:
        untracked = git("ls-files", "--others", "--exclude-standard")
        if untracked.returncode == 0:
            paths.extend(
                line.strip().replace("\\", "/")
                for line in untracked.stdout.splitlines()
                if line.strip()
            )
    return sorted(set(paths))


def forbidden_paths(paths: Sequence[str]) -> list[str]:
    bad: list[str] = []
    for path in paths:
        lowered = path.lower()
        name = Path(lowered).name
        if lowered in FORBIDDEN_EXACT:
            bad.append(path)
            continue
        if any(lowered.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            bad.append(path)
            continue
        if any(fragment in lowered for fragment in FORBIDDEN_FRAGMENTS):
            bad.append(path)
            continue
        if name.startswith(".env"):
            bad.append(path)
    return sorted(set(bad))


def existing_focused_tests(phase: str, extra: Sequence[str]) -> tuple[list[str], list[str]]:
    requested = [*PHASE_FOCUSED_TESTS.get(phase, []), *extra]
    present: list[str] = []
    missing: list[str] = []
    for item in dict.fromkeys(requested):
        if (ROOT / item).exists():
            present.append(item)
        else:
            missing.append(item)
    return present, missing


def execute_step(name: str, command: list[str], *, timeout: int = 900) -> StepResult:
    started = datetime.now(UTC)
    print(f"\n=== {name} ===")
    print(" ".join(command))
    try:
        completed = run(command, timeout=timeout)
        elapsed = (datetime.now(UTC) - started).total_seconds()
        status = "passed" if completed.returncode == 0 else "failed"
        print(f"[{status.upper()}] {name} ({elapsed:.1f}s)")
        if completed.stdout.strip():
            print(completed.stdout[-4000:])
        if completed.stderr.strip():
            print(completed.stderr[-4000:], file=sys.stderr)
        return StepResult(
            name=name,
            command=command,
            status=status,
            exit_code=completed.returncode,
            duration_seconds=elapsed,
            stdout=completed.stdout[-12000:],
            stderr=completed.stderr[-12000:],
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = (datetime.now(UTC) - started).total_seconds()
        stderr = f"Timed out after {timeout} seconds."
        print(f"[FAILED] {name}: {stderr}", file=sys.stderr)
        return StepResult(
            name=name,
            command=command,
            status="failed",
            exit_code=124,
            duration_seconds=elapsed,
            stdout=(exc.stdout or "")[-12000:] if isinstance(exc.stdout, str) else "",
            stderr=stderr,
        )


def write_report(
    *,
    phase: str,
    branch: str,
    steps: Sequence[StepResult],
    missing_tests: Sequence[str],
    changed: Sequence[str],
    status: str,
) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = REPORT_DIR / f"{phase}-{stamp}.json"
    payload = {
        "phase": phase,
        "branch": branch,
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "python": sys.executable,
        "changed_paths": list(changed),
        "missing_focused_tests": list(missing_tests),
        "steps": [asdict(step) for step in steps],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the reusable AIOS ONE engineering validation workflow."
    )
    parser.add_argument("phase", help="Phase key, for example phase-1e")
    parser.add_argument(
        "--expected-branch",
        help="Require an exact branch name before running.",
    )
    parser.add_argument(
        "--focused",
        action="append",
        default=[],
        metavar="TEST_PATH",
        help="Add a focused pytest file. May be repeated.",
    )
    parser.add_argument(
        "--allow-missing-focused",
        action="store_true",
        help="Do not fail when configured focused test files do not exist yet.",
    )
    parser.add_argument(
        "--fix-ruff",
        action="store_true",
        help="Run Ruff auto-fix before validation.",
    )
    parser.add_argument(
        "--commit",
        metavar="MESSAGE",
        help="Commit all safe changed files after every gate passes.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push the current branch after a successful commit or clean validation.",
    )
    parser.add_argument(
        "--skip-e2e",
        action="store_true",
        help="Skip Playwright in the final quality gate.",
    )
    args = parser.parse_args()

    ensure_repo()
    branch = current_branch()
    print(f"Repository: {ROOT}")
    print(f"Branch: {branch}")
    print(f"Python: {sys.executable}")

    if args.expected_branch and branch != args.expected_branch:
        print(
            f"BLOCKED: expected branch '{args.expected_branch}', found '{branch}'.",
            file=sys.stderr,
        )
        return 2
    if branch in {"main", "master"} and (args.commit or args.push):
        print("BLOCKED: commit/push automation is not allowed on main/master.", file=sys.stderr)
        return 2

    changed = changed_paths()
    unsafe = forbidden_paths(changed)
    if unsafe:
        print("BLOCKED: unsafe or generated files are present:", file=sys.stderr)
        for path in unsafe:
            print(f"  - {path}", file=sys.stderr)
        return 2

    staged_unsafe = forbidden_paths(changed_paths(staged=True))
    if staged_unsafe:
        print("BLOCKED: forbidden files are staged:", file=sys.stderr)
        for path in staged_unsafe:
            print(f"  - {path}", file=sys.stderr)
        return 2

    focused, missing = existing_focused_tests(args.phase, args.focused)
    if missing:
        print("Missing configured focused tests:")
        for path in missing:
            print(f"  - {path}")
        if not args.allow_missing_focused:
            print("BLOCKED: create the missing focused tests or use --allow-missing-focused.")
            return 2

    steps: list[StepResult] = []
    if args.fix_ruff:
        steps.append(
            execute_step(
                "Ruff auto-fix",
                [sys.executable, "-m", "ruff", "check", ".", "--fix"],
            )
        )
        if steps[-1].status == "failed":
            report = write_report(
                phase=args.phase,
                branch=branch,
                steps=steps,
                missing_tests=missing,
                changed=changed,
                status="failed",
            )
            print(f"Report: {report}")
            return 1

    steps.append(
        execute_step(
            "Python compile",
            [sys.executable, "-m", "compileall", "-q", "agentic", "api", "security", "scripts", "tests"],
        )
    )

    if focused:
        steps.append(
            execute_step(
                "Focused tests",
                [sys.executable, "-m", "pytest", "-q", *focused],
                timeout=600,
            )
        )

    steps.append(
        execute_step("Ruff lint", [sys.executable, "-m", "ruff", "check", "."])
    )
    steps.append(execute_step("Mypy types", [sys.executable, "-m", "mypy", "."]))
    steps.append(
        execute_step(
            "Pytest regression",
            [sys.executable, "-m", "pytest", "-q", "-m", "not e2e"],
            timeout=900,
        )
    )

    quality_command = [sys.executable, "scripts/run_quality_gate.py"]
    if not args.skip_e2e:
        quality_command.append("--include-e2e")
    steps.append(execute_step("Complete quality gate", quality_command, timeout=1200))

    failed = [step for step in steps if step.status != "passed"]
    status = "failed" if failed else "passed"
    report = write_report(
        phase=args.phase,
        branch=branch,
        steps=steps,
        missing_tests=missing,
        changed=changed_paths(),
        status=status,
    )
    print(f"\nWorkflow status: {status.upper()}")
    print(f"Report: {report}")

    if failed:
        print("No commit or push was performed.")
        return 1

    if args.commit:
        latest_changed = changed_paths()
        unsafe_after = forbidden_paths(latest_changed)
        if unsafe_after:
            print("BLOCKED before commit: unsafe files appeared:", file=sys.stderr)
            for path in unsafe_after:
                print(f"  - {path}", file=sys.stderr)
            return 2
        if not latest_changed:
            print("Nothing to commit.")
        else:
            add = git("add", "--", *latest_changed)
            if add.returncode != 0:
                print(add.stderr, file=sys.stderr)
                return add.returncode
            staged_bad = forbidden_paths(changed_paths(staged=True))
            if staged_bad:
                git("restore", "--staged", ".")
                print("BLOCKED: forbidden files became staged.", file=sys.stderr)
                return 2
            commit = git("commit", "-m", args.commit)
            print(commit.stdout)
            if commit.returncode != 0:
                print(commit.stderr, file=sys.stderr)
                return commit.returncode

    if args.push:
        push = git("push", "-u", "origin", branch)
        print(push.stdout)
        if push.returncode != 0:
            print(push.stderr, file=sys.stderr)
            return push.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
