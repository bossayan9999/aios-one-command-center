
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
    security_file = tmp_path / ".env.security"
    security_file.write_text(
        "AIOS_OWNER_USERNAME=owner\n"
        f"AIOS_OWNER_PASSWORD_SALT={salt}\n"
        "AIOS_OWNER_PASSWORD_HASH="
        f"{app_security.hash_password(password, salt)}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(app_security, "SECURITY_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(app_security, "SECURITY_ENV_PATH", security_file)
    monkeypatch.setattr(
        app_security,
        "_OWNER_CONFIG_MTIME_NS",
        security_file.stat().st_mtime_ns,
    )
    monkeypatch.setattr(app_security, "SECURE_COOKIES", False)

    import api.main as main

    test_data_dir = tmp_path / "data"
    test_data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(main, "DATA_DIR", test_data_dir)
    monkeypatch.setattr(main, "MISSIONS_FILE", test_data_dir / "missions.json")
    monkeypatch.setattr(main, "missions", {})
    monkeypatch.setattr(
        main,
        "RELIABILITY_REGISTRY",
        main.DefectRegistry(test_data_dir),
    )
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
    status = client.get("/api/auth/status")
    assert status.status_code == 200
    assert status.json()["username_hint"] == "owner"
    login(client, password)
    response = client.get("/api/dashboard")
    assert response.status_code == 200


def test_password_file_rotation_is_loaded_without_restart(monkeypatch, tmp_path):
    client, old_password = configured_client(monkeypatch, tmp_path)
    security_file = tmp_path / ".env.security"
    new_password = "new password loaded without restart"
    new_salt = "fresh-test-salt"
    security_file.write_text(
        "AIOS_OWNER_USERNAME=owner\n"
        f"AIOS_OWNER_PASSWORD_SALT={new_salt}\n"
        "AIOS_OWNER_PASSWORD_HASH="
        f"{app_security.hash_password(new_password, new_salt)}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(app_security, "SECURITY_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(app_security, "SECURITY_ENV_PATH", security_file)
    monkeypatch.setattr(app_security, "_OWNER_CONFIG_MTIME_NS", None)
    monkeypatch.setenv("AIOS_OWNER_USERNAME", app_security.OWNER_USERNAME)
    monkeypatch.setenv("AIOS_OWNER_PASSWORD_SALT", app_security.OWNER_PASSWORD_SALT)
    monkeypatch.setenv("AIOS_OWNER_PASSWORD_HASH", app_security.OWNER_PASSWORD_HASH)

    assert app_security.verify_owner("owner", new_password)
    assert not app_security.verify_owner("owner", old_password)


def test_local_http_login_cookie_is_not_secure(monkeypatch, tmp_path):
    client, password = configured_client(monkeypatch, tmp_path)
    import api.main as main

    monkeypatch.setattr(main, "SECURE_COOKIES", True)
    local_client = TestClient(main.app, base_url="http://127.0.0.1")
    response = local_client.post(
        "/api/auth/login",
        json={"username": "owner", "password": password},
    )
    assert response.status_code == 200
    assert all("Secure" not in value for value in response.headers.get_list("set-cookie"))
    assert local_client.get("/api/dashboard").status_code == 200


def test_forwarded_https_login_cookie_is_secure(monkeypatch, tmp_path):
    client, password = configured_client(monkeypatch, tmp_path)
    import api.main as main

    monkeypatch.setattr(main, "SECURE_COOKIES", True)
    response = client.post(
        "/api/auth/login",
        headers={"X-Forwarded-Proto": "https"},
        json={"username": "owner", "password": password},
    )
    assert response.status_code == 200
    assert all("Secure" in value for value in response.headers.get_list("set-cookie"))


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
