# AIOS ONE Phase 1A Security Foundation

## Added

- owner login and logout
- PBKDF2 password hashing
- HttpOnly session cookie
- secure and SameSite=Strict cookie policy
- session expiration
- revoke-all sessions
- CSRF double-submit validation
- login rate limiting
- owner-only Desktop Companion boundary
- authentication for API routes
- security audit events
- security response headers
- login interface
- owner configuration helper
- dedicated authentication and CSRF tests
- Playwright login flow

## Validation

- Python syntax passed
- JavaScript syntax passed
- regression suite passed
- real unauthenticated-request block passed
- owner login passed
- authenticated API read passed
- missing-CSRF rejection passed
- valid-CSRF write passed
- logout and session revocation passed

## Setup

1. Run `python scripts\configure_owner.py`.
2. Load `.env.security` before starting Uvicorn.
3. Keep `AIOS_SECURE_COOKIES=1` for `https://aios.bossayan.com`.
4. Never commit `.env.security`.
