
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
