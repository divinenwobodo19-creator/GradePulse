"""
Tiering of students by average score in a subject.

Thresholds follow the Nigerian WAEC grading scale (0–1):
  - remediation (Needs Extra Help):  average < 0.4   (F9 — Fail)
  - on_track (At Expected Level):    0.4 <= average < 0.75  (E8 to B2)
  - ahead (Ahead of Class):          average >= 0.75 (A1 — Excellent)
"""
from typing import Dict, List

TIER_LABELS = {1: "remediation", 2: "on_track", 3: "ahead"}
TIER_DIFFICULTY = {1: 1, 2: 3, 3: 5}
TIER_NOTES = {
    1: "Scored below 40% (F9). Needs extra practice — give foundational materials.",
    2: "Scored 40–74% (E8 to B2). On track — continue with standard curriculum.",
    3: "Scored 75% or above (A1). Ahead of class — give advanced materials.",
}


def tier_for(score: float) -> int:
    if score < 0.4:
        return 1
    if score < 0.75:
        return 2
    return 3


def build_triage_report(subject: str, results: List[Dict]) -> Dict:
    """
    Build the triage payload from students who have been assessed in `subject`.

    Each result needs: student_id, name, predicted (0–1), attempts. Students
    with no score in the subject must not be passed in — a report must not
    imply a grade for a subject the student never took.
    """
    tiers = {1: [], 2: [], 3: []}
    for r in results:
        tiers[tier_for(r["predicted"])].append({
            "student_id": r["student_id"],
            "name": r["name"],
            "predicted_score": round(r["predicted"], 2),
            "attempts": r["attempts"],
        })

    return {
        "subject": subject,
        "total_students": len(results),
        "tiers": {
            TIER_LABELS[k]: {
                "students": v,
                "count": len(v),
                "recommended_difficulty": TIER_DIFFICULTY[k],
                "note": TIER_NOTES[k],
            }
            for k, v in tiers.items()
        },
        "scope": "assessed_only",
    }
