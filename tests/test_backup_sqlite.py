"""
Backups of the live SQLite database: copied through SQLite (WAL writes
included), restored only from our own backup folder, after an integrity
check, and never over by the engine's in-memory state.
"""
import json
import os
import sqlite3

from linucb_brain.backup import BackupManager, is_sqlite


def _wal_db(path):
    """A WAL-mode database with a write still in the -wal file (connection kept open)."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("CREATE TABLE users (email TEXT)")
    conn.execute("INSERT INTO users VALUES ('first@school.ng')")
    conn.commit()
    return conn


def _emails(path):
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute("SELECT email FROM users ORDER BY email")]
    finally:
        conn.close()


def _manager(tmp_path, *files, max_backups=24):
    m = BackupManager(backup_dir=str(tmp_path / "backups"), backup_interval=0, max_backups=max_backups)
    for f in files:
        m.register_file(str(f))
    return m


def test_backup_includes_writes_still_in_the_wal_file(tmp_path):
    db = tmp_path / "gradepulse_users.db"
    live = _wal_db(db)
    assert os.path.getsize(str(db) + "-wal") > 0  # the row is only in the WAL
    backup = _manager(tmp_path, db).create_backup("test")
    copy = os.path.join(backup.path, "gradepulse_users.db")
    assert is_sqlite(copy) and _emails(copy) == ["first@school.ng"]
    assert backup.files == ["gradepulse_users.db"]  # no -wal/-shm copied loose
    live.close()


def test_sidecar_files_are_not_registered(tmp_path):
    m = _manager(tmp_path, tmp_path / "x.db", tmp_path / "x.db-wal", tmp_path / "x.db-shm")
    assert m._files_to_backup == [str(tmp_path / "x.db")]


def test_restore_writes_into_the_live_database_and_keeps_a_pre_restore_copy(tmp_path):
    db = tmp_path / "gradepulse_users.db"
    live = _wal_db(db)
    m = _manager(tmp_path, db)
    backup = m.create_backup("test")
    live.execute("INSERT INTO users VALUES ('later@school.ng')")
    live.commit()

    result = m.restore_backup(os.path.basename(backup.path))  # by folder name
    assert result["restored"] == ["gradepulse_users.db"]
    assert _emails(db) == ["first@school.ng"]
    assert [r[0] for r in live.execute("SELECT email FROM users")] == ["first@school.ng"]  # open connections see it
    assert _emails(os.path.join(result["pre_restore"], "gradepulse_users.db")) == ["first@school.ng", "later@school.ng"]
    live.close()


def test_only_backups_inside_the_backup_folder_can_be_restored(tmp_path):
    state = tmp_path / "brain_state.json"
    state.write_text(json.dumps({"students": {}}))
    m = _manager(tmp_path, state)
    m.create_backup("test")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "_backup_meta.json").write_text(json.dumps({"timestamp": "2026-01-01T00:00:00", "files": ["brain_state.json"]}))
    (outside / "brain_state.json").write_text(json.dumps({"students": {"X": {}}}))
    assert m.restore_backup(str(outside)) is None
    assert m.restore_backup(str(tmp_path / "backups" / ".." / "elsewhere")) is None
    assert json.loads(state.read_text()) == {"students": {}}


def test_a_damaged_backup_restores_nothing(tmp_path):
    db = tmp_path / "gradepulse_users.db"
    state = tmp_path / "brain_state.json"
    state.write_text(json.dumps({"students": {}}))
    live = _wal_db(db)
    m = _manager(tmp_path, db, state)
    backup = m.create_backup("test")
    with open(os.path.join(backup.path, "gradepulse_users.db"), "r+b") as f:
        f.seek(100)
        f.write(b"\xff" * 4000)  # corrupt the copy
    state.write_text(json.dumps({"students": {"NEW": {}}}))

    assert m.restore_backup(backup.path) is None
    assert _emails(db) == ["first@school.ng"]
    assert json.loads(state.read_text()) == {"students": {"NEW": {}}}  # untouched: all or nothing
    live.close()


def test_restoring_the_oldest_backup_survives_rotation(tmp_path):
    state = tmp_path / "brain_state.json"
    state.write_text(json.dumps({"v": 1}))
    m = _manager(tmp_path, state, max_backups=2)
    oldest = m.create_backup("one")
    state.write_text(json.dumps({"v": 2}))
    m.create_backup("two")
    state.write_text(json.dumps({"v": 3}))
    # The pre-restore backup rotates the oldest folder away mid-restore.
    assert m.restore_backup(oldest.path)["restored"] == ["brain_state.json"]
    assert json.loads(state.read_text()) == {"v": 1}


# ── Through the API ──────────────────────────────────────────────────────────

import uuid  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from conftest import OPERATOR_HEADERS  # noqa: E402
from linucb_brain.api import app as app_module  # noqa: E402


def _signup(client):
    email = f"restore_{uuid.uuid4().hex[:8]}@restore.local"
    r = client.post("/auth/signup", json={"email": email, "password": "Kettle-Mango-42", "school_name": "Restore School"})
    assert r.status_code == 200, r.text
    return email


def _can_login(client, email):
    return client.post("/auth/login", json={"email": email, "password": "Kettle-Mango-42"}).status_code == 200


def test_restore_endpoint_restores_accounts_and_reloads_the_engine(tmp_path, monkeypatch):
    # Other suites import the app with backups off; turn them on for this one.
    monkeypatch.setattr(app_module, "BACKUP_ENABLED", True)
    monkeypatch.setattr(app_module, "BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(app_module, "backup_manager", app_module.backup_manager)  # put back afterwards
    with TestClient(app_module.app) as client:
        app_module.SIGNUP_LIMITER.reset()
        assert app_module.backup_manager is not None
        before = _signup(client)
        backup = client.post("/backup", headers=OPERATOR_HEADERS).json()
        after = _signup(client)
        engine_before = app_module.brain_instance

        r = client.post("/backup/restore", headers=OPERATOR_HEADERS,
                        params={"backup_path": os.path.basename(backup["path"])})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "gradepulse_users.db" in body["restored"] and body["pre_restore_backup"]
        assert _can_login(client, before) and not _can_login(client, after)
        assert app_module.brain_instance is not engine_before  # reloaded from the restored file

        r = client.post("/backup/restore", headers=OPERATOR_HEADERS, params={"backup_path": "/etc"})
        assert r.status_code == 404
        assert client.post("/backup/restore", params={"backup_path": "x"}).status_code == 403
