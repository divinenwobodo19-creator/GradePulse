"""
Tests for data ingestion API endpoint added by Data Engineer (Bob).
Endpoint: POST /ingest

Tests file upload, validation, dry-run mode, school creation, and error handling.
Bob's code — QA writes tests only.

KNOWN BUG (logged by QA 2026-08-31): The endpoint uses relative import
`from ...ingest` in app.py:614 which fails because ingest.py is at the
project root, not inside the linucb_brain package. All ingest requests
return HTTP 500.
Fix: Change to absolute import `from ingest import ingest_students, ingest_content, ValidationReport`.
"""
import os
import uuid
import csv
import io
import pytest
import requests

from live_api import is_real_api

BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")
import uuid
...
TEST_EMAIL = f"ingestapitest_{uuid.uuid4().hex[:8]}@gradepulse.com"
TEST_PASSWORD = "ingestapitest123"


def _api_available():
    return is_real_api()


def _get_token():
    resp = requests.post(f"{BASE_URL}/auth/signup", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD, "school_name": "Ingest Test School"
    })
    if resp.status_code == 200:
        return resp.json()["token"]
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD
    })
    return resp.json()["token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _make_student_csv(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _make_content_csv(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


@pytest.fixture(scope="module")
def api_ready():
    if not _api_available():
        pytest.skip("API server not running")


@pytest.fixture(scope="module")
def token(api_ready):
    return _get_token()


# ── Endpoint structure tests (work even with the import bug) ──────────────────

class TestIngestEndpointStructure:
    """Verify the endpoint exists, requires auth, and accepts the right params."""

    def test_ingest_requires_auth(self, api_ready):
        csv_data = _make_student_csv([{"student_id": "X", "name": "X"}])
        resp = requests.post(
            f"{BASE_URL}/ingest",
            files={"file": ("test.csv", csv_data, "text/csv")},
            data={"type": "students"},
        )
        assert resp.status_code in [401, 403]

    def test_invalid_type_returns_400(self, token):
        csv_data = _make_student_csv([{"student_id": "X", "name": "X"}])
        resp = requests.post(
            f"{BASE_URL}/ingest",
            headers=_headers(token),
            files={"file": ("test.csv", csv_data, "text/csv")},
            data={"type": "invalid_type"},
        )
        assert resp.status_code == 400

    def test_invalid_file_extension_returns_400(self, token):
        resp = requests.post(
            f"{BASE_URL}/ingest",
            headers=_headers(token),
            files={"file": ("test.txt", b"some data", "text/plain")},
            data={"type": "students"},
        )
        assert resp.status_code == 400

    def test_missing_type_returns_422(self, token):
        csv_data = _make_student_csv([{"student_id": "X", "name": "X"}])
        resp = requests.post(
            f"{BASE_URL}/ingest",
            headers=_headers(token),
            files={"file": ("test.csv", csv_data, "text/csv")},
            data={},
        )
        assert resp.status_code == 422

    def test_missing_file_returns_422(self, token):
        resp = requests.post(
            f"{BASE_URL}/ingest",
            headers=_headers(token),
            data={"type": "students"},
        )
        assert resp.status_code == 422


# ── Import bug now fixed — these verify the endpoint succeeds ─────────────────

class TestIngestImportBug:
    """The relative-import bug in app.py:614 is fixed. /ingest must now return
    HTTP 200 with a success report instead of HTTP 500."""

    def test_valid_student_csv_succeeds(self, token):
        csv_data = _make_student_csv([
            {"student_id": "APISTU001", "name": "Test Student One", "performance_score": "0.75"},
            {"student_id": "APISTU002", "name": "Test Student Two", "performance_score": "0.60"},
        ])
        resp = requests.post(
            f"{BASE_URL}/ingest",
            headers=_headers(token),
            files={"file": ("students.csv", csv_data, "text/csv")},
            data={"type": "students"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["report"]["stats"]["students_valid"] == 2

    def test_valid_content_csv_succeeds(self, token):
        csv_data = _make_content_csv([
            {"content_id": "APIC001", "title": "API Test Content", "topic": "Math", "difficulty": "3", "content_type": "video"},
        ])
        resp = requests.post(
            f"{BASE_URL}/ingest",
            headers=_headers(token),
            files={"file": ("content.csv", csv_data, "text/csv")},
            data={"type": "content"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["report"]["stats"]["content_valid"] == 1

    def test_dry_run_returns_200(self, token):
        csv_data = _make_student_csv([{"student_id": "DRY001", "name": "Dry Run"}])
        resp = requests.post(
            f"{BASE_URL}/ingest",
            headers=_headers(token),
            files={"file": ("students.csv", csv_data, "text/csv")},
            data={"type": "students", "dry_run": "true"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_with_school_name_returns_200(self, token):
        csv_data = _make_student_csv([{"student_id": "SCH001", "name": "School Test"}])
        resp = requests.post(
            f"{BASE_URL}/ingest",
            headers=_headers(token),
            files={"file": ("students.csv", csv_data, "text/csv")},
            data={"type": "students", "school": "INGEST TEST SCHOOL"},
        )
        assert resp.status_code == 200

    def test_error_message_mentions_ingestion(self, token):
        csv_data = _make_student_csv([{"student_id": "ERR001", "name": "Error Test"}])
        resp = requests.post(
            f"{BASE_URL}/ingest",
            headers=_headers(token),
            files={"file": ("students.csv", csv_data, "text/csv")},
            data={"type": "students"},
        )
        assert resp.status_code == 200


# ── Post-fix verification (import bug is fixed) ───────────────────────────────

class TestIngestPostFix:
    """/ingest returns HTTP 200 once the import bug is fixed."""

    def _make_request(self, token, file_data, filename, type_param, **extra):
        return requests.post(
            f"{BASE_URL}/ingest",
            headers=_headers(token),
            files={"file": (filename, file_data, "text/csv")},
            data={"type": type_param, **extra},
        )

    def test_student_csv_after_fix(self, token):
        csv_data = _make_student_csv([
            {"student_id": "FIX001", "name": "Post Fix Student"},
        ])
        resp = self._make_request(token, csv_data, "students.csv", "students")
        assert resp.status_code == 200

    def test_content_csv_after_fix(self, token):
        csv_data = _make_content_csv([
            {"content_id": "FIXC001", "title": "Post Fix Content", "topic": "Math", "difficulty": "3", "content_type": "video"},
        ])
        resp = self._make_request(token, csv_data, "content.csv", "content")
        assert resp.status_code == 200

    def test_dry_run_after_fix(self, token):
        csv_data = _make_student_csv([{"student_id": "FIXD001", "name": "Dry Fix"}])
        resp = self._make_request(token, csv_data, "students.csv", "students", dry_run="true")
        assert resp.status_code == 200
