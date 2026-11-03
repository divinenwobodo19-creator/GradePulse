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


# ── Weekly triage over dated scores ─────────────────────────────────────────
#
# The school report behind "who needs help this week". A student's standing
# is the average of their last RECENT_TESTS tests in the subject, so one old
# bad test stops counting once newer ones come in, and one bad week does not
# outweigh everything before it. "Last week" is the same figure worked out
# from the tests before this week (the 7 days ending on the report date), so
# the report can say who moved into or out of needs help, and who is falling.
# Because an average is slow to react, a student whose latest test is below
# 40% but who is not (yet) in needs help is listed under "watch".

RECENT_TESTS = 3
WEEK_DAYS = 7
BIG_CHANGE = 0.10  # 10 percentage points between last week and now

WEEKLY_NOTES = {
    1: "Recent average below 40% (F9). Needs extra help now.",
    2: "Recent average 40 to 74% (E8 to B2). On track.",
    3: "Recent average 75% or above (A1). Ahead of class.",
}


def _recent_average(scores: List[float]) -> float:
    recent = scores[-RECENT_TESTS:]
    return min(1.0, max(0.0, sum(recent) / len(recent)))


def _movement(current: float, previous, cur_tier: int, prev_tier) -> str:
    if previous is None:
        return "new"
    if cur_tier == 1 and prev_tier != 1:
        return "moved_into_help"
    if prev_tier == 1 and cur_tier != 1:
        return "left_help"
    change = round(current - previous, 4)  # 0.40 - 0.50 must count as 10 points
    if change <= -BIG_CHANGE:
        return "falling"
    if change >= BIG_CHANGE:
        return "rising"
    return "steady"


def build_weekly_triage(subject: str, students: List[Dict], as_of=None) -> Dict:
    """Weekly triage from dated scores.

    `students`: [{"student_id", "name", "scores": [(date, score), ...]}] with
    scores oldest first (dates are datetime.date). Students with no score in
    the subject up to `as_of` are left out. `as_of` defaults to the date of
    the latest test in the subject, so a school that tests on Friday sees that
    week's picture all weekend.
    """
    from datetime import timedelta

    dated = [s for s in students if s["scores"]]
    if as_of is None and dated:
        as_of = max(d for s in dated for d, _ in s["scores"])
    week_start = as_of - timedelta(days=WEEK_DAYS - 1) if as_of else None

    tiers = {1: [], 2: [], 3: []}
    changes = {"moved_into_help": [], "left_help": [], "falling": [], "rising": [], "watch": []}
    tested_this_week = 0
    for s in students:
        upto = [(d, v) for d, v in s["scores"] if as_of and d <= as_of]
        if not upto:
            continue
        values = [v for _, v in upto]
        before = [v for d, v in upto if d < week_start]
        current = _recent_average(values)
        previous = _recent_average(before) if before else None
        cur_tier = tier_for(current)
        prev_tier = tier_for(previous) if previous is not None else None
        movement = _movement(current, previous, cur_tier, prev_tier)
        this_week = upto[-1][0] >= week_start
        tested_this_week += this_week
        entry = {
            "student_id": s["student_id"],
            "name": s["name"],
            "predicted_score": round(current, 2),  # kept for older clients
            "current_score": round(current, 2),
            "previous_score": round(previous, 2) if previous is not None else None,
            "change": round(current - previous, 2) if previous is not None else None,
            "previous_tier": TIER_LABELS[prev_tier] if prev_tier else None,
            "movement": movement,
            "tested_this_week": this_week,
            "latest_score": round(upto[-1][1], 2),
            "last_assessed_on": upto[-1][0].isoformat(),
            "attempts": len(values),
        }
        tiers[cur_tier].append(entry)
        brief = {k: entry[k] for k in ("student_id", "name", "current_score", "previous_score", "change", "latest_score")}
        if movement in changes:
            changes[movement].append(brief)
        if cur_tier != 1 and upto[-1][1] < 0.4:
            changes["watch"].append(brief)

    # Most urgent first: the lowest in needs help, the highest in ahead.
    tiers[1].sort(key=lambda e: (e["current_score"], e["name"]))
    tiers[2].sort(key=lambda e: (e["current_score"], e["name"]))
    tiers[3].sort(key=lambda e: (-e["current_score"], e["name"]))
    for key, moved in changes.items():
        if key == "watch":
            moved.sort(key=lambda e: (e["latest_score"], e["name"]))
        else:
            moved.sort(key=lambda e: (e["change"] if e["change"] is not None else 0, e["name"]))

    total = sum(len(v) for v in tiers.values())
    return {
        "subject": subject,
        "as_of": as_of.isoformat() if as_of else None,
        "week_start": week_start.isoformat() if week_start else None,
        "recent_tests": RECENT_TESTS,
        "total_students": total,
        "tested_this_week": tested_this_week,
        "tiers": {
            TIER_LABELS[k]: {
                "students": v,
                "count": len(v),
                "recommended_difficulty": TIER_DIFFICULTY[k],
                "note": WEEKLY_NOTES[k],
            }
            for k, v in tiers.items()
        },
        "changes": changes,
        "scope": "assessed_only",
    }
