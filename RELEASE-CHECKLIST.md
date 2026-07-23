# AIOS ONE Release Checklist

A release is eligible only when all required items pass.

## Automated gates

- [ ] Ruff lint passes
- [ ] Mypy passes
- [ ] Pytest regression suite passes
- [ ] Playwright browser smoke passes
- [ ] Python compilation passes
- [ ] No critical dependency or secret scan findings

## Product verification

- [ ] Login and tenant boundary tested
- [ ] Mission creation and completion tested
- [ ] Model preflight tested
- [ ] Provider switching tested
- [ ] Mission History tested
- [ ] Obsidian export tested
- [ ] Desktop Companion approval tested
- [ ] Emergency stop tested
- [ ] Backup and restore demonstrated
- [ ] Deployment rollback demonstrated
- [ ] Mobile navigation tested

## Release evidence

- [ ] Git commit recorded
- [ ] CI run URL recorded
- [ ] Version and release notes prepared
- [ ] Backup created before deployment
- [ ] Post-deployment health check passed
- [ ] Rollback package available
