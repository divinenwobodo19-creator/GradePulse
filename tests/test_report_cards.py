"""
Term report cards: CA from the term's weekly tests, the exam, grades,
positions, remarks, comments and attendance. Offline, against TestClient.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from linucb_brain.api import app as app_module
from linucb_brain.api import report_cards
from linucb_brain.api.app import app


# ── The calculation ────────────────────────────────────────────────────────

def _students(*ids):
    return [{"pk": i + 1, "student_id": sid, "name": sid} for i, sid in enumerate(ids)]


def test_ca_and_exam_are_weighted_and_graded_on_waec():
    settings = report_cards.settings_with_defaults({})
    cards = report_cards.build_cards(
        _students("ADA"), ["MATH"],
        weekly=[{"student_pk": 1, "subject": "MATH", "score": 0.8}, {"student_pk": 1, "subject": "MATH", "score": 0.6}],
        exams=[{"student_pk": 1, "subject": "MATH", "score": 0.75}],
        remarks=[], comments=[], settings=settings,
    )
    row = cards[0]["subjects"][0]
    # CA: mean 0.7 x 40 = 28; exam: 0.75 x 60 = 45; total 73 -> B2.
    assert (row["ca"], row["exam"], row["total"], row["grade"], row["tests"]) == (28.0, 45.0, 73.0, "B2", 2)
    assert row["grade_remark"] == "Very good"


def test_school_can_change_the_split():
    settings = report_cards.settings_with_defaults({"ca_weight": 30})
    cards = report_cards.build_cards(
        _students("ADA"), ["MATH"],
        weekly=[{"student_pk": 1, "subject": "MATH", "score": 1.0}],
        exams=[{"student_pk": 1, "subject": "MATH", "score": 0.5}],
        remarks=[], comments=[], settings=settings,
    )
    assert cards[0]["subjects"][0]["total"] == 65.0  # 30 + 35


def test_missing_exam_is_flagged_not_counted_as_zero():
    settings = report_cards.settings_with_defaults({})
    cards = report_cards.build_cards(
        _students("ADA", "BAYO"), ["MATH", "ENGLISH"],
        weekly=[{"student_pk": 1, "subject": "MATH", "score": 0.5}, {"student_pk": 1, "subject": "ENGLISH", "score": 0.9},
                {"student_pk": 2, "subject": "MATH", "score": 0.5}],
        exams=[{"student_pk": 1, "subject": "MATH", "score": 0.5}, {"student_pk": 2, "subject": "MATH", "score": 0.5}],
        remarks=[], comments=[], settings=settings,
    )
    ada, bayo = cards
    english = next(r for r in ada["subjects"] if r["subject"] == "ENGLISH")
    assert english["total"] is None and english["ca"] == 36.0
    assert ada["missing"] == ["ENGLISH"]
    # A part-filled card gets no overall position; complete ones are ranked.
    assert ada["position"] is None and bayo["position"] == 1
    # Subjects a student has no marks in are left off their card.
    assert [r["subject"] for r in bayo["subjects"]] == ["MATH"]


def test_positions_use_competition_ranking_and_can_be_switched_off():
    weekly = [{"student_pk": pk, "subject": "MATH", "score": s} for pk, s in ((1, 0.9), (2, 0.8), (3, 0.8), (4, 0.7))]
    exams = [{"student_pk": pk, "subject": "MATH", "score": s} for pk, s in ((1, 0.9), (2, 0.8), (3, 0.8), (4, 0.7))]
    on = report_cards.build_cards(_students("A", "B", "C", "D"), ["MATH"], weekly, exams, [], [],
                                  report_cards.settings_with_defaults({}))
    assert [c["subjects"][0]["position"] for c in on] == [1, 2, 2, 4]
    assert [c["position"] for c in on] == [1, 2, 2, 4]
    assert on[0]["subjects"][0]["highest"] == 90.0 and on[0]["subjects"][0]["lowest"] == 70.0
    assert on[0]["subjects"][0]["class_average"] == 80.0
    off = report_cards.build_cards(_students("A", "B", "C", "D"), ["MATH"], weekly, exams, [], [],
                                   report_cards.settings_with_defaults({"show_positions": False}))
    assert all(c["position"] is None and c["subjects"][0]["position"] is None for c in off)


def test_grade_scale_validation():
    scale = report_cards.clean_grade_scale([{"grade": "B", "min": 50, "remark": "Good"},
                                            {"grade": "A", "min": 70}, {"grade": "F", "min": 0}])
    assert [b["grade"] for b in scale] == ["A", "B", "F"]
    for bad in ([{"grade": "A", "min": 50}, {"grade": "B", "min": 40}],          # no 0
                [{"grade": "A", "min": 50}, {"grade": "A", "min": 0}],           # same name
                [{"grade": "A", "min": 0}, {"grade": "B", "min": 0}],            # same cut-off
                [{"grade": "A", "min": 0}]):                                     # too few
        with pytest.raises(ValueError):
            report_cards.clean_grade_scale(bad)


# ── The API ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _fresh_signup_budget():
    app_module.SIGNUP_LIMITER.reset()
    yield


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def school(client):
    """An admin, a teacher of class A, classes A and B, two students in A and
    one in B, each with weekly MATH tests inside and outside the term."""
    admin = client.post("/auth/signup", json={
        "email": f"adm_{uuid.uuid4().hex[:6]}@rc.local", "password": "Kettle-Mango-42", "school_name": "Report School",
    }).json()
    a = _hdr(admin["token"])
    code = client.post("/invites", headers=a).json()["code"]
    teacher = client.post("/auth/signup", json={
        "email": f"tch_{uuid.uuid4().hex[:6]}@rc.local", "password": "Kettle-Mango-42", "invite_code": code,
    }).json()
    sid = admin["school_id"]
    class_a = client.post(f"/classes/{sid}", headers=a, json={"label": "SS1A"}).json()["class_id"]
    class_b = client.post(f"/classes/{sid}", headers=a, json={"label": "SS1B"}).json()["class_id"]
    for student_id, class_id in (("ADA", class_a), ("BAYO", class_a), ("CHI", class_b)):
        assert client.post("/students", headers=a, json={
            "student_id": student_id, "name": student_id.title(), "class_id": class_id}).status_code == 200
    for day, score in (("2026-09-20", 0.8), ("2026-10-10", 0.6), ("2026-05-01", 0.0)):  # the last is last term
        assert client.post("/bulk-update", headers=a, json={"assessed_on": day, "entries": [
            {"student_id": s, "subject": "MATH", "score": score} for s in ("ADA", "BAYO", "CHI")]}).status_code == 200
    client.put(f"/members/{teacher['id']}/classes", headers=a, json={"class_ids": [class_a]})
    term = client.post("/terms", headers=a, json={
        "session": "2026/2027", "name": "First Term", "starts_on": "2026-09-14", "ends_on": "2026-12-18",
        "next_term_begins": "2027-01-11", "days_opened": 60}).json()
    return {"admin": a, "teacher": _hdr(teacher["token"]), "a": class_a, "b": class_b, "term": term["term_id"]}


def test_full_report_card_flow(client, school):
    a, t, term = school["admin"], school["teacher"], school["term"]
    assert client.put("/report-settings", headers=a, json={
        "ca_weight": 40, "grade_scale": report_cards.DEFAULT_GRADE_SCALE, "show_positions": True,
        "address": "12 Ogui Road, Enugu", "principal_name": "Mrs N. Okafor"}).status_code == 200
    # The teacher enters the exam and remarks for their class...
    r = client.put(f"/terms/{term}/exam-scores", headers=t, json={"subject": "math", "entries": [
        {"student_id": "ADA", "score": 0.75}, {"student_id": "BAYO", "score": 0.5}]})
    assert r.status_code == 200, r.text
    assert client.put(f"/terms/{term}/remarks", headers=t, json={"entries": [
        {"student_id": "ADA", "subject": "MATH", "remark": "  Strong   term "}]}).status_code == 200
    assert client.put(f"/terms/{term}/comments", headers=t, json={"entries": [
        {"student_id": "ADA", "days_present": 58, "form_teacher_comment": "A focused student."}]}).status_code == 200
    # ...and the admin adds the principal's comment without touching the rest.
    assert client.put(f"/terms/{term}/comments", headers=a, json={"entries": [
        {"student_id": "ADA", "principal_comment": "Well done."}]}).status_code == 200

    body = client.get(f"/terms/{term}/report-cards", headers=t, params={"class_id": school["a"]}).json()
    assert body["class"]["label"] == "SS1A" and body["class_size"] == 2
    assert body["school"]["address"] == "12 Ogui Road, Enugu"
    assert body["term"]["next_term_begins"] == "2027-01-11" and body["term"]["days_opened"] == 60
    assert body["settings"]["exam_weight"] == 60
    ada = next(c for c in body["cards"] if c["student_id"] == "ADA")
    math = ada["subjects"][0]
    # Only the two tests inside the term count: mean 0.7 -> CA 28; exam 45.
    assert (math["tests"], math["ca"], math["exam"], math["total"], math["grade"]) == (2, 28.0, 45.0, 73.0, "B2")
    assert math["teacher_remark"] == "Strong term" and math["position"] == 1
    assert (ada["days_present"], ada["form_teacher_comment"], ada["principal_comment"]) == (
        58, "A focused student.", "Well done.")
    assert ada["position"] == 1


def test_clearing_an_exam_score(client, school):
    a, term = school["admin"], school["term"]
    client.put(f"/terms/{term}/exam-scores", headers=a, json={"subject": "MATH", "entries": [
        {"student_id": "ADA", "score": 0.5}]})
    client.put(f"/terms/{term}/exam-scores", headers=a, json={"subject": "MATH", "entries": [
        {"student_id": "ADA", "score": None}]})
    ada = next(c for c in client.get(f"/terms/{term}/report-cards", headers=a,
                                     params={"class_id": school["a"]}).json()["cards"] if c["student_id"] == "ADA")
    assert ada["subjects"][0]["exam"] is None and ada["missing"] == ["MATH"]


def test_teachers_stay_inside_their_classes(client, school):
    t, term = school["teacher"], school["term"]
    assert client.get(f"/terms/{term}/report-cards", headers=t, params={"class_id": school["b"]}).status_code == 403
    assert client.put(f"/terms/{term}/exam-scores", headers=t, json={"subject": "MATH", "entries": [
        {"student_id": "CHI", "score": 0.5}]}).status_code == 404
    assert client.put(f"/terms/{term}/comments", headers=t, json={"entries": [
        {"student_id": "ADA", "principal_comment": "Not mine to write"}]}).status_code == 403
    # Setting up terms and the grading scale is for admins.
    assert client.post("/terms", headers=t, json={
        "session": "2026/2027", "name": "Second Term", "starts_on": "2027-01-11", "ends_on": "2027-04-01"}).status_code == 403
    assert client.put("/report-settings", headers=t, json={
        "grade_scale": report_cards.DEFAULT_GRADE_SCALE}).status_code == 403


def test_terms_are_per_school(client, school):
    other = client.post("/auth/signup", json={
        "email": f"oth_{uuid.uuid4().hex[:6]}@rc.local", "password": "Kettle-Mango-42", "school_name": "Other"}).json()
    o = _hdr(other["token"])
    assert school["term"] not in [t["term_id"] for t in client.get("/terms", headers=o).json()]
    assert client.get(f"/terms/{school['term']}/report-cards", headers=o,
                      params={"class_id": school["a"]}).status_code == 404
    assert client.put(f"/terms/{school['term']}/exam-scores", headers=o, json={
        "subject": "MATH", "entries": []}).status_code == 404


def test_term_validation_and_editing(client, school):
    a, term = school["admin"], school["term"]
    assert client.post("/terms", headers=a, json={
        "session": "2026/2027", "name": "Bad", "starts_on": "2026-12-01", "ends_on": "2026-09-01"}).status_code == 422
    assert client.put(f"/terms/{term}", headers=a, json={"ends_on": "2026-01-01"}).status_code == 400
    r = client.put(f"/terms/{term}", headers=a, json={"name": "First  Term", "next_term_begins": None})
    assert r.status_code == 200 and r.json()["name"] == "First Term" and r.json()["next_term_begins"] == ""
    assert client.delete(f"/terms/{term}", headers=a).status_code == 200
    assert client.get(f"/terms/{term}/report-cards", headers=a, params={"class_id": school["a"]}).status_code == 404


def test_bad_grade_scale_is_refused(client, school):
    r = client.put("/report-settings", headers=school["admin"], json={
        "ca_weight": 40, "grade_scale": [{"grade": "A", "min": 50}, {"grade": "B", "min": 40}]})
    assert r.status_code == 400 and "0" in r.json()["detail"]
    # Defaults come back for a school that never saved settings.
    assert client.get("/report-settings", headers=school["teacher"]).json()["ca_weight"] == 40


def test_remarks_only_for_the_school_subjects(client, school):
    r = client.put(f"/terms/{school['term']}/remarks", headers=school["admin"], json={"entries": [
        {"student_id": "ADA", "subject": "ASTROLOGY", "remark": "Stars aligned"}]})
    assert r.status_code == 400


def test_school_data_export_includes_report_card_entries(client, school):
    import csv
    import io
    import zipfile
    a, term = school["admin"], school["term"]
    client.put(f"/terms/{term}/exam-scores", headers=a, json={"subject": "MATH", "entries": [
        {"student_id": "ADA", "score": 0.75}]})
    client.put(f"/terms/{term}/remarks", headers=a, json={"entries": [
        {"student_id": "ADA", "subject": "MATH", "remark": "Strong term"}]})
    client.put(f"/terms/{term}/comments", headers=a, json={"entries": [
        {"student_id": "ADA", "days_present": 58, "principal_comment": "Well done."}]})
    archive = zipfile.ZipFile(io.BytesIO(client.get("/export", headers=a).content))

    def rows(name):
        return list(csv.DictReader(io.StringIO(archive.read(name).decode())))

    assert rows("terms.csv")[0]["name"] == "First Term"
    assert rows("exam_scores.csv") == [{"session": "2026/2027", "term": "First Term", "student_id": "ADA",
                                        "name": "Ada", "subject": "MATH", "exam_percent": "75.0"}]
    assert rows("subject_remarks.csv")[0]["remark"] == "Strong term"
    comment = rows("report_comments.csv")[0]
    assert (comment["days_present"], comment["principal_comment"]) == ("58", "Well done.")


def test_free_plan_schools_do_not_get_report_cards(client, school, monkeypatch):
    """Report cards are the heart of the paid plan (founder, 26 Nov 2026)."""
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_test_free_plan")
    monkeypatch.setenv("PRICE_PER_STUDENT_NAIRA", "500")
    monkeypatch.setenv("FREE_STUDENTS", "40")
    for headers, action in ((school["admin"], "Billing page"), (school["teacher"], "Ask your school admin")):
        r = client.get(f"/terms/{school['term']}/report-cards", headers=headers, params={"class_id": school["a"]})
        assert r.status_code == 402
        assert "report cards come with a paid term" in r.json()["detail"] and action in r.json()["detail"]
