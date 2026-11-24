"""
Term report cards: turn a term's weekly tests and exam into the card a
Nigerian secondary school prints at the end of term.

For each student and subject:

- CA (continuous assessment) = the mean of the weekly tests taken inside the
  term, scaled to the school's CA weight (40 by default).
- Exam = the exam score scaled to the rest (60 by default).
- Total = CA + Exam, out of 100, graded on the school's scale (WAEC A1-F9 by
  default).

A subject appears on a card when the student has a weekly test or an exam in
it this term. A total is only worked out when every part the school weighs is
there; otherwise the subject is listed under `missing` so the teacher can see
what is left to enter, rather than the card quietly counting a gap as zero.

Positions use competition ranking (1, 2, 2, 4) and can be switched off.
"""
from typing import Dict, Iterable, List, Optional, Tuple

DEFAULT_CA_WEIGHT = 40

# WAEC grades with their usual remarks; `min` is the lowest total for the grade.
DEFAULT_GRADE_SCALE = [
    {"grade": "A1", "min": 75, "remark": "Excellent"},
    {"grade": "B2", "min": 70, "remark": "Very good"},
    {"grade": "B3", "min": 65, "remark": "Good"},
    {"grade": "C4", "min": 60, "remark": "Credit"},
    {"grade": "C5", "min": 55, "remark": "Credit"},
    {"grade": "C6", "min": 50, "remark": "Credit"},
    {"grade": "D7", "min": 45, "remark": "Pass"},
    {"grade": "E8", "min": 40, "remark": "Pass"},
    {"grade": "F9", "min": 0, "remark": "Fail"},
]

TEXT_MAX = 300      # address, comments
REMARK_MAX = 120    # one subject remark


def settings_with_defaults(saved: dict) -> dict:
    """A school's report-card settings with any missing value filled in."""
    return {
        "ca_weight": saved.get("ca_weight", DEFAULT_CA_WEIGHT),
        "grade_scale": saved.get("grade_scale") or [dict(g) for g in DEFAULT_GRADE_SCALE],
        "show_positions": saved.get("show_positions", True),
        "address": saved.get("address", ""),
        "principal_name": saved.get("principal_name", ""),
    }


def clean_grade_scale(scale: List[dict]) -> List[dict]:
    """Validate a school's grading scale: distinct grades and cut-offs, one of
    them 0 so every total gets a grade. Returned highest first."""
    if not 2 <= len(scale) <= 15:
        raise ValueError("A grading scale needs between 2 and 15 grades")
    cleaned = []
    for band in scale:
        grade = str(band.get("grade", "")).strip()
        remark = str(band.get("remark", "")).strip()
        try:
            minimum = float(band.get("min"))
        except (TypeError, ValueError):
            raise ValueError("Each grade needs a lowest score between 0 and 100")
        if not grade or len(grade) > 4:
            raise ValueError("Each grade needs a short name, such as A1 or B")
        if not 0 <= minimum <= 100:
            raise ValueError("Each grade needs a lowest score between 0 and 100")
        if len(remark) > 30:
            raise ValueError("Keep each grade's remark under 30 characters")
        cleaned.append({"grade": grade, "min": minimum, "remark": remark})
    if len({b["grade"] for b in cleaned}) != len(cleaned):
        raise ValueError("Each grade name must be different")
    if len({b["min"] for b in cleaned}) != len(cleaned):
        raise ValueError("Each grade must start at a different score")
    if min(b["min"] for b in cleaned) != 0:
        raise ValueError("The lowest grade must start at 0, so every total gets a grade")
    return sorted(cleaned, key=lambda b: -b["min"])


def grade_for(total: float, scale: List[dict]) -> Tuple[str, str]:
    for band in sorted(scale, key=lambda b: -b["min"]):
        if total >= band["min"]:
            return band["grade"], band["remark"]
    return scale[-1]["grade"], scale[-1]["remark"]


def rank(values: Dict[int, float]) -> Dict[int, int]:
    """Competition ranking, highest first: 90, 80, 80, 70 -> 1, 2, 2, 4."""
    ordered = sorted(values.values(), reverse=True)
    return {key: ordered.index(value) + 1 for key, value in values.items()}


def _round(x: float) -> float:
    return round(x + 1e-9, 1)


def build_cards(
    students: List[dict],
    subjects: List[str],
    weekly: Iterable[dict],
    exams: Iterable[dict],
    remarks: Iterable[dict],
    comments: Iterable[dict],
    settings: dict,
) -> List[dict]:
    """One card per student.

    students: [{"pk", "student_id", "name"}], in the order to print.
    subjects: the school's subject list (the order subjects appear on a card).
    weekly / exams: rows with student_pk, subject and a 0-1 score.
    remarks: rows with student_pk, subject, remark. comments: one row per
    student_pk with days_present and the two comments.
    """
    ca_weight = settings["ca_weight"]
    exam_weight = 100 - ca_weight
    scale = settings["grade_scale"]
    show_positions = settings["show_positions"]

    tests: Dict[Tuple[int, str], List[float]] = {}
    for row in weekly:
        tests.setdefault((row["student_pk"], row["subject"]), []).append(row["score"])
    exam = {(r["student_pk"], r["subject"]): r["score"] for r in exams}
    remark = {(r["student_pk"], r["subject"]): r["remark"] for r in remarks}
    comment = {r["student_pk"]: r for r in comments}

    # Subjects on the cards: the school's list first, then any other subject
    # that has marks this term (e.g. one since removed from the list).
    order = list(subjects)
    for _, subject in list(tests) + list(exam):
        if subject not in order:
            order.append(subject)

    cards = []
    totals: Dict[str, Dict[int, float]] = {s: {} for s in order}
    for student in students:
        pk = student["pk"]
        rows, missing = [], []
        for subject in order:
            key = (pk, subject)
            if key not in tests and key not in exam:
                continue
            ca = _round(sum(tests[key]) / len(tests[key]) * ca_weight) if key in tests else None
            ex = _round(exam[key] * exam_weight) if key in exam else None
            complete = (ca is not None or ca_weight == 0) and (ex is not None or exam_weight == 0)
            total = _round((ca or 0) + (ex or 0)) if complete else None
            grade, grade_remark = grade_for(total, scale) if total is not None else ("", "")
            if total is not None:
                totals[subject][pk] = total
            else:
                missing.append(subject)
            rows.append({
                "subject": subject, "tests": len(tests.get(key, [])), "ca": ca, "exam": ex, "total": total,
                "grade": grade, "grade_remark": grade_remark, "teacher_remark": remark.get(key, ""),
                "position": None, "class_average": None, "highest": None, "lowest": None,
            })
        c = comment.get(pk, {})
        cards.append({
            "student_id": student["student_id"], "name": student["name"], "pk": pk,
            "subjects": rows, "missing": missing,
            "total": None, "average": None, "position": None,
            "days_present": c.get("days_present"),
            "form_teacher_comment": c.get("form_teacher_comment", ""),
            "principal_comment": c.get("principal_comment", ""),
        })

    # Class figures per subject, from the totals that are complete.
    stats = {}
    for subject, by_pk in totals.items():
        if by_pk:
            values = list(by_pk.values())
            stats[subject] = {"class_average": _round(sum(values) / len(values)),
                              "highest": max(values), "lowest": min(values),
                              "positions": rank(by_pk)}

    averages: Dict[int, float] = {}
    for card in cards:
        complete_totals = []
        for row in card["subjects"]:
            figure = stats.get(row["subject"])
            if figure:
                row.update(class_average=figure["class_average"], highest=figure["highest"], lowest=figure["lowest"])
                if show_positions and row["total"] is not None:
                    row["position"] = figure["positions"][card["pk"]]
            if row["total"] is not None:
                complete_totals.append(row["total"])
        if complete_totals:
            card["total"] = _round(sum(complete_totals))
            card["average"] = _round(sum(complete_totals) / len(complete_totals))
            # Overall positions only compare students whose cards are complete;
            # ranking a part-filled card would flatter or punish it.
            if not card["missing"]:
                averages[card["pk"]] = card["average"]
    if show_positions:
        positions = rank(averages)
        for card in cards:
            card["position"] = positions.get(card["pk"])
    for card in cards:
        del card["pk"]
    return cards
