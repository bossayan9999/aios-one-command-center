from __future__ import annotations

from typing import Any

SKILLS: list[dict[str, Any]] = [
    {
        "skill_id": "github-pr-triage",
        "name": "GitHub PR Triage",
        "allowed_tools": ["get_repo", "get_pr_info", "list_pr_changed_filenames", "get_commit_combined_status"],
        "blocked_actions": ["merge", "delete_repository", "manage_secrets"],
        "token_budget": 8000,
        "time_budget_minutes": 20,
        "approval_triggers": ["write_comment", "rerun_workflow", "merge"],
        "brain_vault_destination": "01-Projects/AIOS-ONE/Tasks",
    },
    {
        "skill_id": "cloudflare-safe-deploy",
        "name": "Safe Cloudflare Deployment",
        "allowed_tools": ["tunnel_health", "dns_read", "worker_preview", "analytics_read"],
        "blocked_actions": ["account_delete", "tunnel_delete", "policy_remove"],
        "token_budget": 10000,
        "time_budget_minutes": 30,
        "approval_triggers": ["dns_write", "worker_deploy", "access_policy_write"],
        "brain_vault_destination": "01-Projects/AIOS-ONE/Tasks",
    },
    {
        "skill_id": "supabase-rls-review",
        "name": "Supabase RLS Review",
        "allowed_tools": ["schema_read", "migration_read", "rls_read", "docs_search"],
        "blocked_actions": ["service_role_exposure", "disable_rls"],
        "token_budget": 12000,
        "time_budget_minutes": 35,
        "approval_triggers": ["migration_execute", "schema_write", "function_deploy"],
        "brain_vault_destination": "01-Projects/AIOS-ONE/Tasks",
    },
    {
        "skill_id": "brain-vault-retrieval",
        "name": "Brain Vault Retrieval",
        "allowed_tools": ["search_notes", "read_note", "list_project_notes"],
        "blocked_actions": ["arbitrary_file_read", "read_secrets"],
        "token_budget": 5000,
        "time_budget_minutes": 10,
        "approval_triggers": [],
        "brain_vault_destination": "01-Projects/AIOS-ONE/Tasks",
    },
    {
        "skill_id": "connector-health-diagnosis",
        "name": "Connector Health Diagnosis",
        "allowed_tools": ["connector_health", "list_tools", "read_configuration_status"],
        "blocked_actions": ["write_configuration", "rotate_secrets"],
        "token_budget": 6000,
        "time_budget_minutes": 15,
        "approval_triggers": ["change_configuration"],
        "brain_vault_destination": "01-Projects/AIOS-ONE/Diagnostics",
    },
]
