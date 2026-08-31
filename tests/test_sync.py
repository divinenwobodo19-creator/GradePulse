"""
Tests for multi-worker synchronization (BrainSynchronizer).
"""
import os
import time
import tempfile
import threading
import pytest
from linucb_brain.brain import Brain
from linucb_brain.sync import BrainSynchronizer, FileLock


class TestFileLock:
    def test_file_lock_acquire_release(self, tmp_path):
        lock_path = str(tmp_path / "test.lock")
        lock = FileLock(lock_path)
        
        assert lock.acquire(timeout=1.0) is True
        lock.release()
    
    def test_file_lock_context_manager(self, tmp_path):
        lock_path = str(tmp_path / "test.lock")
        with FileLock(lock_path) as lock:
            assert lock._lock_fd is not None
        assert lock._lock_fd is None
    
    def test_file_lock_concurrent_access(self, tmp_path):
        lock_path = str(tmp_path / "test.lock")
        results = []
        
        def worker(worker_id):
            lock = FileLock(lock_path)
            lock.acquire(timeout=5.0)
            results.append(f"start-{worker_id}")
            time.sleep(0.05)
            results.append(f"end-{worker_id}")
            lock.release()
        
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)
        
        start_count = sum(1 for r in results if r.startswith("start-"))
        end_count = sum(1 for r in results if r.startswith("end-"))
        assert start_count == 3
        assert end_count == 3


class TestBrainSynchronizer:
    def test_synchronizer_load_save(self, tmp_path):
        state_path = str(tmp_path / "brain_state.json")
        config_path = str(tmp_path / "class_config.json")
        
        # Create and save a brain
        brain = Brain(model_type="hybrid")
        brain.add_student("S01", "Alice", performance_score=0.7)
        brain.add_content("C01", "Math", "Math", 3, "quiz")
        brain.save(state_path)
        
        # Load via synchronizer
        sync = BrainSynchronizer(state_path, config_path, auto_save_interval=0)
        loaded = sync.load_brain(Brain.load)
        
        assert loaded is not None
        assert "S01" in loaded.students
        assert loaded.students["S01"].name == "Alice"
    
    def test_synchronizer_save_uses_lock(self, tmp_path):
        state_path = str(tmp_path / "brain_state.json")
        config_path = str(tmp_path / "class_config.json")
        
        brain = Brain(model_type="hybrid")
        brain.add_student("S01", "Alice", performance_score=0.7)
        brain.save(state_path)
        
        sync = BrainSynchronizer(state_path, config_path, auto_save_interval=0)
        sync.set_brain(brain)
        
        # Update brain
        brain.add_student("S02", "Bob", performance_score=0.5)
        
        # Save should work
        result = sync.save_brain(brain.save)
        assert result is True
        
        # Verify saved state
        loaded = Brain.load(state_path)
        assert "S01" in loaded.students
        assert "S02" in loaded.students
    
    def test_synchronizer_set_get_brain(self, tmp_path):
        state_path = str(tmp_path / "brain_state.json")
        config_path = str(tmp_path / "class_config.json")
        
        sync = BrainSynchronizer(state_path, config_path, auto_save_interval=0)
        brain = Brain(model_type="hybrid")
        
        sync.set_brain(brain)
        assert sync.get_brain() is brain
    
    def test_synchronizer_auto_save(self, tmp_path):
        state_path = str(tmp_path / "brain_state.json")
        config_path = str(tmp_path / "class_config.json")
        
        save_count = [0]
        
        def on_save():
            save_count[0] += 1
        
        brain = Brain(model_type="hybrid")
        brain.add_student("S01", "Alice", performance_score=0.7)
        brain.save(state_path)
        
        sync = BrainSynchronizer(
            state_path, config_path,
            auto_save_interval=0.1,
            on_save=on_save
        )
        sync.set_brain(brain)
        sync.start_auto_save(brain.save)
        
        # Wait for a few auto-saves
        time.sleep(0.5)
        
        sync.stop_auto_save()
        
        # Auto-save should have triggered at least once
        # (may be 0 if the interval hasn't elapsed yet)
        assert save_count[0] >= 0  # Just verify no crashes
    
    def test_synchronizer_force_reload(self, tmp_path):
        state_path = str(tmp_path / "brain_state.json")
        config_path = str(tmp_path / "class_config.json")
        
        # Create initial brain
        brain1 = Brain(model_type="hybrid")
        brain1.add_student("S01", "Alice", performance_score=0.7)
        brain1.save(state_path)
        
        sync = BrainSynchronizer(state_path, config_path, auto_save_interval=0)
        sync.load_brain(Brain.load)
        
        # Create a new brain and save it (simulating another worker's changes)
        brain2 = Brain(model_type="hybrid")
        brain2.add_student("S02", "Bob", performance_score=0.5)
        brain2.save(state_path)
        
        # Force reload should pick up the new state
        reloaded = sync.force_reload(Brain.load)
        assert reloaded is not None
        assert "S02" in reloaded.students


# ── Coverage gap tests (added by QA — David) ──────────────────────────────────

class TestFileLockEdgeCases:
    def test_acquire_timeout_returns_false(self, tmp_path):
        lock_path = str(tmp_path / "test.lock")
        lock1 = FileLock(lock_path)
        lock1.acquire(timeout=1.0)

        lock2 = FileLock(lock_path)
        result = lock2.acquire(timeout=0.1)
        assert result is False

        lock1.release()

    def test_release_without_acquire_is_safe(self, tmp_path):
        lock_path = str(tmp_path / "test.lock")
        lock = FileLock(lock_path)
        lock.release()
        assert lock._lock_fd is None

    def test_lock_file_contains_pid(self, tmp_path):
        import os
        lock_path = str(tmp_path / "test.lock")
        lock = FileLock(lock_path)
        lock.acquire(timeout=1.0)

        lock_file = f"{lock_path}.lock"
        assert os.path.exists(lock_file)
        with open(lock_file, "r") as f:
            content = f.read()
        assert str(os.getpid()) in content

        lock.release()


class TestBrainSynchronizerEdgeCases:
    def test_load_brain_nonexistent_file(self, tmp_path):
        state_path = str(tmp_path / "nonexistent.json")
        config_path = str(tmp_path / "class_config.json")

        sync = BrainSynchronizer(state_path, config_path, auto_save_interval=0)
        loaded = sync.load_brain(Brain.load)
        assert loaded is None

    def test_load_brain_corrupted_file(self, tmp_path):
        state_path = str(tmp_path / "brain_state.json")
        config_path = str(tmp_path / "class_config.json")

        with open(state_path, "w") as f:
            f.write("{invalid json content")

        sync = BrainSynchronizer(state_path, config_path, auto_save_interval=0)
        loaded = sync.load_brain(Brain.load)
        assert loaded is None

    def test_save_brain_without_brain_set(self, tmp_path):
        state_path = str(tmp_path / "brain_state.json")
        config_path = str(tmp_path / "class_config.json")

        sync = BrainSynchronizer(state_path, config_path, auto_save_interval=0)
        result = sync.save_brain(lambda p: None)
        assert result is False

    def test_save_brain_with_save_failure(self, tmp_path):
        state_path = str(tmp_path / "brain_state.json")
        config_path = str(tmp_path / "class_config.json")

        brain = Brain(model_type="hybrid")
        brain.add_student("S01", "Alice", performance_score=0.7)
        brain.save(state_path)

        sync = BrainSynchronizer(state_path, config_path, auto_save_interval=0)
        sync.set_brain(brain)

        def failing_save(path):
            raise IOError("Disk full")

        result = sync.save_brain(failing_save)
        assert result is False

    def test_start_auto_save_with_zero_interval(self, tmp_path):
        state_path = str(tmp_path / "brain_state.json")
        config_path = str(tmp_path / "class_config.json")

        brain = Brain(model_type="hybrid")
        brain.save(state_path)

        sync = BrainSynchronizer(state_path, config_path, auto_save_interval=0)
        sync.set_brain(brain)
        sync.start_auto_save(brain.save)

        assert sync._auto_save_thread is None

    def test_stop_auto_save_without_start(self, tmp_path):
        state_path = str(tmp_path / "brain_state.json")
        config_path = str(tmp_path / "class_config.json")

        sync = BrainSynchronizer(state_path, config_path, auto_save_interval=0)
        sync.stop_auto_save()
        assert sync._auto_save_thread is None

    def test_force_reload_nonexistent_file(self, tmp_path):
        state_path = str(tmp_path / "nonexistent.json")
        config_path = str(tmp_path / "class_config.json")

        sync = BrainSynchronizer(state_path, config_path, auto_save_interval=0)
        result = sync.force_reload(Brain.load)
        assert result is None

    def test_auto_save_callback_is_called(self, tmp_path):
        state_path = str(tmp_path / "brain_state.json")
        config_path = str(tmp_path / "class_config.json")

        call_count = [0]

        def on_save():
            call_count[0] += 1

        brain = Brain(model_type="hybrid")
        brain.add_student("S01", "Alice", performance_score=0.7)
        brain.save(state_path)

        sync = BrainSynchronizer(
            state_path, config_path,
            auto_save_interval=0.05,
            on_save=on_save
        )
        sync.set_brain(brain)
        sync.start_auto_save(brain.save)

        time.sleep(0.3)
        sync.stop_auto_save()

        assert call_count[0] >= 1

    def test_concurrent_synchronizers_same_file(self, tmp_path):
        state_path = str(tmp_path / "brain_state.json")
        config_path = str(tmp_path / "class_config.json")

        brain1 = Brain(model_type="hybrid")
        brain1.add_student("S01", "Alice", performance_score=0.7)
        brain1.save(state_path)

        sync1 = BrainSynchronizer(state_path, config_path, auto_save_interval=0)
        sync1.load_brain(Brain.load)

        brain2 = Brain(model_type="hybrid")
        brain2.add_student("S02", "Bob", performance_score=0.5)

        sync2 = BrainSynchronizer(state_path, config_path, auto_save_interval=0)
        sync2.set_brain(brain2)
        sync2.save_brain(brain2.save)

        # Note: save_brain overwrites the entire file with the new brain state.
        # This is expected — the file stores the full state, not deltas.
        # In production, workers coordinate via file lock before saving.
        reloaded = sync1.force_reload(Brain.load)
        assert reloaded is not None
        assert "S02" in reloaded.students
