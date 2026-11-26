#!/usr/bin/env python3
"""
Set up a demo school with a finished term, so a principal can see complete
term report cards: one class, eight subjects, six weekly tests, the exam,
subject remarks, attendance, and form-teacher and principal comments.

The school is made through the normal API (sign-up, then the admin's own
calls), so nothing touches the database directly. A free pilot term is then
given with the operator key, because report cards come with a paid or pilot
term. Talk to the API itself (127.0.0.1:8100 on the live laptop): the web
proxy hides the operator routes.

Pure stdlib. Usage:
  OPERATOR_KEY=... python3 deploy/demo_report_cards.py --api http://127.0.0.1:8100 \
      --email demo@gradepulse.com.ng
  # or read the key from the live server.env:
  python3 deploy/demo_report_cards.py --api http://127.0.0.1:8100 \
      --env-file ~/gradepulse-live-data/server.env

It prints the email and a new random password for the demo admin. Running it
again with the same email fails at sign-up rather than making a second school.
"""

import argparse
import json
import os
import random
import secrets
import sys
import urllib.error
import urllib.request

SCHOOL = "Demo Secondary School"
ADDRESS = "14 Ogui Road, Enugu"
PRINCIPAL = "Mrs. A. N. Eze"
CLASS = "JSS2A"
SUBJECTS = ["ENGLISH", "MATHEMATICS", "BASIC SCIENCE", "BASIC TECHNOLOGY", "SOCIAL STUDIES",
            "CIVIC EDUCATION", "CRS", "IGBO"]
TERM = {"session": "2026/2027", "name": "First Term", "starts_on": "2026-09-14", "ends_on": "2026-12-11",
        "next_term_begins": "2027-01-11", "days_opened": 62}
TEST_DAYS = ["2026-09-25", "2026-10-09", "2026-10-23", "2026-11-06", "2026-11-13", "2026-11-20"]
STUDENTS = [
    ("DSS/24/001", "Adaeze Okafor", 0.86), ("DSS/24/002", "Chinedu Eze", 0.71),
    ("DSS/24/003", "Ifeoma Nwankwo", 0.78), ("DSS/24/004", "Emeka Obi", 0.55),
    ("DSS/24/005", "Ngozi Ugwu", 0.64), ("DSS/24/006", "Tobenna Agu", 0.48),
    ("DSS/24/007", "Chiamaka Onu", 0.82), ("DSS/24/008", "Kelechi Nnaji", 0.59),
    ("DSS/24/009", "Somto Ani", 0.69), ("DSS/24/010", "Uchenna Ede", 0.42),
    ("DSS/24/011", "Amarachi Odo", 0.75), ("DSS/24/012", "Obinna Mba", 0.62),
]
REMARKS = [(0.75, "Excellent work this term"), (0.65, "Very good, keep it up"), (0.55, "Good effort"),
           (0.45, "Fair, needs more practice"), (0.0, "Needs extra help and practice")]
FORM_COMMENTS = [(0.75, "A diligent and well-behaved student. Keep it up."),
                 (0.6, "A good term. More attention in class will bring even better results."),
                 (0.0, "Can do better with steady work and regular revision.")]
PRINCIPAL_COMMENTS = [(0.75, "An excellent result. Well done."), (0.6, "A good result. Aim higher next term."),
                      (0.0, "You can do better. Work hard next term.")]


def pick(table, value):
    return next(text for floor, text in table if value >= floor)


def call(base, method, path, token=None, payload=None, operator_key=None):
    headers = {"Accept": "application/json", "User-Agent": "gradepulse-demo-seed"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if operator_key:
        headers["X-Operator-Key"] = operator_key
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} failed ({e.code}): {e.read().decode(errors='replace')[:300]}")
    return json.loads(body) if body else {}


def operator_key_from(env_file):
    if os.environ.get("OPERATOR_KEY"):
        return os.environ["OPERATOR_KEY"]
    if env_file:
        with open(os.path.expanduser(env_file)) as f:
            for line in f:
                line = line.strip().removeprefix("export ")
                if line.startswith("OPERATOR_KEY="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit("Set OPERATOR_KEY or pass --env-file with an OPERATOR_KEY line")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://127.0.0.1:8100")
    parser.add_argument("--email", default="demo@gradepulse.com.ng")
    parser.add_argument("--env-file", help="a server.env holding OPERATOR_KEY")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    operator_key = operator_key_from(args.env_file)
    rng = random.Random(args.seed)
    password = "Card-" + secrets.token_urlsafe(12)

    admin = call(args.api, "POST", "/auth/signup", payload={
        "email": args.email, "password": password, "school_name": SCHOOL})
    token, school_id = admin["token"], admin["school_id"]
    call(args.api, "PUT", "/subjects", token, {"subjects": SUBJECTS})
    class_id = call(args.api, "POST", f"/classes/{school_id}", token, {"label": CLASS})["class_id"]
    for student_id, name, _ in STUDENTS:
        call(args.api, "POST", "/students", token, {"student_id": student_id, "name": name, "class_id": class_id})

    # Pilot term first: entering scores for a whole class can need it.
    call(args.api, "POST", "/billing/pilot", payload={"email": args.email, "students": 100},
         operator_key=operator_key)

    # Each student has a level, each subject a small lean, and each test some noise.
    lean = {(sid, subject): rng.uniform(-0.08, 0.08) for sid, _, _ in STUDENTS for subject in SUBJECTS}

    def mark(sid, level, subject, spread):
        return round(min(1.0, max(0.05, level + lean[(sid, subject)] + rng.uniform(-spread, spread))), 3)

    for week, day in enumerate(TEST_DAYS, start=1):
        call(args.api, "POST", "/bulk-update", token, {"assessed_on": day, "label": f"Week {week * 2} test", "entries": [
            {"student_id": sid, "subject": subject, "score": mark(sid, level, subject, 0.1)}
            for sid, _, level in STUDENTS for subject in SUBJECTS]})

    call(args.api, "PUT", "/report-settings", token, {
        "ca_weight": 40, "show_positions": True, "address": ADDRESS, "principal_name": PRINCIPAL,
        "grade_scale": call(args.api, "GET", "/report-settings", token)["grade_scale"]})
    term_id = call(args.api, "POST", "/terms", token, TERM)["term_id"]
    for subject in SUBJECTS:
        exams = {sid: mark(sid, level, subject, 0.07) for sid, _, level in STUDENTS}
        call(args.api, "PUT", f"/terms/{term_id}/exam-scores", token, {"subject": subject, "entries": [
            {"student_id": sid, "score": score} for sid, score in exams.items()]})
        call(args.api, "PUT", f"/terms/{term_id}/remarks", token, {"entries": [
            {"student_id": sid, "subject": subject, "remark": pick(REMARKS, score)} for sid, score in exams.items()]})
    call(args.api, "PUT", f"/terms/{term_id}/comments", token, {"entries": [
        {"student_id": sid, "days_present": TERM["days_opened"] - rng.choice([0, 0, 1, 2, 3, 5]),
         "form_teacher_comment": pick(FORM_COMMENTS, level), "principal_comment": pick(PRINCIPAL_COMMENTS, level)}
        for sid, _, level in STUDENTS]})

    cards = call(args.api, "GET", f"/terms/{term_id}/report-cards?class_id={class_id}", token)["cards"]
    incomplete = [c["name"] for c in cards if c["missing"]]
    print(f"Demo school ready: {SCHOOL}, class {CLASS}, {len(cards)} report cards"
          + (f" ({len(incomplete)} incomplete)" if incomplete else ", all complete"))
    print(f"Sign in at the site with:\n  email:    {args.email}\n  password: {password}")
    print("Then open Report cards, pick First Term 2026/2027 and JSS2A, and go to 3. Preview & print.")


if __name__ == "__main__":
    main()
