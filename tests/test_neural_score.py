import pytest
from linucb_brain import Brain

def test_all_5_dimension_scores_return_values_in_0_10():
    brain = Brain()
    # Add minimal data
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math", "Math", 3, "video")
    brain.add_content("C2", "Science", "Science", 4, "quiz")
    
    # Run some sessions
    brain.update("S1", "C1", 0.5)
    brain.update("S1", "C2", 0.8)
    
    scores = brain.neural_score(verbose=False)
    
    dimensions = [
        'exploration_score', 
        'convergence_score', 
        'context_score', 
        'precision_score', 
        'grade_score'
    ]
    for dim in dimensions:
        assert 0.0 <= scores[dim] <= 10.0
    
    assert 0.0 <= scores['neural_score'] <= 10.0

def test_final_neural_score_is_weighted_correctly():
    # Final Neural Score:
    # exploration*0.20, convergence*0.25, context*0.20, precision*0.25, grade*0.10
    brain = Brain()
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math", "Math", 3, "video")
    brain.update("S1", "C1", 0.5)
    
    scores = brain.neural_score(verbose=False)

    manual_weighted = (
        scores['exploration_score'] * 0.15 +
        scores['convergence_score'] * 0.20 +
        scores['context_score']     * 0.15 +
        scores['precision_score']   * 0.20 +
        scores['grade_score']       * 0.10 +
        scores['purity_score']      * 0.10 +
        scores['balance_score']     * 0.10
    )

    assert pytest.approx(scores['neural_score']) == manual_weighted

def test_report_renders_without_errors():
    from linucb_brain.diagnostics.report import render_neural_report
    
    dummy_scores = {
        'exploration_score': 8.0,
        'convergence_score': 7.5,
        'context_score': 9.0,
        'precision_score': 6.5,
        'grade_score': 8.5,
        'neural_score': 7.9
    }
    
    report = render_neural_report(dummy_scores)
    assert "LINUCB BRAIN — NEURAL SCORE" in report
    assert "★  NEURAL SCORE :  7.9 / 10.0   ★" in report
    assert "Status: GOOD" in report

def test_balance_score_is_computed_not_placeholder():
    # Diverse rewards spread across the range -> high balance (entropy).
    brain = Brain()
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math", "Math", 3, "video")
    for i in range(20):
        reward = -0.9 + i * 0.2  # spans the full [-1, 1] regime
        brain.update("S1", "C1", reward)
    balance = brain.neural_score(verbose=False)['balance_score']
    assert 0.0 <= balance <= 10.0
    assert balance > 2.0

def test_balance_score_low_when_single_mode_dominates():
    # All-but-one identical rewards -> near-zero entropy -> low balance.
    brain = Brain()
    brain.add_student("S1", "Alice")
    brain.add_content("C1", "Math", "Math", 3, "video")
    for _ in range(20):
        brain.update("S1", "C1", 0.9)
    balance = brain.neural_score(verbose=False)['balance_score']
    assert 0.0 <= balance <= 10.0
    assert balance < 2.0
