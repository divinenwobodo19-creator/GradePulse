import pytest
import numpy as np
from linucb_brain import Brain, Student, Content

def test_hybrid_brain_initialization():
    brain = Brain(model_type="hybrid")
    assert brain.model_type == "hybrid"
    assert hasattr(brain.model, 'A0')
    assert brain.model.k == 8
    assert brain.model.d == 9

def test_hybrid_recommend_and_update():
    brain = Brain(model_type="hybrid", alpha=1.0)
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math Video", "Math", 3, "video")
    brain.add_content("C2", "Math Quiz", "Math", 5, "quiz")
    
    # Recommend
    rec = brain.recommend("S1", topic="Math")
    assert rec.content_id in ["C1", "C2"]
    
    # Update
    brain.update("S1", rec.content_id, 1.0)
    assert len(brain.sessions) == 1
    assert brain.model.arms[rec.content_id]['b'].sum() != 0

def test_hybrid_save_load(tmp_path):
    brain = Brain(model_type="hybrid")
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math Video", "Math", 3, "video")
    brain.update("S1", "C1", 0.9)
    
    save_path = tmp_path / "hybrid_brain.json"
    brain.save(save_path)
    
    loaded = Brain.load(save_path)
    assert loaded.model_type == "hybrid"
    assert np.allclose(loaded.model.A0, brain.model.A0)
    assert len(loaded.model.arms) == 1
    assert "C1" in loaded.model.arms

def test_hybrid_top_n_distinct_and_capped():
    brain = Brain(model_type="hybrid", alpha=1.0)
    brain.add_student("S1", "Alice")
    for i in range(4):
        brain.add_content(f"C{i}", f"Math {i}", "Math", 3, "video")

    picks3 = brain.recommend("S1", top_n=3)
    assert isinstance(picks3, list) and len(picks3) == 3
    assert len({c.content_id for c in picks3}) == 3  # distinct within a call

    picks100 = brain.recommend("S1", top_n=100)
    assert len(picks100) == 4  # capped to the number of available contents
    assert len({c.content_id for c in picks100}) == 4

    one = brain.recommend("S1", top_n=1)
    assert isinstance(one, Content)


def test_hybrid_top_n_respects_recency_penalty():
    # C1 is heavily rewarded, which inflates its recency counter in the engine
    # (how LinUCBHybrid.select() de-prioritises over-used arms). A correct
    # top_n>1 path applies the same penalty as top_n==1, so C1 must not
    # monopolise every pick across repeated calls.
    brain = Brain(model_type="hybrid", alpha=1.0)
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math A", "Math", 3, "video")
    brain.add_content("C2", "Math B", "Math", 3, "video")
    brain.add_content("C3", "Math C", "Math", 3, "video")
    for _ in range(5):
        brain.update("S1", "C1", 1.0)

    picked = set()
    for _ in range(12):
        rec = brain.recommend("S1", top_n=1)
        picked.add(rec.content_id)
        assert rec.content_id in {"C1", "C2", "C3"}
    assert len(picked) >= 2  # penalised C1 is rotated out at least sometimes
