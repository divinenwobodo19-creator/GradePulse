import pytest
import os
import numpy as np
from linucb_brain import Brain, Student, Content

def test_add_student_and_add_content():
    brain = Brain()
    student = brain.add_student("S1", "Alice")
    assert student.student_id == "S1"
    assert student.name == "Alice"
    assert len(brain.students) == 1
    
    content = brain.add_content("C1", "Math Video", "Math", 3, "video")
    assert content.content_id == "C1"
    assert content.title == "Math Video"
    assert len(brain.contents) == 1

def test_recommend_returns_valid_content():
    brain = Brain()
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math Video", "Math", 3, "video")
    brain.add_content("C2", "History Reading", "History", 2, "reading")
    
    # Recommend from all
    rec = brain.recommend("S1")
    assert isinstance(rec, Content)
    assert rec.content_id in ["C1", "C2"]
    
    # Recommend from topic
    rec_math = brain.recommend("S1", topic="Math")
    assert rec_math.content_id == "C1"

def test_update_increments_session_count():
    brain = Brain()
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math Video", "Math", 3, "video")
    
    initial_sessions = len(brain.sessions)
    initial_student_sessions = brain.students["S1"].session_count
    
    # Standard flow: recommend then update
    brain.recommend("S1")
    brain.update("S1", "C1", 0.8)
    
    assert len(brain.sessions) == initial_sessions + 1
    assert brain.students["S1"].session_count == initial_student_sessions + 1
    assert brain.contents["C1"].times_recommended == 1

def test_save_and_load_preserves_state(tmp_path):
    brain = Brain()
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math Video", "Math", 3, "video")
    brain.update("S1", "C1", 0.9)
    
    save_path = tmp_path / "test_brain.json"
    brain.save(save_path)
    
    loaded_brain = Brain.load(save_path)
    
    assert loaded_brain.alpha == brain.alpha
    assert len(loaded_brain.students) == 1
    assert len(loaded_brain.contents) == 1
    assert len(loaded_brain.sessions) == 1
    assert loaded_brain.students["S1"].name == "Alice"
    assert loaded_brain.contents["C1"].title == "Math Video"
    assert np.allclose(loaded_brain.model.arms["C1"]['A'], brain.model.arms["C1"]['A'])

def test_save_is_atomic_and_leaves_no_tmp(tmp_path):
    brain = Brain()
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math", "Math", 3, "video")
    brain.update("S1", "C1", 0.9)

    path = tmp_path / "state.json"
    brain.save(str(path))

    tmp_leftovers = [p.name for p in tmp_path.iterdir() if ".tmp" in p.name]
    assert tmp_leftovers == []
    loaded = Brain.load(str(path))
    assert loaded.students["S1"].name == "Alice"
    assert loaded.contents["C1"].avg_reward is not None

def test_save_retains_bak_and_load_falls_back(tmp_path):
    brain = Brain()
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math", "Math", 3, "video")
    brain.update("S1", "C1", 0.9)

    path = tmp_path / "state.json"
    brain.save(str(path))
    brain.update("S1", "C1", 0.2)   # second save -> first good state is kept as .bak
    brain.save(str(path))

    assert (tmp_path / "state.json.bak").exists()

    path.write_text("{ this is not valid json, so the main file is corrupt ")
    loaded = Brain.load(str(path))
    assert "S1" in loaded.students
    assert "C1" in loaded.contents

def test_load_raises_when_no_bak_and_main_corrupt(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("not json at all")
    with pytest.raises(ValueError):
        Brain.load(str(path))
