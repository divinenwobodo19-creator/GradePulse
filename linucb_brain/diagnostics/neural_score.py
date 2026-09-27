import numpy as np
import random
import itertools
from math import log
from typing import Dict, List, Optional
from ..models.student import Student
from ..models.content import Content
from ..models.session import Session

def run_neural_diagnostics(
    students: Dict[str, Student], 
    contents: Dict[str, Content], 
    sessions: List[Session],
    brain_instance
) -> Dict[str, float]:
    """
    Run full Neural Score diagnostics for the brain.
    
    Args:
        students (Dict[str, Student]): Dictionary of students.
        contents (Dict[str, Content]): Dictionary of content items.
        sessions (List[Session]): List of all recorded sessions.
        brain_instance: The Brain object to call methods from.
        
    Returns:
        Dict[str, float]: Calculated scores for each dimension.
    """
    scores = {}
    
    # 1. EXPLORATION EFFICIENCY (exploration_score)
    # entropy = -sum(p * log(p)) for p = recommendations per arm / total
    # MEASURE DIVERSITY OF RECOMMENDATIONS MADE DURING DIAGNOSTICS
    diag_recs = {}
    student_ids = list(students.keys())
    content_ids = list(contents.keys())
    
    # Sample 100 students and get their top recommendation
    for _ in range(min(100, len(students))):
        sid = random.choice(student_ids)
        rec = brain_instance.recommend(sid, top_n=1)
        diag_recs[rec.content_id] = diag_recs.get(rec.content_id, 0) + 1
        
    total_diag = sum(diag_recs.values())
    if total_diag > 0:
        p_recs = [count / total_diag for count in diag_recs.values()]
        entropy = -sum(p * log(p) for p in p_recs)
        # Max entropy for 100 samples is log(min(100, len(contents)))
        max_ent = log(min(100, len(contents))) if len(contents) > 1 else 1.0
        exploration_score = (entropy / max_ent) * 10.0
    else:
        exploration_score = 0.0
    scores['exploration_score'] = min(exploration_score, 10.0)

    # 2. REWARD CONVERGENCE (convergence_score)
    if len(sessions) < 100: # Need more sessions for a stable convergence score
        convergence_score = 5.0
    else:
        # Divide into 5 chunks and check if avg reward is trending up
        chunk_size = len(sessions) // 5
        chunk_avgs = []
        for i in range(5):
            chunk = sessions[i*chunk_size : (i+1)*chunk_size]
            chunk_avgs.append(np.mean([s.reward for s in chunk if s.reward is not None]))
        
        # Calculate slope of chunk_avgs
        if len(chunk_avgs) >= 2:
            x = np.arange(len(chunk_avgs))
            slope, _ = np.polyfit(x, chunk_avgs, 1)
            # Normalize slope: 0.05 improvement per chunk is EXCELLENT (slope=0.05 -> score 10)
            convergence_score = (slope + 0.01) * 100.0 + 5.0
        else:
            convergence_score = 5.0
    scores['convergence_score'] = min(max(convergence_score, 0.0), 10.0)

    # 3. CONTEXT SENSITIVITY (context_score)
    if len(students) < 2:
        context_score = 5.0
    else:
        student_ids = list(students.keys())
        student_pairs = list(itertools.combinations(student_ids, 2))

        orig_alpha = brain_instance.alpha
        brain_instance.alpha = 0.05

        pair_scores = []
        for id_a, id_b in student_pairs:
            same_topic = 1.0 if students[id_a].current_topic == students[id_b].current_topic else 0.0

            rec_a = brain_instance.recommend(id_a, top_n=1)
            rec_b = brain_instance.recommend(id_b, top_n=1)
            same_rec_topic = 1.0 if rec_a.topic == rec_b.topic else 0.0

            pair_scores.append(1.0 - abs(same_rec_topic - same_topic))

        brain_instance.alpha = orig_alpha
        context_score = np.mean(pair_scores) * 10.0 if pair_scores else 0.0
    scores['context_score'] = min(max(context_score, 0.0), 10.0)

    # 4. RECOMMENDATION PRECISION (precision_score)
    if not sessions:
        precision_score = 5.0
    else:
        global_mean_reward = np.mean([s.reward for s in sessions if s.reward is not None])
        above_mean_count = sum(1 for s in sessions if s.reward is not None and s.reward > global_mean_reward)
        precision = above_mean_count / len(sessions)
        precision_score = precision * 10.0
    scores['precision_score'] = min(precision_score, 10.0)

    # 5. GRADE PREDICTION ACCURACY (grade_score)
    accuracy_samples = []
    for student_id, student in students.items():
        for subject, grades in student.grade_history.items():
            if len(grades) >= 3:
                # predicted = predict_grade(student_id, subject)
                predicted = brain_instance.predict_grade(student_id, subject)
                actual = grades[-1]
                error = abs(predicted - actual)
                accuracy_samples.append(1 - error)
                
    if not accuracy_samples:
        grade_score = 5.0
    else:
        grade_score = np.mean(accuracy_samples) * 10.0
    scores['grade_score'] = min(max(grade_score, 0.0), 10.0)

    # 6. CLUSTER PURITY (New for COBART)
    if hasattr(brain_instance, 'clustering') and brain_instance.clustering.initialized:
        stats = brain_instance.clustering.get_cluster_stats()
        # Measure how balanced the clusters are (Entropy of student distribution)
        counts = list(stats.values())
        total = sum(counts)
        p = [c / total for c in counts]
        entropy = -sum(pk * log(pk) for pk in p)
        max_entropy = log(brain_instance.clustering.n_clusters)
        purity_score = (entropy / max_entropy) * 10.0 if max_entropy > 0 else 5.0
    else:
        purity_score = 5.0
    scores['purity_score'] = min(max(purity_score, 0.0), 10.0)

    # 7. OBJECTIVE BALANCE (real, not a placeholder)
    # A system where one objective dominates tends to collapse reward feedback
    # toward a single mode. We measure the entropy of the reward distribution
    # (5 bins over the [-1, 1] signal range): high entropy = balanced signals,
    # low entropy = one mode is dominating (2026-09-27).
    rewards = np.array([s.reward for s in sessions if s.reward is not None], dtype=float)
    if len(rewards) >= 5:
        bins = np.histogram(rewards, bins=5, range=(-1.0, 1.0))[0].astype(float)
        bins = bins[bins > 0]
        probs = bins / bins.sum()
        entropy = -sum(p * log(p) for p in probs)
        max_entropy = log(5)
        balance_score = (entropy / max_entropy) * 10.0 if max_entropy > 0 else 5.0
    else:
        balance_score = 5.0
    scores['balance_score'] = min(max(balance_score, 0.0), 10.0)

    # Final Neural Score (Weighted with new dimensions)
    final_score = (
        scores['exploration_score'] * 0.15 +
        scores['convergence_score'] * 0.20 +
        scores['context_score']     * 0.15 +
        scores['precision_score']   * 0.20 +
        scores['grade_score']       * 0.10 +
        scores['purity_score']      * 0.10 +
        scores['balance_score']     * 0.10
    )
    scores['neural_score'] = final_score
    
    return scores
