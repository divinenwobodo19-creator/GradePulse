"""
Automated backup system for GradePulse brain state and configuration.

Provides:
- Periodic backups of brain_state.json and class_config.json
- Backup rotation with configurable retention
- Backup restoration with validation
- Atomic file operations to prevent corruption
"""
import os
import shutil
import time
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class BackupInfo:
    """Information about a single backup."""
    path: str
    timestamp: datetime
    size_bytes: int
    files: List[str]


class BackupManager:
    """
    Manages automated backups of GradePulse state files.
    
    Features:
    - Periodic backup on configurable interval
    - Atomic file copy (write to temp, then rename)
    - Configurable retention policy (max backups)
    - Backup metadata tracking
    - Safe restoration with validation
    """
    
    def __init__(
        self,
        backup_dir: str = "backups",
        max_backups: int = 24,
        backup_interval: float = 21600.0,  # 6 hours
        on_backup_complete: Optional[callable] = None,
    ):
        """
        Initialize the backup manager.
        
        Args:
            backup_dir: Directory to store backups
            max_backups: Maximum number of backups to keep (0 = unlimited)
            backup_interval: Seconds between backups
            on_backup_complete: Optional callback after successful backup
        """
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        self.backup_interval = backup_interval
        self.on_backup_complete = on_backup_complete
        
        self._stop_event = threading.Event()
        self._backup_thread: Optional[threading.Thread] = None
        self._files_to_backup: List[str] = []
        self._backup_count = 0
    
    def register_file(self, filepath: str):
        """Register a file for backup."""
        filepath = os.path.abspath(filepath)
        if filepath not in self._files_to_backup:
            self._files_to_backup.append(filepath)
    
    def start(self):
        """Start the periodic backup thread."""
        if self.backup_interval <= 0:
            return
        
        self._stop_event.clear()
        self._backup_thread = threading.Thread(
            target=self._backup_loop,
            daemon=True,
            name="backup-manager"
        )
        self._backup_thread.start()
    
    def stop(self):
        """Stop the periodic backup thread."""
        self._stop_event.set()
        if self._backup_thread:
            self._backup_thread.join(timeout=5.0)
            self._backup_thread = None
    
    def _backup_loop(self):
        """Main backup loop running in background thread."""
        while not self._stop_event.is_set():
            # Wait for the interval or until stopped
            self._stop_event.wait(self.backup_interval)
            
            if not self._stop_event.is_set():
                try:
                    self.create_backup("periodic")
                except Exception as e:
                    print(f"Warning: Periodic backup failed: {e}")
    
    def create_backup(self, reason: str = "manual") -> Optional[BackupInfo]:
        """
        Create a backup of all registered files.
        
        Args:
            reason: Reason for backup (for metadata)
            
        Returns:
            BackupInfo if successful, None if no files to backup
        """
        if not self._files_to_backup:
            return None
        
        # Create backup directory
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate backup folder name with timestamp (microsecond precision to avoid collisions)
        timestamp = datetime.now()
        backup_name = timestamp.strftime("%Y%m%d_%H%M%S_%f")
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Copy files atomically
        copied_files = []
        for filepath in self._files_to_backup:
            if not os.path.exists(filepath):
                continue
            
            filename = os.path.basename(filepath)
            dest = backup_path / filename
            
            # Atomic copy: write to temp file, then rename
            temp_path = dest.with_suffix(dest.suffix + ".tmp")
            try:
                shutil.copy2(filepath, temp_path)
                temp_path.rename(dest)
                copied_files.append(filename)
            except Exception as e:
                print(f"Warning: Failed to backup {filename}: {e}")
                if temp_path.exists():
                    temp_path.unlink()
        
        if not copied_files:
            backup_path.rmdir()
            return None
        
        # Write backup metadata
        metadata = {
            "timestamp": timestamp.isoformat(),
            "reason": reason,
            "files": copied_files,
            "worker_pid": os.getpid(),
        }
        meta_path = backup_path / "_backup_meta.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        # Calculate total size
        total_size = sum(
            (backup_path / f).stat().st_size
            for f in copied_files
            if (backup_path / f).exists()
        )
        
        backup_info = BackupInfo(
            path=str(backup_path),
            timestamp=timestamp,
            size_bytes=total_size,
            files=copied_files,
        )
        
        self._backup_count += 1
        
        # Rotation: remove old backups if over limit
        if self.max_backups > 0:
            self._rotate_backups()
        
        if self.on_backup_complete:
            self.on_backup_complete(backup_info)
        
        return backup_info
    
    def _rotate_backups(self):
        """Remove oldest backups if over max_backups limit."""
        backups = self.list_backups()
        if len(backups) <= self.max_backups:
            return
        
        # Sort by timestamp (oldest first)
        backups.sort(key=lambda b: b.timestamp)
        
        # Remove excess backups
        to_remove = backups[:len(backups) - self.max_backups]
        for backup in to_remove:
            try:
                shutil.rmtree(backup.path)
            except Exception as e:
                print(f"Warning: Failed to remove old backup {backup.path}: {e}")
    
    def list_backups(self) -> List[BackupInfo]:
        """List all available backups."""
        backups = []
        
        if not self.backup_dir.exists():
            return backups
        
        for entry in self.backup_dir.iterdir():
            if not entry.is_dir():
                continue
            
            meta_path = entry / "_backup_meta.json"
            if meta_path.exists():
                with open(meta_path) as f:
                    meta = json.load(f)
                
                backups.append(BackupInfo(
                    path=str(entry),
                    timestamp=datetime.fromisoformat(meta["timestamp"]),
                    size_bytes=sum(
                        (entry / fn).stat().st_size
                        for fn in meta.get("files", [])
                        if (entry / fn).exists()
                    ),
                    files=meta.get("files", []),
                ))
        
        return backups
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        Restore files from a backup.
        
        Args:
            backup_path: Path to the backup directory
            
        Returns:
            True if successful, False otherwise
        """
        backup_dir = Path(backup_path)
        
        if not backup_dir.exists():
            print(f"Error: Backup path does not exist: {backup_path}")
            return False
        
        # Read metadata
        meta_path = backup_dir / "_backup_meta.json"
        if not meta_path.exists():
            print(f"Error: No backup metadata found at {meta_path}")
            return False
        
        with open(meta_path) as f:
            meta = json.load(f)
        
        # Restore each file
        restored = []
        for filename in meta.get("files", []):
            src = backup_dir / filename
            if not src.exists():
                print(f"Warning: File {filename} not found in backup")
                continue
            
            # Find the original path
            original_path = None
            for registered in self._files_to_backup:
                if os.path.basename(registered) == filename:
                    original_path = registered
                    break
            
            if original_path is None:
                print(f"Warning: No registered path for {filename}")
                continue
            
            # Atomic restore
            temp_path = original_path + ".restore.tmp"
            try:
                shutil.copy2(src, temp_path)
                os.replace(temp_path, original_path)
                restored.append(filename)
            except Exception as e:
                print(f"Error restoring {filename}: {e}")
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        
        return len(restored) > 0
    
    def get_latest_backup(self) -> Optional[BackupInfo]:
        """Get the most recent backup."""
        backups = self.list_backups()
        if not backups:
            return None
        return max(backups, key=lambda b: b.timestamp)
