
from fastapi.testclient import TestClient

import security.app_security as app_security


def configured_client(monkeypatch, tmp_path):
    monkeypatch.setenv("AIOS_SECURITY_TEST_BYPASS", "0")
    salt = "test-salt"
    password = "correct horse battery staple"
    monkeypatch.setattr(app_security, "OWNER_USERNAME", "owner")
    monkeypatch.setattr(app_security, "OWNER_PASSWORD_SALT", salt)
    monkeypatch.setattr(
        app_security,
        "OWNER_PASSWORD_HASH",
        app_security.hash_password(password, salt),
    )
    monkeypatch.setattr(app_security, "SECURE_COOKIES", False)

    import api.main as main
    monkeypatch.setattr(main, "SECURITY_STORE", app_security.SecurityStore(tmp_path))
    monkeypatch.setattr(main, "SECURE_COOKIES", False)
    return TestClient(main.app), password


def login(client, password):
    response = client.post(
        "/api/auth/login",
        json={"username": "owner", "password": password},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_unauthenticated_api_is_blocked(monkeypatch, tmp_path):
    client, _ = configured_client(monkeypatch, tmp_path)
    response = client.get("/api/dashboard")
    assert response.status_code == 401


def test_owner_login_and_authenticated_read(monkeypatch, tmp_path):
    client, password = configured_client(monkeypatch, tmp_path)
    login(client, password)
    response = client.get("/api/dashboard")
    assert response.status_code == 200


def test_write_requires_csrf(monkeypatch, tmp_path):
    client, password = configured_client(monkeypatch, tmp_path)
    login(client, password)
    response = client.post(
        "/api/missions",
        json={
            "title": "Security test mission",
            "objective": "Verify CSRF protection",
            "privacy": "local",
            "output_type": "report",
        },
    )
    assert response.status_code == 403


def test_valid_csrf_allows_write(monkeypatch, tmp_path):
    client, password = configured_client(monkeypatch, tmp_path)
    csrf = login(client, password)
    response = client.post(
        "/api/missions",
        headers={"X-CSRF-Token": csrf},
        json={
            "title": "Security test mission",
            "objective": "Verify valid CSRF request",
            "privacy": "local",
            "output_type": "report",
        },
    )
    assert response.status_code == 200


def test_logout_revokes_session(monkeypatch, tmp_path):
    client, password = configured_client(monkeypatch, tmp_path)
    csrf = login(client, password)
    response = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert client.get("/api/dashboard").status_code == 401



def test_security_session_listing_and_revoke_others(monkeypatch, tmp_path):
    client, password = configured_client(monkeypatch, tmp_path)
    first_csrf = login(client, password)

    second = TestClient(client.app)
    second_login = second.post(
        "/api/auth/login",
        json={"username": "owner", "password": password},
    )
    assert second_login.status_code == 200

    sessions = client.get("/api/security/sessions")
    assert sessions.status_code == 200
    assert len(sessions.json()["items"]) == 2

    revoked = client.post(
        "/api/security/sessions/revoke-others",
        headers={"X-CSRF-Token": first_csrf},
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] == 1
    assert client.get("/api/dashboard").status_code == 200
    assert second.get("/api/dashboard").status_code == 401


def test_password_rotation_revokes_sessions(monkeypatch, tmp_path):
    client, password = configured_client(monkeypatch, tmp_path)
    csrf = login(client, password)
    response = client.post(
        "/api/security/password/rotate",
        headers={"X-CSRF-Token": csrf},
        json={
            "current_password": password,
            "new_password": "a completely different secure password",
        },
    )
    assert response.status_code == 200
    assert response.json()["rotated"] is True
    assert client.get("/api/dashboard").status_code == 401


def test_security_summary_flags_failed_logins(monkeypatch, tmp_path):
    client, password = configured_client(monkeypatch, tmp_path)
    login(client, password)
    for _ in range(3):
        failed = client.post(
            "/api/auth/login",
            json={"username": "owner", "password": "incorrect-password"},
        )
        assert failed.status_code == 401
    summary = client.get("/api/security/summary")
    assert summary.status_code == 200
    assert summary.json()["failed_logins_last_hour"] >= 3
    assert summary.json()["suspicious"] is True
