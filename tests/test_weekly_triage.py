"""
Weekly triage: students are tiered on their last few tests in a subject, and
the report says who moved into or out of needs help since last week.
"""
from datetime import date

import pytest

from linucb_brain.core.triage import RECENT_TESTS, build_weekly_triage
from test_score_store import _add, _enter, client, school  # noqa: F401  (fixtures)

D = date.fromisoformat


def _student(sid, *scores):
    return {"student_id": sid, "name": sid.title(), "scores": [(D(d), v) for d, v in scores]}


def _by_id(report):
    return {s["student_id"]: (tier, s) for tier, t in report["tiers"].items() for s in t["students"]}


# ── The logic ────────────────────────────────────────────────────────────────

def test_only_recent_tests_count():
    # Three good tests after a very bad start: the start no longer counts.
    report = build_weekly_triage("MATH", [_student(
        "ada", ("2026-09-01", 0.05), ("2026-09-08", 0.6), ("2026-09-15", 0.7), ("2026-09-22", 0.8))])
    tier, ada = _by_id(report)["ada"]
    assert RECENT_TESTS == 3
    assert (tier, ada["current_score"], ada["attempts"]) == ("on_track", 0.7, 4)


def test_report_date_defaults_to_the_latest_test_and_weeks_count_back_from_it():
    report = build_weekly_triage("MATH", [
        _student("ada", ("2026-10-02", 0.5)), _student("bola", ("2026-10-09", 0.5))])
    assert (report["as_of"], report["week_start"]) == ("2026-10-09", "2026-10-03")
    ids = _by_id(report)
    assert ids["bola"][1]["tested_this_week"] is True
    assert ids["ada"][1]["tested_this_week"] is False
    assert report["tested_this_week"] == 1


def test_movement_since_last_week():
    week1, week2 = "2026-10-02", "2026-10-09"
    report = build_weekly_triage("MATH", [
        _student("slipped", (week1, 0.55), (week2, 0.15)),   # 0.55 -> 0.35: into needs help
        _student("recovered", (week1, 0.30), (week2, 0.70)),  # 0.30 -> 0.50: out of needs help
        _student("falling", (week1, 0.90), (week2, 0.60)),    # 0.90 -> 0.75: still ahead, down 15
        _student("rising", (week1, 0.45), (week2, 0.75)),     # 0.45 -> 0.60: up 15
        _student("steady", (week1, 0.60), (week2, 0.62)),
        _student("new", (week2, 0.20)),
    ])
    ids = _by_id(report)
    assert {sid: s["movement"] for sid, (_, s) in ids.items()} == {
        "slipped": "moved_into_help", "recovered": "left_help", "falling": "falling",
        "rising": "rising", "steady": "steady", "new": "new"}
    assert ids["slipped"][0] == "remediation" and ids["slipped"][1]["previous_tier"] == "on_track"
    assert ids["new"][1]["previous_score"] is None and ids["new"][1]["change"] is None
    assert ids["falling"][1]["change"] == -0.15
    assert [s["student_id"] for s in report["changes"]["moved_into_help"]] == ["slipped"]
    assert [s["student_id"] for s in report["changes"]["left_help"]] == ["recovered"]
    assert [s["student_id"] for s in report["changes"]["falling"]] == ["falling"]
    assert [s["student_id"] for s in report["changes"]["rising"]] == ["rising"]


def test_a_low_latest_test_is_watched_before_the_average_catches_up():
    report = build_weekly_triage("MATH", [_student(
        "chiamaka", ("2026-10-16", 0.55), ("2026-10-23", 0.45), ("2026-10-30", 0.20))])
    tier, c = _by_id(report)["chiamaka"]
    assert (tier, c["current_score"], c["latest_score"]) == ("on_track", 0.4, 0.2)
    assert c["movement"] == "falling"  # 0.50 -> 0.40 is exactly 10 points
    assert [s["student_id"] for s in report["changes"]["watch"]] == ["chiamaka"]


def test_needs_help_students_are_not_also_watched():
    report = build_weekly_triage("MATH", [_student("ada", ("2026-10-30", 0.1))])
    assert report["changes"]["watch"] == []


def test_as_of_ignores_later_tests():
    report = build_weekly_triage("MATH", [_student("ada", ("2026-10-02", 0.2), ("2026-10-09", 0.9))],
                                 as_of=D("2026-10-05"))
    tier, ada = _by_id(report)["ada"]
    assert (tier, ada["current_score"], ada["attempts"]) == ("remediation", 0.2, 1)


def test_needs_help_lists_the_lowest_first():
    report = build_weekly_triage("MATH", [
        _student("b", ("2026-10-09", 0.30)), _student("a", ("2026-10-09", 0.10)), _student("c", ("2026-10-09", 0.35))])
    assert [s["student_id"] for s in report["tiers"]["remediation"]["students"]] == ["a", "b", "c"]


def test_no_scores_gives_an_empty_report():
    report = build_weekly_triage("MATH", [_student("ada")])
    assert report["total_students"] == 0 and report["as_of"] is None
    assert all(t["count"] == 0 for t in report["tiers"].values())


# ── Through the API ──────────────────────────────────────────────────────────

def test_api_reports_this_week_against_last_week(client, school):  # noqa: F811
    for sid in ("S1", "S2", "OTHER"):
        _add(client, school, sid)
    _enter(client, school, 0.6, "S1", assessed_on="2026-10-02")
    _enter(client, school, 0.1, "S1", assessed_on="2026-10-09")
    _enter(client, school, 0.8, "S2", assessed_on="2026-10-09")
    _enter(client, school, 0.1, "OTHER", subject="ENGLISH", assessed_on="2026-10-09")

    report = client.post("/triage", headers=school["h"], json={"subject": "MATH"}).json()
    assert (report["as_of"], report["total_students"], report["tested_this_week"]) == ("2026-10-09", 2, 2)
    s1 = report["tiers"]["remediation"]["students"][0]
    assert (s1["student_id"], s1["previous_score"], s1["movement"]) == ("S1", 0.6, "moved_into_help")

    earlier = client.post("/triage", headers=school["h"], json={"subject": "MATH", "as_of": "2026-10-03"}).json()
    assert earlier["total_students"] == 1 and earlier["tiers"]["on_track"]["count"] == 1
