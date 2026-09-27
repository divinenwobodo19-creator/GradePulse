"""
File-based synchronization for multi-worker brain state access.

This module provides file locking and periodic sync to allow multiple
uvicorn workers to safely share the same brain state without silent divergence.
"""
import os
import time
import threading
import fcntl
import json
from typing import Optional, Callable
from datetime import datetime


class FileLock:
    """
    File-based lock using fcntl for safe concurrent access.
    
    This ensures only one worker can write to the brain state file at a time,
    preventing corruption from concurrent writes.

    Design notes:
    - `flock()` fences across processes (and across distinct FileLock instances
      in the same process, because each open() creates a separate open-file
      description).
    - A per-instance `threading.Lock` serializes concurrent holders of the SAME
      FileLock instance inside a single process. Without it, two threads that
      share one instance can clobber each other's `_lock_fd` and close a lock
      file descriptor out from under the thread that actually holds the lock
      (observed as `OSError: [Errno 9] Bad file descriptor` under concurrent
      bulk-update load, which then lets writers race unsynchronized).
    - Lock *attempts* keep their file descriptor in a local variable so a
      failed acquire can never release/close a descriptor owned by the holder.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.lock_path = f"{filepath}.lock"
        self._lock_fd: Optional[int] = None
        self._thread_lock = threading.Lock()
    
    def acquire(self, timeout: float = 30.0) -> bool:
        """
        Acquire the file lock.
        
        Args:
            timeout: Maximum seconds to wait for the lock.
            
        Returns:
            True if lock acquired, False if timeout.
        """
        # Serialize same-instance holders in this process. This lock is held
        # until release() so a single instance can never have two active fds.
        if not self._thread_lock.acquire(timeout=timeout):
            return False
        start_time = time.time()
        attempt_fd: Optional[int] = None
        while True:
            try:
                attempt_fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR)
                fcntl.flock(attempt_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Write PID for debugging (truncate stale content first)
                os.ftruncate(attempt_fd, 0)
                os.write(attempt_fd, str(os.getpid()).encode())
                self._lock_fd = attempt_fd
                return True
            except (IOError, OSError):
                # Never touch self._lock_fd from the failure path — it may
                # belong to an in-progress holder of this instance.
                if attempt_fd is not None:
                    try:
                        os.close(attempt_fd)
                    except OSError:
                        pass
                    attempt_fd = None
                if time.time() - start_time >= timeout:
                    self._thread_lock.release()
                    return False
                time.sleep(0.005)
    
    def release(self):
        """Release the file lock."""
        fd, self._lock_fd = self._lock_fd, None
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except (IOError, OSError):
                pass
            try:
                os.close(fd)
            except OSError:
                pass
        # Release the in-process serialization lock (release-without-acquire is
        # a no-op rather than an error).
        try:
            self._thread_lock.release()
        except RuntimeError:
            pass
    
    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(
                f"Could not acquire file lock within timeout: {self.lock_path}"
            )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


class BrainSynchronizer:
    """
    Manages safe multi-worker brain state synchronization.
    
    Features:
    - File locking for safe concurrent writes
    - Periodic auto-save to keep workers synchronized
    - Per-worker brain loading (not forked copies)
    """
    
    def __init__(
        self,
        brain_state_path: str,
        config_path: str,
        auto_save_interval: float = 30.0,
        on_save: Optional[Callable] = None,
    ):
        """
        Initialize the synchronizer.
        
        Args:
            brain_state_path: Path to brain_state.json
            config_path: Path to class_config.json
            auto_save_interval: Seconds between auto-saves (0 to disable)
            on_save: Optional callback after successful save
        """
        self.brain_state_path = brain_state_path
        self.config_path = config_path
        self.auto_save_interval = auto_save_interval
        self.on_save = on_save
        
        self._brain_lock = FileLock(brain_state_path)
        self._config_lock = FileLock(config_path)
        self._auto_save_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._brain = None
        self._worker_pid = os.getpid()
    
    def load_brain(self, load_fn: Callable) -> Optional[object]:
        """
        Load brain state from disk with file locking.
        
        This ensures each worker loads a fresh copy from disk,
        not a forked copy from the parent process.
        
        Args:
            load_fn: Function to call to load the brain (e.g., Brain.load)
            
        Returns:
            Loaded brain instance or None if no state file exists
        """
        if not os.path.exists(self.brain_state_path):
            return None
        
        with self._brain_lock:
            try:
                brain = load_fn(self.brain_state_path)
                self._brain = brain
                return brain
            except Exception as e:
                print(f"Warning: Could not load brain state: {e}")
                return None
    
    def save_brain(self, save_fn: Callable) -> bool:
        """
        Save brain state to disk with file locking.
        
        Args:
            save_fn: Function to call to save the brain (e.g., brain.save)
            
        Returns:
            True if save succeeded, False otherwise
        """
        if self._brain is None:
            return False
        
        with self._brain_lock:
            try:
                save_fn(self.brain_state_path)
                return True
            except Exception as e:
                print(f"Warning: Could not save brain state: {e}")
                return False
    
    def start_auto_save(self, save_fn: Callable):
        """
        Start periodic auto-save thread.
        
        This keeps all workers synchronized by periodically saving state to disk.
        
        Args:
            save_fn: Function to call to save the brain
        """
        if self.auto_save_interval <= 0:
            return
        
        self._stop_event.clear()
        
        def _auto_save_loop():
            while not self._stop_event.is_set():
                self._stop_event.wait(self.auto_save_interval)
                if not self._stop_event.is_set() and self._brain is not None:
                    if self.save_brain(save_fn):
                        if self.on_save:
                            self.on_save()
        
        self._auto_save_thread = threading.Thread(
            target=_auto_save_loop,
            daemon=True,
            name=f"brain-autosave-{self._worker_pid}"
        )
        self._auto_save_thread.start()
    
    def stop_auto_save(self):
        """Stop the auto-save thread."""
        self._stop_event.set()
        if self._auto_save_thread:
            self._auto_save_thread.join(timeout=5.0)
            self._auto_save_thread = None
    
    def set_brain(self, brain):
        """Set the brain instance for this worker."""
        self._brain = brain
    
    def get_brain(self):
        """Get the brain instance for this worker."""
        return self._brain
    
    def force_reload(self, load_fn: Callable) -> Optional[object]:
        """
        Force reload brain state from disk (for recovery scenarios).
        
        Args:
            load_fn: Function to call to load the brain
            
        Returns:
            Reloaded brain instance or None
        """
        brain = self.load_brain(load_fn)
        if brain is not None:
            self._brain = brain
        return brain
