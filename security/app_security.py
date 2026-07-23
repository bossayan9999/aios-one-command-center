from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

SESSION_COOKIE = "aios_session"
CSRF_COOKIE = "aios_csrf"
SESSION_SECONDS = int(os.getenv("AIOS_SESSION_SECONDS", "28800"))
OWNER_USERNAME = os.getenv("AIOS_OWNER_USERNAME", "owner")
OWNER_PASSWORD_HASH = os.getenv("AIOS_OWNER_PASSWORD_HASH", "")
OWNER_PASSWORD_SALT = os.getenv("AIOS_OWNER_PASSWORD_SALT", "")
SECURE_COOKIES = os.getenv("AIOS_SECURE_COOKIES", "1") == "1"
LOGIN_WINDOW_SECONDS = 300
LOGIN_MAX_ATTEMPTS = 5


@dataclass
class SecurityStore:
    data_dir: Path

    @property
    def sessions_file(self) -> Path:
        return self.data_dir / "security_sessions.json"

    @property
    def audit_file(self) -> Path:
        return self.data_dir / "security_audit.jsonl"

    @property
    def attempts_file(self) -> Path:
        return self.data_dir / "security_login_attempts.json"

    def _read_json(self, path: Path, default: Any) -> Any:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return default

    def _write_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2), encoding="utf-8")

    def audit(self, event: str, request: Request, **details: Any) -> None:
        payload = {
            "at": time.time(),
            "event": event,
            "ip": request.client.host if request.client else "unknown",
            "path": request.url.path,
            **details,
        }
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def sessions(self) -> dict[str, dict[str, Any]]:
        return self._read_json(self.sessions_file, {})

    def save_sessions(self, sessions: dict[str, dict[str, Any]]) -> None:
        self._write_json(self.sessions_file, sessions)

    def create_session(self, username: str) -> tuple[str, str, float]:
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        expires_at = time.time() + SESSION_SECONDS
        sessions = self.sessions()
        sessions[hashlib.sha256(token.encode()).hexdigest()] = {
            "username": username,
            "role": "owner",
            "csrf": csrf,
            "expires_at": expires_at,
            "created_at": time.time(),
        }
        self.save_sessions(sessions)
        return token, csrf, expires_at

    def get_session(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        sessions = self.sessions()
        key = hashlib.sha256(token.encode()).hexdigest()
        session = sessions.get(key)
        if not session:
            return None
        if float(session.get("expires_at", 0)) <= time.time():
            sessions.pop(key, None)
            self.save_sessions(sessions)
            return None
        return session

    def revoke_session(self, token: str) -> bool:
        sessions = self.sessions()
        key = hashlib.sha256(token.encode()).hexdigest()
        removed = sessions.pop(key, None) is not None
        self.save_sessions(sessions)
        return removed

    def revoke_all(self) -> int:
        sessions = self.sessions()
        count = len(sessions)
        self.save_sessions({})
        return count


    def list_sessions(self, current_token: str = "") -> list[dict[str, Any]]:
        sessions = self.sessions()
        current_key = (
            hashlib.sha256(current_token.encode()).hexdigest()
            if current_token else ""
        )
        now = time.time()
        changed = False
        items: list[dict[str, Any]] = []
        for session_id, session in list(sessions.items()):
            expires_at = float(session.get("expires_at", 0) or 0)
            if expires_at <= now:
                sessions.pop(session_id, None)
                changed = True
                continue
            items.append({
                "id": session_id,
                "username": session.get("username", ""),
                "role": session.get("role", ""),
                "created_at": float(session.get("created_at", 0) or 0),
                "expires_at": expires_at,
                "current": hmac.compare_digest(session_id, current_key)
                if current_key else False,
            })
        if changed:
            self.save_sessions(sessions)
        return sorted(items, key=lambda item: item["created_at"], reverse=True)

    def revoke_session_id(self, session_id: str) -> bool:
        sessions = self.sessions()
        removed = sessions.pop(session_id, None) is not None
        if removed:
            self.save_sessions(sessions)
        return removed

    def revoke_other_sessions(self, current_token: str) -> int:
        current_key = hashlib.sha256(current_token.encode()).hexdigest()
        sessions = self.sessions()
        preserved = sessions.get(current_key)
        count = len(sessions) - (1 if preserved else 0)
        self.save_sessions({current_key: preserved} if preserved else {})
        return max(0, count)

    def audit_events(self, limit: int = 200) -> list[dict[str, Any]]:
        if not self.audit_file.exists():
            return []
        items: list[dict[str, Any]] = []
        for line in self.audit_file.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    items.append(value)
            except Exception:
                continue
        return list(reversed(items[-max(1, min(limit, 1000)):]))

    def security_summary(self) -> dict[str, Any]:
        events = self.audit_events(500)
        now = time.time()
        recent_failed = [
            item for item in events
            if item.get("event") == "login.failed"
            and now - float(item.get("at", 0) or 0) <= 3600
        ]
        denied = [
            item for item in events
            if item.get("event") == "access.denied"
            and now - float(item.get("at", 0) or 0) <= 3600
        ]
        return {
            "active_sessions": len(self.list_sessions()),
            "failed_logins_last_hour": len(recent_failed),
            "access_denied_last_hour": len(denied),
            "suspicious": len(recent_failed) >= 3 or len(denied) >= 10,
        }

    def check_rate_limit(self, request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        attempts = self._read_json(self.attempts_file, {})
        recent = [
            stamp for stamp in attempts.get(ip, [])
            if now - float(stamp) <= LOGIN_WINDOW_SECONDS
        ]
        attempts[ip] = recent
        self._write_json(self.attempts_file, attempts)
        if len(recent) >= LOGIN_MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    def record_failed_login(self, request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        attempts = self._read_json(self.attempts_file, {})
        recent = attempts.setdefault(ip, [])
        recent.append(time.time())
        attempts[ip] = recent[-LOGIN_MAX_ATTEMPTS:]
        self._write_json(self.attempts_file, attempts)


def hash_password(password: str, salt: str) -> str:
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 210_000)
    return derived.hex()


def owner_is_configured() -> bool:
    return bool(OWNER_PASSWORD_HASH and OWNER_PASSWORD_SALT)


def verify_owner(username: str, password: str) -> bool:
    if not owner_is_configured():
        return False
    if not hmac.compare_digest(username, OWNER_USERNAME):
        return False
    candidate = hash_password(password, OWNER_PASSWORD_SALT)
    return hmac.compare_digest(candidate, OWNER_PASSWORD_HASH)


def require_session(request: Request, store: SecurityStore) -> dict[str, Any]:
    token = request.cookies.get(SESSION_COOKIE, "")
    session = store.get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return session


def require_owner(request: Request, store: SecurityStore) -> dict[str, Any]:
    session = require_session(request, store)
    if session.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Owner permission required.")
    return session


def require_csrf(request: Request, store: SecurityStore) -> dict[str, Any]:
    session = require_session(request, store)
    expected = str(session.get("csrf", ""))
    supplied = request.headers.get("X-CSRF-Token", "")
    cookie = request.cookies.get(CSRF_COOKIE, "")
    if not expected or not supplied or not cookie:
        raise HTTPException(status_code=403, detail="CSRF token required.")
    if not hmac.compare_digest(expected, supplied) or not hmac.compare_digest(expected, cookie):
        raise HTTPException(status_code=403, detail="Invalid CSRF token.")
    return session
