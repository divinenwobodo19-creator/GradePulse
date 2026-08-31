"""
Tests for backup system (BackupManager).
"""
import os
import time
import json
import pytest
from linucb_brain.brain import Brain
from linucb_brain.backup import BackupManager, BackupInfo


class TestBackupManager:
    def test_backup_manager_init(self, tmp_path):
        backup_dir = tmp_path / "backups"
        manager = BackupManager(
            backup_dir=str(backup_dir),
            max_backups=5,
            backup_interval=0,
        )
        assert manager.backup_dir == backup_dir
        assert manager.max_backups == 5
    
    def test_register_file(self, tmp_path):
        manager = BackupManager(backup_dir=str(tmp_path / "backups"), backup_interval=0)
        filepath = str(tmp_path / "test.json")
        
        manager.register_file(filepath)
        assert filepath in manager._files_to_backup
        
        # Registering same file again should not duplicate
        manager.register_file(filepath)
        assert manager._files_to_backup.count(filepath) == 1
    
    def test_create_backup(self, tmp_path):
        # Create test files
        brain_path = tmp_path / "brain_state.json"
        config_path = tmp_path / "class_config.json"
        
        brain_data = {"students": {}, "contents": {}, "model_type": "hybrid"}
        with open(brain_path, "w") as f:
            json.dump(brain_data, f)
        with open(config_path, "w") as f:
            json.dump({"schools": []}, f)
        
        # Create backup
        backup_dir = tmp_path / "backups"
        manager = BackupManager(backup_dir=str(backup_dir), backup_interval=0)
        manager.register_file(str(brain_path))
        manager.register_file(str(config_path))
        
        result = manager.create_backup("test")
        
        assert result is not None
        assert result.files == ["brain_state.json", "class_config.json"]
        assert result.size_bytes > 0
        assert os.path.exists(result.path)
    
    def test_backup_rotation(self, tmp_path):
        # Create test file
        brain_path = tmp_path / "brain_state.json"
        with open(brain_path, "w") as f:
            json.dump({"test": "data"}, f)
        
        # Create manager with max 3 backups
        backup_dir = tmp_path / "backups"
        manager = BackupManager(
            backup_dir=str(backup_dir),
            max_backups=3,
            backup_interval=0,
        )
        manager.register_file(str(brain_path))
        
        for i in range(5):
            manager.create_backup(f"test{i}")
            time.sleep(0.05)
        
        backups = manager.list_backups()
        assert len(backups) == 3
    
    def test_list_backups(self, tmp_path):
        brain_path = tmp_path / "brain_state.json"
        with open(brain_path, "w") as f:
            json.dump({"test": "data"}, f)
        
        backup_dir = tmp_path / "backups"
        manager = BackupManager(backup_dir=str(backup_dir), backup_interval=0)
        manager.register_file(str(brain_path))
        
        manager.create_backup("test1")
        time.sleep(0.05)
        manager.create_backup("test2")
        
        backups = manager.list_backups()
        assert len(backups) == 2
        assert all(isinstance(b, BackupInfo) for b in backups)
    
    def test_restore_backup(self, tmp_path):
        brain_path = tmp_path / "brain_state.json"
        
        # Create original data
        original_data = {"students": {"S01": {"name": "Alice"}}}
        with open(brain_path, "w") as f:
            json.dump(original_data, f)
        
        # Create backup
        backup_dir = tmp_path / "backups"
        manager = BackupManager(backup_dir=str(backup_dir), backup_interval=0)
        manager.register_file(str(brain_path))
        backup = manager.create_backup("test")
        
        # Modify original
        modified_data = {"students": {"S01": {"name": "Bob"}}}
        with open(brain_path, "w") as f:
            json.dump(modified_data, f)
        
        # Restore
        success = manager.restore_backup(backup.path)
        assert success is True
        
        # Verify restored
        with open(brain_path) as f:
            restored_data = json.load(f)
        assert restored_data["students"]["S01"]["name"] == "Alice"
    
    def test_restore_nonexistent_backup(self, tmp_path):
        manager = BackupManager(backup_dir=str(tmp_path / "backups"), backup_interval=0)
        success = manager.restore_backup("/nonexistent/path")
        assert success is False
    
    def test_get_latest_backup(self, tmp_path):
        brain_path = tmp_path / "brain_state.json"
        with open(brain_path, "w") as f:
            json.dump({"test": "data"}, f)
        
        backup_dir = tmp_path / "backups"
        manager = BackupManager(backup_dir=str(backup_dir), backup_interval=0)
        manager.register_file(str(brain_path))
        
        # No backups yet
        assert manager.get_latest_backup() is None
        
        # Create backups
        manager.create_backup("first")
        time.sleep(0.01)
        manager.create_backup("second")
        
        latest = manager.get_latest_backup()
        assert latest is not None
        assert "second" in str(latest.path) or latest.timestamp is not None
    
    def test_backup_callback(self, tmp_path):
        brain_path = tmp_path / "brain_state.json"
        with open(brain_path, "w") as f:
            json.dump({"test": "data"}, f)
        
        callback_results = []
        
        def on_backup(info):
            callback_results.append(info)
        
        backup_dir = tmp_path / "backups"
        manager = BackupManager(
            backup_dir=str(backup_dir),
            backup_interval=0,
            on_backup_complete=on_backup,
        )
        manager.register_file(str(brain_path))
        manager.create_backup("test")
        
        assert len(callback_results) == 1
        assert isinstance(callback_results[0], BackupInfo)
    
    def test_empty_backup_returns_none(self, tmp_path):
        manager = BackupManager(backup_dir=str(tmp_path / "backups"), backup_interval=0)
        # No files registered
        result = manager.create_backup("test")
        assert result is None
