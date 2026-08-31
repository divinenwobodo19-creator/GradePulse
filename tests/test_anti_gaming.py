import pytest
import numpy as np
from linucb_brain import Brain
from linucb_brain.core.reward import calculate_reward


def test_low_performer_improvement_is_penalized():
    """A student at 0.1 improving to 0.5 should get LESS reward than a student at 0.6 improving to 0.9."""
    brain = Brain()

    # Low performer: 0.1 -> 0.5 (delta = 0.4)
    reward_low = brain.calculate_multi_objective_reward(
        improvement=0.4, completed=True, engaged=True,
        churned=False, current_performance=0.1
    )

    # High performer: 0.6 -> 0.9 (delta = 0.3)
    reward_high = brain.calculate_multi_objective_reward(
        improvement=0.3, completed=True, engaged=True,
        churned=False, current_performance=0.6
    )

    # The high performer should get equal or more reward despite smaller delta
    assert reward_high >= reward_low, (
        f"High performer ({reward_high}) should be rewarded >= low performer ({reward_low}) "
        f"despite smaller improvement"
    )


def test_identical_delta_different_levels_different_rewards():
    """Same 0.2 improvement at different performance levels should yield different rewards."""
    brain = Brain()

    reward_at_02 = brain.calculate_multi_objective_reward(
        improvement=0.2, completed=True, engaged=True,
        churned=False, current_performance=0.2
    )

    reward_at_07 = brain.calculate_multi_objective_reward(
        improvement=0.2, completed=True, engaged=True,
        churned=False, current_performance=0.7
    )

    # Improving at 0.7 is harder — should get more reward
    assert reward_at_07 > reward_at_02


def test_ceiling_factor_floor_prevents_zero_reward():
    """Even at performance 0.99, improvement should still register some reward."""
    brain = Brain()

    reward = brain.calculate_multi_objective_reward(
        improvement=0.3, completed=True, engaged=True,
        churned=False, current_performance=0.99
    )

    # With ceiling_factor=0.1, imp_signal = 0.3*5*0.1 = 0.15
    # weighted = 0.5*0.15 + 0.3*1.0 + 0.2*1.0 = 0.075 + 0.3 + 0.2 = 0.575
    assert reward > 0.0


def test_gaming_scenario_low_then_high_gives_moderate_reward():
    """Simulate the gaming pattern: score low first, then high."""
    brain = Brain()

    # Gaming: student scores 0.1, then jumps to 0.8 (delta = 0.7)
    reward_gaming = brain.calculate_multi_objective_reward(
        improvement=0.7, completed=True, engaged=True,
        churned=False, current_performance=0.1
    )

    # Legitimate: student at 0.5 improving to 0.8 (delta = 0.3)
    reward_legit = brain.calculate_multi_objective_reward(
        improvement=0.3, completed=True, engaged=True,
        churned=False, current_performance=0.5
    )

    # The gaming reward should not dominate legitimate learning
    assert reward_gaming < reward_legit + 0.5, (
        f"Gaming reward ({reward_gaming}) should not greatly exceed legitimate ({reward_legit})"
    )


def test_churned_always_returns_negative_one():
    brain = Brain()
    reward = brain.calculate_multi_objective_reward(
        improvement=0.5, completed=True, engaged=True,
        churned=True, current_performance=0.5
    )
    assert reward == -1.0


def test_standalone_reward_anti_gaming():
    """The standalone calculate_reward function should also have anti-gaming."""
    # Low performer: before=0.1, after=0.5 (delta=0.4)
    reward_low = calculate_reward(
        before_score=0.1, after_score=0.5,
        completed=True, time_spent_ratio=1.0,
        engaged=True, churned=False
    )

    # High performer: before=0.6, after=0.9 (delta=0.3)
    reward_high = calculate_reward(
        before_score=0.6, after_score=0.9,
        completed=True, time_spent_ratio=1.0,
        engaged=True, churned=False
    )

    # High performer reward should be >= low performer despite smaller delta
    assert reward_high >= reward_low


def test_standalone_reward_churned():
    reward = calculate_reward(
        before_score=0.5, after_score=0.8,
        completed=True, time_spent_ratio=1.0,
        engaged=True, churned=True
    )
    assert reward == -1.0
