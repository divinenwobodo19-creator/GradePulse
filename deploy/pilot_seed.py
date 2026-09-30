#!/usr/bin/env python3
"""
GradePulse pilot seed tool.

Creates or attaches the pilot schools (accounts + rosters + content catalog) and
optionally runs recommend -> update rounds so the bandit has real history and
`recommend` returns meaningful picks instead of cold-start noise.

Pure stdlib (urllib) — runs anywhere, in or out of the containers.

Usage:
  python3 deploy/pilot_seed.py --api http://localhost:8000
  python3 deploy/pilot_seed.py --api http://localhost:8000 --scores --rounds 4
  python3 deploy/pilot_seed.py --api http://localhost:8000 --config deploy/pilot_schools.json
"""

import argparse
import csv
import io
import json
import os
import random
import sys
import urllib.error
import urllib.request
import uuid

STUDENT_FIELDS = [
    "student_id", "name", "class_label", "school_name",
    "performance_score", "session_count", "current_topic",
    "education_level", "age_band", "credits_studied", "imd_band", "region_code",
    "grade_history_math", "grade_history_science", "grade_history_english",
    "grade_history_history",
]

GRADE_LEVELS = {
    "JSS1": (1.0, (14.0, 16.0)),
    "JSS2": (2.0, (15.0, 17.0)),
    "JSS3": (3.0, (16.0, 18.0)),
    "SSS1": (4.0, (17.0, 19.0)),
    "SSS2": (5.0, (18.0, 20.0)),
    "SSS3": (6.0, (19.0, 21.0)),
}

DEFAULT_CONFIG = os.path.join(os.path.dirname(__file__), "pilot_schools.json")


def _request(base, method, path, token=None, payload=None, files=None, form=None, timeout=60):
    url = base.rstrip("/") + path
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = "Bearer " + token
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif files is not None:
        boundary = "----gpseed" + uuid.uuid4().hex
        parts = []
        for key, val in (form or {}).items():
            parts.append(b"--" + boundary.encode())
            parts.append('Content-Disposition: form-data; name="{}"'.format(key).encode())
            parts.append(b"")
            parts.append(str(val).encode())
        fname, fbytes, ctype = files
        parts.append(b"--" + boundary.encode())
        parts.append('Content-Disposition: form-data; name="file"; filename="{}"'.format(fname).encode())
        parts.append(("Content-Type: " + ctype).encode())
        parts.append(b"")
        parts.append(fbytes)
        parts.append(b"--" + boundary.encode() + b"--")
        data = b"\r\n".join(parts)
        headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, None


def _ensure_teacher(base, email, password, school_name):
    status, body = _request(base, "POST", "/auth/signup",
                            payload={"email": email, "password": password, "school_name": school_name})
    if status == 200:
        print(f"  account created: {email}")
        return body
    status, body = _request(base, "POST", "/auth/login",
                            payload={"email": email, "password": password})
    if status == 200:
        print(f"  account exists, logged in: {email}")
        return body
    raise SystemExit(f"Could not sign up / log in {email}: HTTP {status} {body}")


def _grade_info(class_label):
    label = (class_label or "").strip().upper()
    for key, (edu, age) in GRADE_LEVELS.items():
        if label.startswith(key):
            return edu, round((age[0] + age[1]) / 2, 1)
    return 0.0, 0.0


def _student_csv(school_name, students):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=STUDENT_FIELDS)
    writer.writeheader()
    for st in students:
        topic = (st.get("topic") or "Math").strip()
        edu, age = _grade_info(st.get("class"))
        history = st.get("history") or []
        hist = ";".join(str(round(float(h), 3)) for h in history)
        cols = {"grade_history_math": "", "grade_history_science": "",
                "grade_history_english": "", "grade_history_history": ""}
        key = "grade_history_" + topic.lower()
        if key in cols:
            cols[key] = hist
        row = {
            "student_id": st["id"], "name": st["name"],
            "class_label": (st.get("class") or "").strip().upper(),
            "school_name": school_name,
            "performance_score": str(st.get("perf", 0.5)),
            "session_count": str(st.get("sessions", 0)),
            "current_topic": topic,
            "education_level": str(edu),
            "age_band": str(age),
            "credits_studied": str(round(edu * 4.0, 1)),
            "imd_band": "0.5",
            "region_code": "1.0",
        }
        row.update(cols)
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _ingest(base, token, kind, csv_bytes):
    files = ("students.csv" if kind == "students" else "content.csv", csv_bytes, "text/csv")
    status, body = _request(base, "POST", "/ingest", token=token,
                            files=files, form={"type": kind})
    if status != 200:
        raise SystemExit(f"/ingest {kind} failed: HTTP {status} {body}")
    if body and body.get("status") != "success":
        raise SystemExit(f"/ingest {kind} completed with errors: {body}")
    return body or {}


def _simulate(base, token, students, rounds):
    random.seed(2026)
    rewarded = 0
    for st in students:
        sid = st["id"]
        for _ in range(rounds):
            status, body = _request(base, "POST", "/recommend", token=token,
                                    payload={"student_id": sid, "top_n": 1})
            if status != 200 or not body:
                continue
            cid = body[0].get("content_id")
            if not cid:
                continue
            reward = round(max(-1.0, min(1.0, float(st.get("perf", 0.5)) + random.uniform(-0.15, 0.15))), 3)
            _request(base, "POST", "/update", token=token,
                     payload={"student_id": sid, "content_id": cid, "reward": reward})
            rewarded += 1
    return rewarded


def _verify(base, token, school_id, school_name):
    status, body = _request(base, "GET", "/students?school_id=" + school_id, token=token)
    count = 0
    if status == 200 and body is not None:
        count = len(body)
    _, summary = _request(base, "GET", "/summary", token=token)
    sessions = (summary or {}).get("total_sessions", 0)
    classes = []
    _, cls = _request(base, "GET", "/classes/" + school_id, token=token)
    if cls:
        classes = [c.get("label") for c in cls]
    print(f"  ✓ {school_name}: {count} students | classes {classes} | brain sessions {sessions}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://localhost:8000", help="Base API URL")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Pilot schools JSON")
    parser.add_argument("--scores", action="store_true", help="Run recommend->update rounds")
    parser.add_argument("--rounds", type=int, default=4, help="Rounds per student (with --scores)")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    content_csv_path = config.get("content_csv") or "sample_data/pilot_grade/pilot_content.csv"
    if not os.path.isabs(content_csv_path):
        content_csv_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), content_csv_path))
    if not os.path.exists(content_csv_path):
        raise SystemExit(f"Content catalog not found at {content_csv_path}; regenerate with generate_pilot_data.py")
    with open(content_csv_path, "rb") as f:
        content_bytes = f.read()

    health_ok = False
    try:
        status, body = _request(args.api, "GET", "/health")
        health_ok = status == 200 and body.get("engine") == "GradePulse"
    except Exception:
        health_ok = False
    if not health_ok:
        raise SystemExit(f"No GradePulse API at {args.api} (engine check failed) — start the demo/prod stack first")

    total_students = total_rewards = 0
    for school in config["schools"]:
        name = school["name"].strip().upper()
        print(f"Seeding {name}")
        teacher = _ensure_teacher(args.api, school["email"], school["password"], name)
        token = teacher["token"]
        school_id = teacher.get("school_id", "")
        cfg = _ingest(args.api, token, "students", _student_csv(name, school["students"]))
        stats = (cfg or {}).get("report", {}).get("stats", {})
        print(f"  students ingested: {stats.get('students_valid', 0)} valid / {stats.get('students_read', 0)} read")
        _ingest(args.api, token, "content", content_bytes)
        if args.scores:
            total_rewards += _simulate(args.api, token, school["students"], args.rounds)
        _verify(args.api, token, school_id, name)
        total_students += len(school["students"])

    print(f"\nDone: {total_students} students across {len(config['schools'])} schools"
          + (f", {total_rewards} recommend->update rounds" if args.scores else "")
          + ".")
    print("Login URLs/emails are in deploy/pilot_schools.json (change the passwords before a real pilot).")


if __name__ == "__main__":
    main()