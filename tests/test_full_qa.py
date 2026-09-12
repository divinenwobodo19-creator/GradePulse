"""
Comprehensive QA Test Suite — GradePulse Full App (v2)
=======================================================
Tests every public interface with current auth-enabled API.
All endpoints require JWT auth except: POST /auth/signup, POST /auth/login, GET /.

Author: David (QA Tester)
Date: 2026-09-02
"""
import os
import json
import math
import time
import tempfile
import uuid
import numpy as np
import pytest
from pathlib import Path
from typing import Dict, List

from fastapi.testclient import TestClient
from linucb_brain.api.app import app
from linucb_brain.brain import Brain

# Clean stale lock files so lifespan can acquire locks
for _lf in ["brain_state.json.lock", "class_config.json.lock",
            "oulad_brain_state.json.lock"]:
    _lp = os.path.join(os.getcwd(), _lf)
    if os.path.exists(_lp):
        os.remove(_lp)

_client = TestClient(app).__enter__()
from linucb_brain.models.student import Student, normalize_label
from linucb_brain.models.content import Content
from linucb_brain.core.context import build_context, build_context_split, get_context_dimension, CONTENT_TYPES
from linucb_brain.core.reward import calculate_reward
from linucb_brain.core.clustering import ClusteringEngine

client = TestClient(app)

PILOT_DIR = Path(__file__).parent.parent / "sample_data" / "pilot_grade"
LARGE_DIR = Path(__file__).parent.parent / "sample_data" / "large"

TEST_EMAIL = f"qatest_{uuid.uuid4().hex[:8]}@gradepulse.com"
TEST_PASSWORD = "QATestPass123!"


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def _signup(email=TEST_EMAIL, password=TEST_PASSWORD, school="QA Test School"):
    r = client.post("/auth/signup", json={
        "email": email, "password": password, "school_name": school
    })
    return r


def _login(email=TEST_EMAIL, password=TEST_PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def _get_token(email=TEST_EMAIL, password=TEST_PASSWORD):
    r = _signup(email, password)
    if r.status_code == 200:
        return r.json()["token"]
    r = _login(email, password)
    return r.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def token():
    return _get_token()


@pytest.fixture(scope="module")
def auth_headers(token):
    return _auth(token)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthSignup:
    def test_signup_returns_200(self):
        email = f"signup_{uuid.uuid4().hex[:6]}@test.com"
        r = _signup(email)
        assert r.status_code == 200

    def test_signup_returns_token(self):
        email = f"signup_{uuid.uuid4().hex[:6]}@test.com"
        r = _signup(email)
        assert "token" in r.json()
        assert len(r.json()["token"]) > 0

    def test_signup_returns_user_fields(self):
        email = f"signup_{uuid.uuid4().hex[:6]}@test.com"
        r = _signup(email, school="My School")
        data = r.json()
        assert "id" in data
        assert data["email"] == email
        assert "school_id" in data
        assert data["school_name"] == "MY SCHOOL"

    def test_signup_duplicate_email_returns_400(self):
        email = f"dup_{uuid.uuid4().hex[:6]}@test.com"
        _signup(email)
        r = _signup(email)
        assert r.status_code == 400

    def test_signup_missing_email_returns_422(self):
        r = client.post("/auth/signup", json={"password": "pass123"})
        assert r.status_code == 422

    def test_signup_missing_password_returns_422(self):
        r = client.post("/auth/signup", json={"email": "x@test.com"})
        assert r.status_code == 422

    def test_signup_empty_body_returns_422(self):
        r = client.post("/auth/signup", json={})
        assert r.status_code == 422


class TestAuthLogin:
    def test_login_returns_200(self):
        email = f"login_{uuid.uuid4().hex[:6]}@test.com"
        _signup(email, "pass123")
        r = _login(email, "pass123")
        assert r.status_code == 200

    def test_login_returns_token(self):
        email = f"login_{uuid.uuid4().hex[:6]}@test.com"
        _signup(email, "pass123")
        r = _login(email, "pass123")
        assert "token" in r.json()

    def test_login_wrong_password_returns_401(self):
        email = f"login_{uuid.uuid4().hex[:6]}@test.com"
        _signup(email, "pass123")
        r = _login(email, "wrongpass")
        assert r.status_code == 401

    def test_login_nonexistent_user_returns_401(self):
        r = _login("nonexistent@test.com", "pass123")
        assert r.status_code == 401


class TestAuthMe:
    def test_me_returns_user(self, auth_headers):
        r = client.get("/auth/me", headers=auth_headers)
        assert r.status_code == 200
        assert "id" in r.json()
        assert "email" in r.json()

    def test_me_without_auth_returns_401(self):
        r = client.get("/auth/me")
        assert r.status_code == 401

    def test_me_with_invalid_token_returns_401(self):
        r = client.get("/auth/me", headers={"Authorization": "Bearer invalid"})
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: ROOT & HEALTH
# ═══════════════════════════════════════════════════════════════════════════════


class TestRootEndpoint:
    def test_root_returns_200(self):
        r = client.get("/")
        assert r.status_code == 200

    def test_root_has_status_field(self):
        data = client.get("/").json()
        assert data["status"] == "alive"

    def test_root_has_engine_field(self):
        assert "engine" in client.get("/").json()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: SCHOOL CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchoolsAPI:
    def test_list_schools_returns_200(self, auth_headers):
        r = client.get("/schools", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_schools_without_auth_returns_401(self):
        r = client.get("/schools")
        assert r.status_code == 401

    def test_create_school_returns_200(self, auth_headers):
        r = client.post("/schools", headers=auth_headers,
                        json={"name": f"QA School {uuid.uuid4().hex[:4]}"})
        assert r.status_code == 200
        assert "school_id" in r.json()

    def test_create_school_uppercases_name(self, auth_headers):
        name = f"qa school {uuid.uuid4().hex[:4]}"
        r = client.post("/schools", headers=auth_headers, json={"name": name})
        assert r.json()["name"] == name.upper()

    def test_update_school_returns_200(self, auth_headers):
        r = client.post("/schools", headers=auth_headers,
                        json={"name": f"Update School {uuid.uuid4().hex[:4]}"})
        sid = r.json()["school_id"]
        r = client.put(f"/schools/{sid}", headers=auth_headers,
                       json={"name": "Updated Name"})
        assert r.status_code == 200
        assert r.json()["name"] == "UPDATED NAME"

    def test_delete_school_returns_200(self, auth_headers):
        r = client.post("/schools", headers=auth_headers,
                        json={"name": f"Delete School {uuid.uuid4().hex[:4]}"})
        sid = r.json()["school_id"]
        r = client.delete(f"/schools/{sid}", headers=auth_headers)
        assert r.status_code == 200

    def test_delete_nonexistent_school_returns_404(self, auth_headers):
        r = client.delete("/schools/nonexistent", headers=auth_headers)
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: CLASS CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestClassesAPI:
    @pytest.fixture
    def school_id(self, auth_headers):
        r = client.post("/schools", headers=auth_headers,
                        json={"name": f"Class Test School {uuid.uuid4().hex[:4]}"})
        return r.json()["school_id"]

    def test_list_classes_returns_200(self, auth_headers, school_id):
        r = client.get(f"/classes/{school_id}", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_class_returns_200(self, auth_headers, school_id):
        r = client.post(f"/classes/{school_id}", headers=auth_headers,
                        json={"label": f"JSS1A_{uuid.uuid4().hex[:4]}"})
        assert r.status_code == 200
        assert "class_id" in r.json()

    def test_create_duplicate_class_returns_400(self, auth_headers, school_id):
        label = f"DUP_{uuid.uuid4().hex[:4]}"
        client.post(f"/classes/{school_id}", headers=auth_headers,
                    json={"label": label})
        r = client.post(f"/classes/{school_id}", headers=auth_headers,
                        json={"label": label})
        assert r.status_code == 400

    def test_update_class_returns_200(self, auth_headers, school_id):
        r = client.post(f"/classes/{school_id}", headers=auth_headers,
                        json={"label": f"UPD_{uuid.uuid4().hex[:4]}"})
        cid = r.json()["class_id"]
        r = client.put(f"/classes/{school_id}/{cid}", headers=auth_headers,
                       json={"label": "NEWLABEL"})
        assert r.status_code == 200
        assert r.json()["label"] == "NEWLABEL"

    def test_delete_class_returns_200(self, auth_headers, school_id):
        r = client.post(f"/classes/{school_id}", headers=auth_headers,
                        json={"label": f"DEL_{uuid.uuid4().hex[:4]}"})
        cid = r.json()["class_id"]
        r = client.delete(f"/classes/{school_id}/{cid}", headers=auth_headers)
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: STUDENT CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestStudentsAPI:
    def test_list_students_returns_200(self, auth_headers):
        r = client.get("/students", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_add_student_returns_200(self, auth_headers):
        sid = f"QA_{uuid.uuid4().hex[:6]}"
        r = client.post("/students", headers=auth_headers, json={
            "student_id": sid, "name": "QA Test Student",
            "performance_score": 0.75, "current_topic": "Math"
        })
        assert r.status_code == 200

    def test_add_student_echoes_fields(self, auth_headers):
        sid = f"QA_{uuid.uuid4().hex[:6]}"
        r = client.post("/students", headers=auth_headers, json={
            "student_id": sid, "name": "Echo Test",
            "performance_score": 0.6, "current_topic": "Science",
            "grade_history": {"Math": [0.5, 0.6]},
            "metadata": {"note": "test"}
        })
        data = r.json()
        assert data["student_id"] == sid
        assert data["name"] == "Echo Test"
        assert data["performance_score"] == 0.6

    def test_add_student_empty_name_returns_200(self, auth_headers):
        sid = f"QA_EMPTY_{uuid.uuid4().hex[:6]}"
        r = client.post("/students", headers=auth_headers,
                        json={"student_id": sid, "name": ""})
        assert r.status_code == 200

    def test_add_student_zero_performance(self, auth_headers):
        sid = f"QA_ZERO_{uuid.uuid4().hex[:6]}"
        r = client.post("/students", headers=auth_headers, json={
            "student_id": sid, "name": "Zero", "performance_score": 0.0
        })
        assert r.status_code == 200

    def test_add_student_max_performance(self, auth_headers):
        sid = f"QA_MAX_{uuid.uuid4().hex[:6]}"
        r = client.post("/students", headers=auth_headers, json={
            "student_id": sid, "name": "Max", "performance_score": 1.0
        })
        assert r.status_code == 200

    def test_update_student_returns_200(self, auth_headers):
        sid = f"QA_UPD_{uuid.uuid4().hex[:6]}"
        client.post("/students", headers=auth_headers,
                    json={"student_id": sid, "name": "Original"})
        r = client.put(f"/students/{sid}", headers=auth_headers,
                       json={"name": "Updated"})
        assert r.status_code == 200
        assert r.json()["name"] == "Updated"

    def test_update_nonexistent_student_returns_404(self, auth_headers):
        r = client.put("/students/DOES_NOT_EXIST", headers=auth_headers,
                       json={"name": "X"})
        assert r.status_code == 404

    def test_delete_student_returns_200(self, auth_headers):
        sid = f"QA_DEL_{uuid.uuid4().hex[:6]}"
        client.post("/students", headers=auth_headers,
                    json={"student_id": sid, "name": "Delete Me"})
        r = client.delete(f"/students/{sid}", headers=auth_headers)
        assert r.status_code == 200

    def test_delete_nonexistent_student_returns_404(self, auth_headers):
        r = client.delete("/students/DOES_NOT_EXIST", headers=auth_headers)
        assert r.status_code == 404

    def test_add_student_without_auth_returns_401(self):
        r = client.post("/students", json={
            "student_id": "X", "name": "X"
        })
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: CONTENT API
# ═══════════════════════════════════════════════════════════════════════════════


class TestContentAPI:
    def test_add_content_returns_200(self, auth_headers):
        cid = f"QAC_{uuid.uuid4().hex[:6]}"
        r = client.post("/content", headers=auth_headers, json={
            "content_id": cid, "title": "QA Content",
            "topic": "Math", "difficulty": 3, "content_type": "video"
        })
        assert r.status_code == 200

    def test_add_content_echoes_fields(self, auth_headers):
        cid = f"QAC_{uuid.uuid4().hex[:6]}"
        r = client.post("/content", headers=auth_headers, json={
            "content_id": cid, "title": "Echo Content",
            "topic": "Science", "difficulty": 5, "content_type": "quiz"
        })
        data = r.json()
        assert data["content_id"] == cid
        assert data["difficulty"] == 5

    def test_add_content_difficulty_too_low_returns_422(self, auth_headers):
        r = client.post("/content", headers=auth_headers, json={
            "content_id": "X", "title": "X", "topic": "X",
            "difficulty": 0, "content_type": "video"
        })
        assert r.status_code == 422

    def test_add_content_difficulty_too_high_returns_422(self, auth_headers):
        r = client.post("/content", headers=auth_headers, json={
            "content_id": "X", "title": "X", "topic": "X",
            "difficulty": 6, "content_type": "video"
        })
        assert r.status_code == 422

    def test_add_content_valid_difficulty_range(self, auth_headers):
        for d in [1, 2, 3, 4, 5]:
            cid = f"QAC_DIFF{d}_{uuid.uuid4().hex[:4]}"
            r = client.post("/content", headers=auth_headers, json={
                "content_id": cid, "title": f"Diff {d}",
                "topic": "Math", "difficulty": d, "content_type": "video"
            })
            assert r.status_code == 200

    def test_add_content_without_auth_returns_401(self):
        r = client.post("/content", json={
            "content_id": "X", "title": "X", "topic": "X",
            "difficulty": 3, "content_type": "video"
        })
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: RECOMMEND API
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecommendAPI:
    @pytest.fixture(autouse=True)
    def _setup(self, auth_headers):
        self.h = auth_headers
        self.sid = f"QAREC_{uuid.uuid4().hex[:6]}"
        self.cid = f"QAREC_C_{uuid.uuid4().hex[:6]}"
        client.post("/students", headers=self.h, json={
            "student_id": self.sid, "name": "Rec Student", "current_topic": "Math"
        })
        client.post("/content", headers=self.h, json={
            "content_id": self.cid, "title": "Rec Content",
            "topic": "Math", "difficulty": 3, "content_type": "video"
        })

    def test_recommend_returns_200(self):
        r = client.post("/recommend", headers=self.h,
                        json={"student_id": self.sid})
        assert r.status_code == 200

    def test_recommend_returns_content_id(self):
        data = client.post("/recommend", headers=self.h,
                           json={"student_id": self.sid}).json()
        assert "content_id" in data

    def test_recommend_top_n_3_returns_list(self):
        for i in range(3):
            client.post("/content", headers=self.h, json={
                "content_id": f"{self.cid}_{i}", "title": f"Multi {i}",
                "topic": "Math", "difficulty": 3, "content_type": "video"
            })
        r = client.post("/recommend", headers=self.h,
                        json={"student_id": self.sid, "top_n": 3})
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) == 3

    def test_recommend_nonexistent_student_returns_400(self):
        r = client.post("/recommend", headers=self.h,
                        json={"student_id": "DOES_NOT_EXIST"})
        assert r.status_code == 400

    def test_recommend_with_topic_filter(self):
        client.post("/content", headers=self.h, json={
            "content_id": f"{self.cid}_sci", "title": "Science",
            "topic": "Science", "difficulty": 3, "content_type": "video"
        })
        r = client.post("/recommend", headers=self.h, json={
            "student_id": self.sid, "topic": "Math", "top_n": 1
        })
        assert r.status_code == 200

    def test_recommend_without_auth_returns_401(self):
        r = client.post("/recommend", json={"student_id": "X"})
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8: UPDATE API
# ═══════════════════════════════════════════════════════════════════════════════


class TestUpdateAPI:
    @pytest.fixture(autouse=True)
    def _setup(self, auth_headers):
        self.h = auth_headers
        self.sid = f"QAUPD_{uuid.uuid4().hex[:6]}"
        self.cid = f"QAUPD_C_{uuid.uuid4().hex[:6]}"
        client.post("/students", headers=self.h,
                    json={"student_id": self.sid, "name": "Update Student"})
        client.post("/content", headers=self.h, json={
            "content_id": self.cid, "title": "Update Content",
            "topic": "Math", "difficulty": 3, "content_type": "video"
        })

    def test_update_returns_200(self):
        r = client.post("/update", headers=self.h, json={
            "student_id": self.sid, "content_id": self.cid, "reward": 0.7
        })
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_update_nonexistent_student_returns_404(self):
        r = client.post("/update", headers=self.h, json={
            "student_id": "DOES_NOT_EXIST", "content_id": self.cid, "reward": 0.5
        })
        assert r.status_code == 404

    def test_update_nonexistent_content_returns_404(self):
        r = client.post("/update", headers=self.h, json={
            "student_id": self.sid, "content_id": "DOES_NOT_EXIST", "reward": 0.5
        })
        assert r.status_code == 404

    def test_update_negative_reward_accepted(self):
        r = client.post("/update", headers=self.h, json={
            "student_id": self.sid, "content_id": self.cid, "reward": -0.5
        })
        assert r.status_code == 200

    def test_update_reward_boundary_minus_1(self):
        r = client.post("/update", headers=self.h, json={
            "student_id": self.sid, "content_id": self.cid, "reward": -1.0
        })
        assert r.status_code == 200

    def test_update_reward_boundary_plus_1(self):
        r = client.post("/update", headers=self.h, json={
            "student_id": self.sid, "content_id": self.cid, "reward": 1.0
        })
        assert r.status_code == 200

    def test_update_reward_out_of_range_returns_422(self):
        r = client.post("/update", headers=self.h, json={
            "student_id": self.sid, "content_id": self.cid, "reward": 1.5
        })
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9: CALCULATE REWARD API
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalculateRewardAPI:
    def test_reward_positive_improvement(self, auth_headers):
        r = client.post("/calculate-reward", headers=auth_headers, json={
            "before_score": 0.5, "after_score": 0.7,
            "completed": True, "time_spent_ratio": 1.0,
            "engaged": True, "churned": False
        })
        assert r.status_code == 200
        assert r.json()["reward"] > 0

    def test_reward_churned_negative_one(self, auth_headers):
        r = client.post("/calculate-reward", headers=auth_headers, json={
            "before_score": 0.5, "after_score": 0.5,
            "completed": False, "time_spent_ratio": 1.0,
            "engaged": False, "churned": True
        })
        assert r.status_code == 200
        assert r.json()["reward"] == -1.0

    def test_reward_without_auth_returns_401(self):
        r = client.post("/calculate-reward", json={
            "before_score": 0.5, "after_score": 0.7,
            "completed": True, "time_spent_ratio": 1.0,
            "engaged": True, "churned": False
        })
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10: SUMMARY & SAVE API
# ═══════════════════════════════════════════════════════════════════════════════


class TestSummaryAPI:
    def test_summary_returns_200(self, auth_headers):
        r = client.get("/summary", headers=auth_headers)
        assert r.status_code == 200

    def test_summary_has_required_fields(self, auth_headers):
        data = client.get("/summary", headers=auth_headers).json()
        for field in ["student_count", "content_count", "total_sessions",
                       "model_type", "current_alpha", "current_gamma",
                       "cumulative_regret"]:
            assert field in data

    def test_summary_student_count_non_negative(self, auth_headers):
        data = client.get("/summary", headers=auth_headers).json()
        assert data["student_count"] >= 0

    def test_summary_without_auth_returns_401(self):
        r = client.get("/summary")
        assert r.status_code == 401


class TestSaveAPI:
    def test_save_returns_200(self, auth_headers):
        r = client.post("/save", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "saved"

    def test_save_without_auth_returns_401(self):
        r = client.post("/save")
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11: TRIAGE & BULK UPDATE API
# ═══════════════════════════════════════════════════════════════════════════════


class TestTriageAPI:
    def test_triage_returns_200(self, auth_headers):
        r = client.post("/triage", headers=auth_headers,
                        json={"subject": "MATH"})
        assert r.status_code == 200
        data = r.json()
        assert "tiers" in data
        assert "remediation" in data["tiers"]

    def test_triage_without_auth_returns_401(self):
        r = client.post("/triage", json={"subject": "MATH"})
        assert r.status_code == 401


class TestBulkUpdateAPI:
    def test_bulk_update_returns_200(self, auth_headers):
        r = client.post("/bulk-update", headers=auth_headers, json={
            "entries": [
                {"student_id": "608041", "subject": "Math", "score": 0.8},
            ]
        })
        assert r.status_code == 200

    def test_bulk_update_without_auth_returns_401(self):
        r = client.post("/bulk-update", json={"entries": []})
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 12: BRAIN METHODS (direct, no API)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBrainAddStudent:
    def test_add_student(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S1", "Alice")
        assert s.student_id == "S1"
        assert "S1" in b.students

    def test_add_duplicate_returns_existing(self):
        b = Brain(model_type="hybrid")
        s1 = b.add_student("S1", "Alice")
        s2 = b.add_student("S1", "Bob")
        assert s1 is s2
        assert s2.name == "Alice"

    def test_add_student_with_kwargs(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S1", "Alice", performance_score=0.9,
                          current_topic="Math",
                          grade_history={"Math": [0.7, 0.8]})
        assert s.performance_score == 0.9
        assert s.current_topic == "Math"


class TestBrainAddContent:
    def test_add_content(self):
        b = Brain(model_type="hybrid")
        c = b.add_content("C1", "Algebra", "Math", 3, "video")
        assert c.content_id == "C1"
        assert "C1" in b.contents

    def test_add_duplicate_returns_existing(self):
        b = Brain(model_type="hybrid")
        c1 = b.add_content("C1", "Algebra", "Math", 3, "video")
        c2 = b.add_content("C1", "Different", "Math", 3, "video")
        assert c1 is c2
        assert c2.title == "Algebra"


class TestBrainRecommend:
    @pytest.fixture
    def brain(self):
        b = Brain(model_type="hybrid")
        for i in range(5):
            b.add_student(f"S{i}", f"Student {i}",
                          performance_score=0.3 + i * 0.15)
            b.add_content(f"C{i}", f"Content {i}",
                          "Math", 2 + i % 4, "video")
        return b

    def test_recommend_returns_content(self, brain):
        rec = brain.recommend("S0")
        assert isinstance(rec, Content)
        assert rec.content_id in brain.contents

    def test_recommend_top_n(self, brain):
        recs = brain.recommend("S0", top_n=3)
        assert isinstance(recs, list)
        assert len(recs) == 3

    def test_recommend_nonexistent_student_raises(self, brain):
        with pytest.raises(KeyError):
            brain.recommend("DOES_NOT_EXIST")

    def test_recommend_with_topic_filter(self, brain):
        brain.add_content("CSCI", "Science", "Science", 3, "quiz")
        rec = brain.recommend("S0", topic="Science")
        assert rec is not None

    def test_recommend_no_matching_topic_raises(self, brain):
        with pytest.raises(ValueError):
            brain.recommend("S0", topic="NONEXISTENT")


class TestBrainUpdate:
    @pytest.fixture
    def brain(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Student 0", performance_score=0.5)
        b.add_content("C0", "Content 0", "Math", 3, "video")
        return b

    def test_update_increments_session_count(self, brain):
        before = brain.update_count
        brain.update("S0", "C0", 0.7)
        assert brain.update_count == before + 1

    def test_update_increments_student_session_count(self, brain):
        before = brain.students["S0"].session_count
        brain.update("S0", "C0", 0.7)
        assert brain.students["S0"].session_count == before + 1

    def test_update_records_session(self, brain):
        before = len(brain.sessions)
        brain.update("S0", "C0", 0.7)
        assert len(brain.sessions) == before + 1

    def test_update_updates_content_avg_reward(self, brain):
        brain.update("S0", "C0", 0.8)
        assert brain.contents["C0"].avg_reward == 0.8

    def test_update_adds_to_grade_history(self, brain):
        brain.update("S0", "C0", 0.9)
        assert "Math" in brain.students["S0"].grade_history

    def test_update_nonexistent_student_raises(self, brain):
        with pytest.raises(KeyError):
            brain.update("DOES_NOT_EXIST", "C0", 0.5)

    def test_update_nonexistent_content_raises(self, brain):
        with pytest.raises(KeyError):
            brain.update("S0", "DOES_NOT_EXIST", 0.5)


class TestBrainPredictGrade:
    def test_predict_with_history(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice", grade_history={"Math": [0.6, 0.8, 0.7]})
        pred = b.predict_grade("S0", "Math")
        assert abs(pred - 0.7) < 0.001

    def test_predict_without_history_uses_performance(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice", performance_score=0.65)
        pred = b.predict_grade("S0", "Math")
        assert abs(pred - 0.65) < 0.001

    def test_predict_nonexistent_student_raises(self):
        b = Brain(model_type="hybrid")
        with pytest.raises(KeyError):
            b.predict_grade("DOES_NOT_EXIST", "Math")


class TestBrainTriage:
    @pytest.fixture
    def brain(self):
        b = Brain(model_type="hybrid")
        for i, (name, perf) in enumerate([
            ("Low", 0.2), ("Mid", 0.6), ("High", 0.9)
        ]):
            b.add_student(f"S{i}", name, performance_score=perf)
            b.add_content(f"C{i}", f"Content {i}", "Math", 3, "video")
            b.update(f"S{i}", f"C{i}", perf)
        return b

    def test_triage_returns_all_tiers(self, brain):
        result = brain.triage("MATH")
        assert "tiers" in result
        assert "remediation" in result["tiers"]
        assert "on_track" in result["tiers"]
        assert "ahead" in result["tiers"]

    def test_triage_empty_subject_returns_zero(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        result = b.triage("NONEXISTENT")
        assert result["total_students"] == 0

    def test_triage_counts_match(self, brain):
        result = brain.triage("MATH")
        total = sum(t["count"] for t in result["tiers"].values())
        assert total == result["total_students"]


class TestBrainBulkUpdate:
    def test_bulk_update(self):
        b = Brain(model_type="hybrid")
        for i in range(5):
            b.add_student(f"S{i}", f"Student {i}")
            b.add_content(f"C{i}", f"Content {i}", "Math", 3, "video")
        entries = [
            {"student_id": "S0", "content_id": "C0", "reward": 0.8},
            {"student_id": "S1", "content_id": "C1", "reward": 0.6},
        ]
        result = b.bulk_update(entries)
        assert result["processed"] == 2
        assert result["avg_reward"] > 0

    def test_bulk_update_empty_list(self):
        b = Brain(model_type="hybrid")
        result = b.bulk_update([])
        assert result["processed"] == 0
        assert result["avg_reward"] == 0.0

    def test_bulk_update_skips_missing_student_id(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        entries = [
            {"student_id": "S0", "content_id": "C0", "reward": 0.8},
            {},
        ]
        result = b.bulk_update(entries)
        assert result["processed"] == 1


class TestBrainWarmStart:
    def test_warm_start(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        b.warm_start([{"student_id": "S0", "content_id": "C0", "reward": 0.8}])
        assert b.update_count == 1

    def test_warm_start_skips_unknown_ids(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        b.warm_start([
            {"student_id": "S0", "content_id": "C0", "reward": 0.8},
            {"student_id": "UNKNOWN", "content_id": "C0", "reward": 0.5},
        ])
        assert b.update_count == 1


class TestBrainNeuralScore:
    def test_neural_score_returns_dict(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        b.update("S0", "C0", 0.7)
        scores = b.neural_score(verbose=False)
        assert isinstance(scores, dict)
        assert "neural_score" in scores

    def test_neural_score_in_range(self):
        b = Brain(model_type="hybrid")
        for i in range(10):
            b.add_student(f"S{i}", f"Student {i}")
            b.add_content(f"C{i}", f"Content {i}", "Math", 3, "video")
            b.update(f"S{i}", f"C{i}", 0.5 + i * 0.05)
        scores = b.neural_score(verbose=False)
        for k, v in scores.items():
            assert 0 <= v <= 10, f"{k} = {v} out of range"


class TestBrainSummary:
    def test_summary_returns_dict(self):
        b = Brain(model_type="hybrid")
        s = b.summary()
        assert isinstance(s, dict)
        assert "student_count" in s

    def test_summary_matches_state(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        s = b.summary()
        assert s["student_count"] == 1
        assert s["content_count"] == 1


class TestBrainSaveLoad:
    def test_save_and_load(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice", performance_score=0.8)
        b.add_content("C0", "Content", "Math", 3, "video")
        b.update("S0", "C0", 0.7)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_brain.json")
            b.save(path)
            loaded = Brain.load(path)
            assert len(loaded.students) == 1
            assert loaded.students["S0"].name == "Alice"
            assert loaded.update_count == 1

    def test_loaded_brain_can_recommend(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_brain.json")
            b.save(path)
            loaded = Brain.load(path)
            rec = loaded.recommend("S0")
            assert rec is not None


class TestBrainExportTeacherData:
    def test_export_returns_dict(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice", performance_score=0.8,
                      grade_history={"Math": [0.7, 0.8]})
        b.add_content("C0", "Content", "Math", 3, "video")
        data = b.export_teacher_data()
        assert "students" in data
        assert "subjects" in data
        assert "generated" in data


class TestBrainMultiObjectiveReward:
    def test_churned_returns_negative_one(self):
        b = Brain(model_type="hybrid")
        assert b.calculate_multi_objective_reward(0.5, True, True, True) == -1.0

    def test_good_improvement_positive(self):
        b = Brain(model_type="hybrid")
        r = b.calculate_multi_objective_reward(0.8, True, True, False)
        assert r > 0

    def test_no_improvement_negative(self):
        b = Brain(model_type="hybrid")
        r = b.calculate_multi_objective_reward(-0.5, False, False, False)
        assert r < 0

    def test_result_always_in_range(self):
        b = Brain(model_type="hybrid")
        for imp in [-1.0, 0.0, 0.5, 1.0]:
            for comp in [True, False]:
                for eng in [True, False]:
                    for churn in [True, False]:
                        r = b.calculate_multi_objective_reward(imp, comp, eng, churn)
                        assert -1.0 <= r <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 13: CONTEXT VECTORS
# ═══════════════════════════════════════════════════════════════════════════════


class TestContextVector:
    def test_dimension_is_17(self):
        assert get_context_dimension() == 17

    def test_build_context_shape(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S0", "Alice", performance_score=0.7,
                          current_topic="Math")
        c = b.add_content("C0", "Algebra", "Math", 3, "video")
        ctx = build_context(s, c)
        assert ctx.shape == (17,)

    def test_build_context_split_shapes(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S0", "Alice")
        c = b.add_content("C0", "Algebra", "Math", 3, "video")
        z, x = build_context_split(s, c)
        assert z.shape == (8,)
        assert x.shape == (9,)

    def test_context_not_all_zeros(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S0", "Alice", performance_score=0.7,
                          current_topic="Math")
        c = b.add_content("C0", "Algebra", "Math", 3, "video")
        ctx = build_context(s, c)
        assert ctx.sum() > 0

    def test_context_changes_with_student(self):
        b = Brain(model_type="hybrid")
        s1 = b.add_student("S1", "Alice", performance_score=0.2)
        s2 = b.add_student("S2", "Bob", performance_score=0.9)
        c = b.add_content("C0", "Algebra", "Math", 3, "video")
        ctx1 = build_context(s1, c)
        ctx2 = build_context(s2, c)
        assert not np.array_equal(ctx1, ctx2)

    def test_context_changes_with_content(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S0", "Alice")
        c1 = b.add_content("C1", "Easy", "Math", 1, "video")
        c2 = b.add_content("C2", "Hard", "Math", 5, "quiz")
        ctx1 = build_context(s, c1)
        ctx2 = build_context(s, c2)
        assert not np.array_equal(ctx1, ctx2)

    def test_context_handles_missing_history(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S0", "Alice")
        c = b.add_content("C0", "Content", "Math", 3, "video")
        ctx = build_context(s, c)
        assert ctx.shape == (17,)
        assert ctx.sum() > 0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 14: MULTI-SCHOOL ISOLATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiSchoolIsolation:
    def test_students_independent(self):
        b = Brain(model_type="hybrid")
        b.add_student("S1", "Alice", school_id="SCHOOL_A")
        b.add_student("S2", "Bob", school_id="SCHOOL_B")
        c = b.add_content("C0", "Content", "Math", 3, "video")
        b.update("S1", "C0", 0.9)
        b.update("S2", "C0", 0.3)
        assert b.students["S1"].session_count == 1
        assert b.students["S2"].session_count == 1

    def test_recommendation_works_across_schools(self):
        b = Brain(model_type="hybrid")
        b.add_student("S1", "Alice", school_id="SCHOOL_A",
                      performance_score=0.8)
        b.add_student("S2", "Bob", school_id="SCHOOL_B",
                      performance_score=0.3)
        b.add_content("C0", "Content", "Math", 3, "video")
        assert b.recommend("S1") is not None
        assert b.recommend("S2") is not None


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 15: REWARD FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════


class TestRewardFunction:
    def test_churned_always_negative_one(self):
        assert calculate_reward(0.5, 0.5, False, 1.0, False, True) == -1.0

    def test_improvement_positive(self):
        r = calculate_reward(0.3, 0.8, True, 1.0, True, False)
        assert r > 0

    def test_decline_negative(self):
        r = calculate_reward(0.8, 0.3, False, 1.0, False, False)
        assert r < 0

    def test_no_change_slightly_negative(self):
        r = calculate_reward(0.5, 0.5, False, 1.0, False, False)
        assert r < 0

    def test_result_in_range(self):
        for b in [0.0, 0.5, 1.0]:
            for a in [0.0, 0.5, 1.0]:
                for comp in [True, False]:
                    for eng in [True, False]:
                        for churn in [True, False]:
                            r = calculate_reward(b, a, comp, 1.0, eng, churn)
                            assert -1.0 <= r <= 1.0

    def test_time_penalty_for_slowness(self):
        r_fast = calculate_reward(0.5, 0.6, True, 1.0, True, False)
        r_slow = calculate_reward(0.5, 0.6, True, 3.0, True, False)
        assert r_slow < r_fast


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 16: EDGE CASES & BOUNDARY CONDITIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_recommend_with_single_content(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Only", "Math", 3, "video")
        rec = b.recommend("S0")
        assert rec.content_id == "C0"

    def test_recommend_top_n_exceeds_content_count(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        recs = b.recommend("S0", top_n=100)
        assert len(recs) == 1

    def test_empty_student_name(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S0", "")
        assert s.name == ""

    def test_empty_content_title(self):
        b = Brain(model_type="hybrid")
        c = b.add_content("C0", "", "Math", 3, "video")
        assert c.title == ""

    def test_unicode_student_name(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S0", "Chidinma Okafor")
        assert s.name == "Chidinma Okafor"

    def test_many_updates_stability(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        for _ in range(50):
            b.update("S0", "C0", 0.7)
        assert b.update_count == 50
        assert b.students["S0"].session_count == 50

    def test_recommend_after_many_updates(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        for i in range(10):
            b.add_content(f"C{i}", f"Content {i}", "Math", 3, "video")
        for _ in range(20):
            rec = b.recommend("S0")
            b.update("S0", rec.content_id, 0.7)
        rec = b.recommend("S0")
        assert rec is not None

    def test_topic_normalization(self):
        assert normalize_label("math") == "MATH"
        assert normalize_label("  Science  ") == "SCIENCE"
        assert normalize_label("") == ""
        assert normalize_label("hello world") == "HELLO WORLD"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 17: CLUSTERING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


class TestClusteringEngine:
    def test_get_cluster_returns_int(self):
        ce = ClusteringEngine(n_clusters=5, n_features=17)
        cluster = ce.get_cluster("S0", np.random.rand(17))
        assert isinstance(cluster, int)

    def test_cluster_in_valid_range(self):
        ce = ClusteringEngine(n_clusters=5, n_features=17)
        for i in range(20):
            cluster = ce.get_cluster(f"S{i}", np.random.rand(17))
            assert 0 <= cluster < 5

    def test_same_student_same_cluster(self):
        ce = ClusteringEngine(n_clusters=5, n_features=17)
        vec = np.random.rand(17)
        c1 = ce.get_cluster("S0", vec)
        c2 = ce.get_cluster("S0", vec)
        assert c1 == c2


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 18: CONCURRENT ACCESS (THREAD SAFETY)
# ═══════════════════════════════════════════════════════════════════════════════


class TestThreadSafety:
    def test_concurrent_updates(self):
        import threading
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        errors = []

        def update_worker():
            try:
                for _ in range(10):
                    b.update("S0", "C0", 0.7)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=update_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert b.update_count == 50

    def test_concurrent_recommends(self):
        import threading
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        for i in range(5):
            b.add_content(f"C{i}", f"Content {i}", "Math", 3, "video")
        results = []
        errors = []

        def recommend_worker():
            try:
                rec = b.recommend("S0")
                results.append(rec.content_id)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=recommend_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(results) == 10


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 19: DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDiagnostics:
    def test_neural_score_has_all_dimensions(self):
        b = Brain(model_type="hybrid")
        for i in range(10):
            b.add_student(f"S{i}", f"Student {i}")
            b.add_content(f"C{i}", f"Content {i}", "Math", 3, "video")
            b.update(f"S{i}", f"C{i}", 0.5 + i * 0.05)
        scores = b.neural_score(verbose=False)
        expected = {"exploration_score", "convergence_score",
                    "context_score", "precision_score",
                    "grade_score", "neural_score"}
        assert expected.issubset(set(scores.keys()))

    def test_auto_diagnose_on_update(self):
        b = Brain(model_type="hybrid", auto_diagnose_every=5)
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        for _ in range(5):
            b.update("S0", "C0", 0.7)
        assert b.last_neural_score is not None


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 20: PILOT DATA INTEGRITY
# ═══════════════════════════════════════════════════════════════════════════════


class TestPilotDataIntegrity:
    def test_pilot_student_csv_has_101_rows(self):
        from ingest import read_data_file
        rows = read_data_file(str(PILOT_DIR / "pilot_students.csv"))
        assert len(rows) == 101

    def test_pilot_content_csv_has_40_rows(self):
        from ingest import read_data_file
        rows = read_data_file(str(PILOT_DIR / "pilot_content.csv"))
        assert len(rows) == 40

    def test_large_student_csv_has_56_rows(self):
        from ingest import read_data_file
        rows = read_data_file(str(LARGE_DIR / "large_students.csv"))
        assert len(rows) == 56

    def test_large_content_csv_has_24_rows(self):
        from ingest import read_data_file
        rows = read_data_file(str(LARGE_DIR / "large_content.csv"))
        assert len(rows) == 24
