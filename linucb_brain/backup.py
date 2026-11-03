"""
Automated backup system for GradePulse brain state and configuration.

Provides:
- Periodic backups of brain_state.json and class_config.json
- Backup rotation with configurable retention
- Backup restoration with validation
- Atomic file operations to prevent corruption

SQLite databases are copied with SQLite's own online backup, never as raw
files: the live database runs in WAL mode, so a plain file copy can miss
recent writes or catch a half-written page. Restoring goes the same way, into
the live database, after the copy passes an integrity check. A restore first
takes a "pre-restore" backup so it can be undone.
"""
import logging
import os
import shutil
import sqlite3
import tempfile
import time
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass


logger = logging.getLogger("gradepulse.backup")

_SQLITE_HEADER = b"SQLite format 3\x00"
_SIDECARS = ("-wal", "-shm", "-journal")


def is_sqlite(path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(16) == _SQLITE_HEADER
    except OSError:
        return False


def copy_sqlite(src_path: str, dest_path: str) -> None:
    """A consistent copy of a live SQLite database (WAL included)."""
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dest_path)
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()


def sqlite_ok(path: str) -> bool:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    except sqlite3.DatabaseError:
        return False
    finally:
        conn.close()


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
        # A database's -wal/-shm files are folded into its backup copy.
        if filepath.endswith(_SIDECARS):
            return
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
                    logger.warning(f"Periodic backup failed: {e}")
    
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
                if is_sqlite(filepath):
                    copy_sqlite(filepath, str(temp_path))
                else:
                    shutil.copy2(filepath, temp_path)
                temp_path.rename(dest)
                copied_files.append(filename)
            except Exception as e:
                logger.warning(f"Failed to backup {filename}: {e}")
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
                logger.warning(f"Failed to remove old backup {backup.path}: {e}")
    
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
    
    def resolve_backup(self, backup_path: str) -> Optional[Path]:
        """The backup folder for a name or path, only if it is one of ours
        (directly inside backup_dir, with metadata)."""
        candidate = Path(backup_path)
        if not candidate.is_absolute() and len(candidate.parts) == 1:
            candidate = self.backup_dir / candidate
        try:
            resolved = candidate.resolve()
            inside = resolved.parent == self.backup_dir.resolve()
        except OSError:
            return None
        if not inside or not (resolved / "_backup_meta.json").is_file():
            return None
        return resolved

    def restore_backup(self, backup_path: str) -> Optional[Dict]:
        """
        Restore files from a backup.

        Args:
            backup_path: a backup folder name, or its path inside backup_dir

        Returns:
            {"restored": [...], "pre_restore": path} if successful, None otherwise.
            Nothing is changed unless every file in the backup checks out.
        """
        backup_dir = self.resolve_backup(backup_path)
        if backup_dir is None:
            logger.error("Not a backup in %s: %s", self.backup_dir, backup_path)
            return None

        with open(backup_dir / "_backup_meta.json") as f:
            meta = json.load(f)

        by_name = {os.path.basename(p): p for p in self._files_to_backup}
        plan = []  # (source in backup, live path, kind)
        with tempfile.TemporaryDirectory() as work:
            for filename in meta.get("files", []):
                if filename.endswith(_SIDECARS):
                    continue  # older backups: folded in with their database below
                src = backup_dir / filename
                target = by_name.get(filename)
                if not src.exists() or target is None:
                    logger.warning("Skipping %s: missing from the backup or not a registered file", filename)
                    continue
                if is_sqlite(src):
                    # Work on a copy (with any -wal from an older backup) so the
                    # backup itself is never modified, then check it.
                    staged = os.path.join(work, filename)
                    shutil.copy2(src, staged)
                    for suffix in ("-wal",):
                        if (backup_dir / (filename + suffix)).exists():
                            shutil.copy2(backup_dir / (filename + suffix), staged + suffix)
                    if not sqlite_ok(staged):
                        logger.error("Backup database %s fails its integrity check; nothing restored", src)
                        return None
                    plan.append((staged, target, "sqlite"))
                else:
                    if filename.endswith(".json"):
                        try:
                            with open(src) as f:
                                json.load(f)
                        except ValueError:
                            logger.error("Backup file %s is not valid JSON; nothing restored", src)
                            return None
                    # Staged too: the pre-restore backup below may rotate
                    # this backup folder away.
                    staged = os.path.join(work, filename)
                    shutil.copy2(src, staged)
                    plan.append((staged, target, "file"))

            if not plan:
                return None

            pre = self.create_backup("pre-restore")
            restored = []
            for src, target, kind in plan:
                try:
                    if kind == "sqlite":
                        copy_sqlite(src, target)  # through SQLite, into the live database
                    else:
                        temp_path = target + ".restore.tmp"
                        shutil.copy2(src, temp_path)
                        os.replace(temp_path, target)
                    restored.append(os.path.basename(target))
                except Exception as e:
                    logger.error("Could not restore %s: %s", os.path.basename(target), e)
            if not restored:
                return None
            return {"restored": restored, "pre_restore": pre.path if pre else None}

    def get_latest_backup(self) -> Optional[BackupInfo]:
        """Get the most recent backup."""
        backups = self.list_backups()
        if not backups:
            return None
        return max(backups, key=lambda b: b.timestamp)
