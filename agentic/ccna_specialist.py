from __future__ import annotations

from typing import Any

ACCEPTABLE_STATUSES = {"healthy", "auth_required", "disabled"}


def _repair_for(check: dict[str, Any]) -> dict[str, Any]:
    identity = f"{check.get('id', '')} {check.get('name', '')}".casefold()
    title = "Review the affected network service"
    rollback = "Restore the previous service or adapter configuration."

    if "cloudflare" in identity or "tunnel" in identity:
        title = "Restore the Cloudflare Tunnel service"
        rollback = "Restore the previous cloudflared service configuration and restart it."
    elif "dns" in identity:
        title = "Validate and repair DNS resolution"
        rollback = "Restore the previous DNS server addresses and resolver settings."
    elif "gateway" in identity or "router" in identity:
        title = "Validate the default gateway and local route"
        rollback = "Restore the previous adapter, route, and gateway configuration."
    elif "internet" in identity:
        title = "Trace the internet connectivity failure"
        rollback = "Restore the previous adapter and proxy configuration."
    elif "aios" in identity or "backend" in identity:
        title = "Restore the local AIOS service path"
        rollback = "Stop the replacement process and restart the previously configured service."

    return {
        "id": f"repair-{check.get('id', 'network')}",
        "title": title,
        "evidence": check.get("detail") or "The health check did not return healthy.",
        "likely_cause": check.get("likely_cause") or "Cause requires verification.",
        "recommended_action": check.get("recommended_action") or title,
        "approval_required": True,
        "execution": "governed_task_only",
        "rollback": rollback,
    }


def build_ccna_analysis(health: dict[str, Any]) -> dict[str, Any]:
    checks = list(health.get("checks") or [])
    findings = [
        {
            "id": check.get("id", "unknown"),
            "name": check.get("name") or check.get("id") or "Unknown check",
            "status": check.get("status", "unknown"),
            "evidence": check.get("detail") or "No detail returned.",
            "likely_cause": check.get("likely_cause") or "",
        }
        for check in checks
        if str(check.get("status", "unknown")).casefold() not in ACCEPTABLE_STATUSES
    ]
    proposals = [
        _repair_for(check)
        for check in checks
        if any(finding["id"] == check.get("id") for finding in findings)
    ]
    evidence_lines = [f"{item['name']} [{item['status']}]: {item['evidence']}" for item in findings]
    task_message = (
        "CCNA network repair request. Diagnose and repair only from the recorded "
        "evidence below. Use read-only checks first. Request owner approval before "
        "desktop, service, route, DNS, tunnel, firewall, or router changes. Verify "
        "connectivity after any approved change and preserve rollback steps.\n\n"
        + ("\n".join(evidence_lines) if evidence_lines else "All network checks are healthy.")
    )
    return {
        "specialist": {
            "id": "ccna",
            "name": "CCNA Network Specialist",
            "status": "ready",
            "authority": "diagnose_and_propose",
        },
        "status": "attention_required" if findings else "healthy",
        "summary": (
            f"{len(findings)} network issue(s) need review."
            if findings
            else "No network faults were found in the current evidence."
        ),
        "checked_at": health.get("checked_at"),
        "findings": findings,
        "repair_proposals": proposals,
        "task_message": task_message,
        "executed_changes": [],
    }
