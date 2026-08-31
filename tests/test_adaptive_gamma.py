import pytest
import numpy as np
from linucb_brain import Brain


def test_adaptive_gamma_initializes_with_baseline():
    brain = Brain(gamma=0.95)
    assert brain.gamma == 0.95
    assert brain._baseline_gamma == 0.95


def test_adaptive_gamma_reduces_on_variance_spike():
    brain = Brain(gamma=1.0)
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math", "Math", 3, "video")

    # Feed 20 low-variance rewards to fill window
    for _ in range(25):
        brain.update("S1", "C1", 0.5 + np.random.normal(0, 0.01))

    gamma_before = brain.gamma

    # Now inject high-variance rewards (exam week scenario)
    for i in range(25):
        reward = 0.1 if i % 2 == 0 else 0.9
        brain.update("S1", "C1", reward)

    assert brain.gamma < gamma_before, "Gamma should decrease after variance spike"


def test_adaptive_gamma_restores_when_variance_normalizes():
    brain = Brain(gamma=1.0)
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math", "Math", 3, "video")

    # Spike variance to push gamma down
    for i in range(50):
        reward = 0.1 if i % 2 == 0 else 0.9
        brain.update("S1", "C1", reward)

    gamma_after_spike = brain.gamma

    # Feed stable rewards — gamma should creep back up
    for _ in range(200):
        brain.update("S1", "C1", 0.6 + np.random.normal(0, 0.01))

    assert brain.gamma >= gamma_after_spike, "Gamma should restore toward baseline"


def test_adaptive_gamma_never_goes_below_floor():
    brain = Brain(gamma=1.0)
    brain._gamma_floor = 0.9
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math", "Math", 3, "video")

    # Sustained extreme variance
    for i in range(200):
        reward = 0.0 if i % 2 == 0 else 1.0
        brain.update("S1", "C1", reward)

    assert brain.gamma >= 0.9, "Gamma should never go below floor"


def test_adaptive_gamma_appears_in_summary():
    brain = Brain(gamma=0.92)
    summary = brain.summary()
    assert summary['current_gamma'] == 0.92
    assert summary['baseline_gamma'] == 0.92


def test_adaptive_gamma_reflects_in_model():
    brain = Brain(gamma=0.95, model_type="disjoint")
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math", "Math", 3, "video")

    # Push gamma down
    for i in range(50):
        reward = 0.0 if i % 2 == 0 else 1.0
        brain.update("S1", "C1", reward)

    assert brain.model.gamma == brain.gamma, "LinUCB model gamma should track brain gamma"
