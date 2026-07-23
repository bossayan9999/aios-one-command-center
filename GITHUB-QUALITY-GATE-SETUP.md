# GitHub Quality Gate Setup

1. Push this project to the main AIOS ONE repository.
2. Open repository Settings → Branches.
3. Add a branch protection rule for `main`.
4. Require a pull request before merging.
5. Require these checks:
   - Ruff, Mypy, Pytest
   - Playwright Smoke
   - Release Gate
6. Require branches to be up to date before merging.
7. Block force pushes and branch deletion.
8. Keep deployment as a separate, approval-required workflow.

Never store provider keys, Cloudflare tokens, Supabase service-role keys, or
desktop credentials in the repository.
