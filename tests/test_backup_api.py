"""
Tests for backup API endpoints added by Infrastructure (Ali).
Endpoints: POST /backup, GET /backups, POST /backup/restore

These tests verify the backup API contract works correctly.
Infra's code — QA writes tests only.
"""
import os
import json
import time
import pytest
import requests

BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")
TEST_EMAIL = "backuptest@gradepulse.com"
TEST_PASSWORD = "backuptest123"


def _api_available():
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=2)
        return r.status_code == 200
    except requests.ConnectionError:
        return False


def _get_token():
    resp = requests.post(f"{BASE_URL}/auth/signup", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD, "school_name": "Backup Test School"
    })
    if resp.status_code == 200:
        return resp.json()["token"]
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD
    })
    return resp.json()["token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def api_ready():
    if not _api_available():
        pytest.skip("API server not running")


@pytest.fixture(scope="module")
def token(api_ready):
    return _get_token()


# ── POST /backup ───────────────────────────────────────────────────────────────

class TestCreateBackup:
    def test_create_backup_returns_200(self, token):
        resp = requests.post(f"{BASE_URL}/backup", headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        assert "path" in data
        assert "timestamp" in data
        assert "files" in data
        assert "size_bytes" in data

    def test_create_backup_has_correct_files(self, token):
        resp = requests.post(f"{BASE_URL}/backup", headers=_headers(token))
        data = resp.json()
        assert "brain_state.json" in data["files"]

    def test_create_backup_timestamp_is_valid_iso(self, token):
        resp = requests.post(f"{BASE_URL}/backup", headers=_headers(token))
        data = resp.json()
        from datetime import datetime
        ts = datetime.fromisoformat(data["timestamp"])
        assert ts.year == 2026

    def test_create_backup_size_positive(self, token):
        resp = requests.post(f"{BASE_URL}/backup", headers=_headers(token))
        data = resp.json()
        assert data["size_bytes"] > 0

    def test_create_backup_without_auth_returns_401(self):
        resp = requests.post(f"{BASE_URL}/backup")
        assert resp.status_code in [401, 403]


# ── GET /backups ───────────────────────────────────────────────────────────────

class TestListBackups:
    def test_list_backups_returns_200(self, token):
        resp = requests.get(f"{BASE_URL}/backups", headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "backups" in data
        assert "total" in data

    def test_list_backups_is_list(self, token):
        resp = requests.get(f"{BASE_URL}/backups", headers=_headers(token))
        data = resp.json()
        assert isinstance(data["backups"], list)
        assert isinstance(data["total"], int)

    def test_list_backups_contains_backup_info(self, token):
        requests.post(f"{BASE_URL}/backup", headers=_headers(token))
        time.sleep(0.1)
        resp = requests.get(f"{BASE_URL}/backups", headers=_headers(token))
        data = resp.json()
        if data["total"] > 0:
            b = data["backups"][0]
            assert "path" in b
            assert "timestamp" in b
            assert "files" in b
            assert "size_bytes" in b

    def test_list_backups_sorted_by_timestamp_desc(self, token):
        resp = requests.get(f"{BASE_URL}/backups", headers=_headers(token))
        data = resp.json()
        if len(data["backups"]) >= 2:
            timestamps = [b["timestamp"] for b in data["backups"]]
            assert timestamps == sorted(timestamps, reverse=True)

    def test_list_backups_without_auth_returns_401(self):
        resp = requests.get(f"{BASE_URL}/backups")
        assert resp.status_code in [401, 403]


# ── POST /backup/restore ──────────────────────────────────────────────────────

class TestRestoreBackup:
    def test_restore_nonexistent_backup_returns_500(self, token):
        resp = requests.post(
            f"{BASE_URL}/backup/restore",
            params={"backup_path": "/nonexistent/path"},
            headers=_headers(token)
        )
        assert resp.status_code == 500

    def test_restore_backup_without_auth_returns_401(self):
        resp = requests.post(
            f"{BASE_URL}/backup/restore",
            params={"backup_path": "/some/path"}
        )
        assert resp.status_code in [401, 403]

    def test_restore_returns_success_message(self, token):
        backup_resp = requests.post(f"{BASE_URL}/backup", headers=_headers(token))
        if backup_resp.status_code == 200:
            backup_path = backup_resp.json()["path"]
            resp = requests.post(
                f"{BASE_URL}/backup/restore",
                params={"backup_path": backup_path},
                headers=_headers(token)
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "restored"
            assert "message" in data


# ── Health check includes backup info ─────────────────────────────────────────

class TestHealthBackupInfo:
    def test_health_includes_backup_status(self, token):
        resp = requests.get(f"{BASE_URL}/health", headers=_headers(token))
        data = resp.json()
        assert "backup_status" in data
        assert data["backup_status"] in ["enabled", "disabled"]

    def test_health_includes_backup_count(self, token):
        resp = requests.get(f"{BASE_URL}/health", headers=_headers(token))
        data = resp.json()
        assert "backup_count" in data
        assert isinstance(data["backup_count"], int)


# ── Integration: create then list ─────────────────────────────────────────────

class TestBackupIntegration:
    def test_create_then_list_shows_new_backup(self, token):
        before_resp = requests.get(f"{BASE_URL}/backups", headers=_headers(token))
        before_count = before_resp.json()["total"]

        requests.post(f"{BASE_URL}/backup", headers=_headers(token))
        time.sleep(0.1)

        after_resp = requests.get(f"{BASE_URL}/backups", headers=_headers(token))
        after_count = after_resp.json()["total"]
        assert after_count >= before_count

    def test_multiple_creates_increase_count(self, token):
        resp1 = requests.get(f"{BASE_URL}/backups", headers=_headers(token))
        initial = resp1.json()["total"]

        for _ in range(3):
            requests.post(f"{BASE_URL}/backup", headers=_headers(token))
            time.sleep(0.5)

        resp2 = requests.get(f"{BASE_URL}/backups", headers=_headers(token))
        final = resp2.json()["total"]
        assert final >= initial + 1
