"""
Comprehensive QA Test Suite — GradePulse Full App (v2)
=======================================================
Tests every public interface: API endpoints (with auth), Brain methods,
context vectors, triage, multi-school isolation, edge cases, data integrity.

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

# Clean stale lock files before importing app
for _lf in ["brain_state.json.lock", "class_config.json.lock",
            "oulad_brain_state.json.lock"]:
    _lp = os.path.join(os.getcwd(), _lf)
    if os.path.exists(_lp):
        os.remove(_lp)

os.environ.setdefault("BACKUP_ENABLED", "false")
os.environ.setdefault("BRAIN_STATE_PATH", "/tmp/qa_brain_state.json")
os.environ.setdefault("CONFIG_PATH", "/tmp/qa_class_config.json")

from fastapi.testclient import TestClient
from linucb_brain.api.app import app
from linucb_brain.brain import Brain
from linucb_brain.models.student import Student, normalize_label
from linucb_brain.models.content import Content
from linucb_brain.core.context import build_context, build_context_split, get_context_dimension, CONTENT_TYPES
from linucb_brain.core.reward import calculate_reward
from linucb_brain.core.clustering import ClusteringEngine

PILOT_DIR = Path(__file__).parent.parent / "sample_data" / "pilot_grade"
LARGE_DIR = Path(__file__).parent.parent / "sample_data" / "large"


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(client):
    email = f"qa_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/auth/signup", json={
        "email": email, "password": "QAPass123!", "school_name": "QA Test School"
    })
    assert r.status_code == 200, f"Signup failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def auth_h(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthSignup:
    def test_signup_returns_200(self, client):
        email = f"signup_{uuid.uuid4().hex[:6]}@test.com"
        r = client.post("/auth/signup", json={
            "email": email, "password": "pass123", "school_name": "School"
        })
        assert r.status_code == 200

    def test_signup_returns_token(self, client):
        email = f"signup_{uuid.uuid4().hex[:6]}@test.com"
        r = client.post("/auth/signup", json={
            "email": email, "password": "pass123"
        })
        assert "token" in r.json()
        assert len(r.json()["token"]) > 0

    def test_signup_returns_user_fields(self, client):
        email = f"signup_{uuid.uuid4().hex[:6]}@test.com"
        r = client.post("/auth/signup", json={
            "email": email, "password": "pass123", "school_name": "My School"
        })
        data = r.json()
        assert "id" in data
        assert data["email"] == email
        assert "school_id" in data
        assert data["school_name"] == "MY SCHOOL"

    def test_signup_duplicate_email_returns_400(self, client):
        email = f"dup_{uuid.uuid4().hex[:6]}@test.com"
        client.post("/auth/signup", json={"email": email, "password": "pass123"})
        r = client.post("/auth/signup", json={"email": email, "password": "pass123"})
        assert r.status_code == 400

    def test_signup_missing_email_returns_422(self, client):
        r = client.post("/auth/signup", json={"password": "pass123"})
        assert r.status_code == 422

    def test_signup_missing_password_returns_422(self, client):
        r = client.post("/auth/signup", json={"email": "x@test.com"})
        assert r.status_code == 422


class TestAuthLogin:
    def test_login_returns_200(self, client):
        email = f"login_{uuid.uuid4().hex[:6]}@test.com"
        client.post("/auth/signup", json={"email": email, "password": "pass123"})
        r = client.post("/auth/login", json={"email": email, "password": "pass123"})
        assert r.status_code == 200

    def test_login_returns_token(self, client):
        email = f"login_{uuid.uuid4().hex[:6]}@test.com"
        client.post("/auth/signup", json={"email": email, "password": "pass123"})
        r = client.post("/auth/login", json={"email": email, "password": "pass123"})
        assert "token" in r.json()

    def test_login_wrong_password_returns_401(self, client):
        email = f"login_{uuid.uuid4().hex[:6]}@test.com"
        client.post("/auth/signup", json={"email": email, "password": "pass123"})
        r = client.post("/auth/login", json={"email": email, "password": "wrong"})
        assert r.status_code == 401

    def test_login_nonexistent_returns_401(self, client):
        r = client.post("/auth/login", json={"email": "nope@test.com", "password": "x"})
        assert r.status_code == 401


class TestAuthMe:
    def test_me_returns_user(self, client, auth_h):
        r = client.get("/auth/me", headers=auth_h)
        assert r.status_code == 200
        assert "id" in r.json()
        assert "email" in r.json()

    def test_me_without_auth_returns_401(self, client):
        r = client.get("/auth/me")
        assert r.status_code == 401

    def test_me_invalid_token_returns_401(self, client):
        r = client.get("/auth/me", headers={"Authorization": "Bearer bad"})
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: ROOT ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


class TestRootEndpoint:
    def test_root_returns_200(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_root_has_status(self, client):
        assert client.get("/").json()["status"] == "alive"

    def test_root_has_engine(self, client):
        assert "engine" in client.get("/").json()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: SCHOOL CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchoolsAPI:
    def test_list_schools_returns_200(self, client, auth_h):
        r = client.get("/schools", headers=auth_h)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_schools_without_auth_returns_401(self, client):
        assert client.get("/schools").status_code == 401

    def test_create_school_returns_200(self, client, auth_h):
        r = client.post("/schools", headers=auth_h,
                        json={"name": f"QA School {uuid.uuid4().hex[:4]}"})
        assert r.status_code == 200
        assert "school_id" in r.json()

    def test_create_school_uppercases_name(self, client, auth_h):
        name = f"qa school {uuid.uuid4().hex[:4]}"
        r = client.post("/schools", headers=auth_h, json={"name": name})
        assert r.json()["name"] == name.upper()

    def _own_school_token(self, client):
        email = f"own_{uuid.uuid4().hex[:6]}@test.com"
        r = client.post("/auth/signup", json={
            "email": email, "password": "pass123",
            "school_name": f"Own {uuid.uuid4().hex[:4]}",
        })
        return r.json()["token"], r.json()["school_id"]

    def test_update_school_returns_200(self, client, auth_h):
        sid = client.get("/auth/me", headers=auth_h).json()["school_id"]
        r = client.put(f"/schools/{sid}", headers=auth_h,
                       json={"name": "Updated Name"})
        assert r.status_code == 200
        assert r.json()["name"] == "UPDATED NAME"

    def test_delete_school_returns_200(self, client, auth_h):
        own_token, sid = self._own_school_token(client)
        headers = {"Authorization": f"Bearer {own_token}"}
        r = client.delete(f"/schools/{sid}", headers=headers)
        assert r.status_code == 200

    def test_delete_nonexistent_returns_403(self, client, auth_h):
        # Phase 2: a school you don't own is indistinguishable from missing.
        assert client.delete("/schools/nope", headers=auth_h).status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: CLASS CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestClassesAPI:
    @pytest.fixture
    def school_id(self, client, auth_h):
        # Classes must be created under the caller's OWN school (Phase 2).
        return client.get("/auth/me", headers=auth_h).json()["school_id"]

    def test_list_classes_returns_200(self, client, auth_h, school_id):
        r = client.get(f"/classes/{school_id}", headers=auth_h)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_class_returns_200(self, client, auth_h, school_id):
        r = client.post(f"/classes/{school_id}", headers=auth_h,
                        json={"label": f"JSS1A_{uuid.uuid4().hex[:4]}"})
        assert r.status_code == 200
        assert "class_id" in r.json()

    def test_create_duplicate_class_returns_400(self, client, auth_h, school_id):
        label = f"DUP_{uuid.uuid4().hex[:4]}"
        client.post(f"/classes/{school_id}", headers=auth_h, json={"label": label})
        r = client.post(f"/classes/{school_id}", headers=auth_h, json={"label": label})
        assert r.status_code == 400

    def test_update_class_returns_200(self, client, auth_h, school_id):
        r = client.post(f"/classes/{school_id}", headers=auth_h,
                        json={"label": f"UPD_{uuid.uuid4().hex[:4]}"})
        cid = r.json()["class_id"]
        r = client.put(f"/classes/{school_id}/{cid}", headers=auth_h,
                       json={"label": "NEWLABEL"})
        assert r.status_code == 200
        assert r.json()["label"] == "NEWLABEL"

    def test_delete_class_returns_200(self, client, auth_h, school_id):
        r = client.post(f"/classes/{school_id}", headers=auth_h,
                        json={"label": f"DEL_{uuid.uuid4().hex[:4]}"})
        cid = r.json()["class_id"]
        r = client.delete(f"/classes/{school_id}/{cid}", headers=auth_h)
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: STUDENT CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestStudentsAPI:
    def test_list_students_returns_200(self, client, auth_h):
        r = client.get("/students", headers=auth_h)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_add_student_returns_200(self, client, auth_h):
        sid = f"QA_{uuid.uuid4().hex[:6]}"
        r = client.post("/students", headers=auth_h, json={
            "student_id": sid, "name": "QA Student", "performance_score": 0.75
        })
        assert r.status_code == 200

    def test_add_student_echoes_fields(self, client, auth_h):
        sid = f"QA_{uuid.uuid4().hex[:6]}"
        r = client.post("/students", headers=auth_h, json={
            "student_id": sid, "name": "Echo", "performance_score": 0.6,
            "current_topic": "Science", "grade_history": {"Math": [0.5, 0.6]}
        })
        data = r.json()
        assert data["student_id"] == sid
        assert data["name"] == "Echo"
        assert data["performance_score"] == 0.6

    def test_add_student_zero_performance(self, client, auth_h):
        sid = f"QA_ZERO_{uuid.uuid4().hex[:6]}"
        r = client.post("/students", headers=auth_h, json={
            "student_id": sid, "name": "Zero", "performance_score": 0.0
        })
        assert r.status_code == 200

    def test_add_student_max_performance(self, client, auth_h):
        sid = f"QA_MAX_{uuid.uuid4().hex[:6]}"
        r = client.post("/students", headers=auth_h, json={
            "student_id": sid, "name": "Max", "performance_score": 1.0
        })
        assert r.status_code == 200

    def test_update_student_returns_200(self, client, auth_h):
        sid = f"QA_UPD_{uuid.uuid4().hex[:6]}"
        client.post("/students", headers=auth_h,
                    json={"student_id": sid, "name": "Original"})
        r = client.put(f"/students/{sid}", headers=auth_h, json={"name": "Updated"})
        assert r.status_code == 200
        assert r.json()["name"] == "Updated"

    def test_update_nonexistent_returns_404(self, client, auth_h):
        r = client.put("/students/NOPE", headers=auth_h, json={"name": "X"})
        assert r.status_code == 404

    def test_delete_student_returns_200(self, client, auth_h):
        sid = f"QA_DEL_{uuid.uuid4().hex[:6]}"
        client.post("/students", headers=auth_h,
                    json={"student_id": sid, "name": "Delete Me"})
        r = client.delete(f"/students/{sid}", headers=auth_h)
        assert r.status_code == 200

    def test_delete_nonexistent_returns_404(self, client, auth_h):
        assert client.delete("/students/NOPE", headers=auth_h).status_code == 404

    def test_without_auth_returns_401(self, client):
        assert client.post("/students", json={"student_id": "X", "name": "X"}).status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: CONTENT API
# ═══════════════════════════════════════════════════════════════════════════════


class TestContentAPI:
    def test_add_content_returns_200(self, client, auth_h):
        cid = f"QAC_{uuid.uuid4().hex[:6]}"
        r = client.post("/content", headers=auth_h, json={
            "content_id": cid, "title": "QA Content", "topic": "Math",
            "difficulty": 3, "content_type": "video"
        })
        assert r.status_code == 200

    def test_add_content_echoes_fields(self, client, auth_h):
        cid = f"QAC_{uuid.uuid4().hex[:6]}"
        r = client.post("/content", headers=auth_h, json={
            "content_id": cid, "title": "Echo Content", "topic": "Science",
            "difficulty": 5, "content_type": "quiz"
        })
        data = r.json()
        assert data["content_id"] == cid
        assert data["difficulty"] == 5

    def test_difficulty_too_low_returns_422(self, client, auth_h):
        r = client.post("/content", headers=auth_h, json={
            "content_id": "X", "title": "X", "topic": "X",
            "difficulty": 0, "content_type": "video"
        })
        assert r.status_code == 422

    def test_difficulty_too_high_returns_422(self, client, auth_h):
        r = client.post("/content", headers=auth_h, json={
            "content_id": "X", "title": "X", "topic": "X",
            "difficulty": 6, "content_type": "video"
        })
        assert r.status_code == 422

    def test_valid_difficulty_range(self, client, auth_h):
        for d in [1, 2, 3, 4, 5]:
            cid = f"DIFF{d}_{uuid.uuid4().hex[:4]}"
            r = client.post("/content", headers=auth_h, json={
                "content_id": cid, "title": f"Diff {d}", "topic": "Math",
                "difficulty": d, "content_type": "video"
            })
            assert r.status_code == 200

    def test_without_auth_returns_401(self, client):
        assert client.post("/content", json={
            "content_id": "X", "title": "X", "topic": "X",
            "difficulty": 3, "content_type": "video"
        }).status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: RECOMMEND API
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecommendAPI:
    @pytest.fixture(autouse=True)
    def _setup(self, client, auth_h):
        self.c = client
        self.h = auth_h
        self.sid = f"QAREC_{uuid.uuid4().hex[:6]}"
        self.cid = f"QAREC_C_{uuid.uuid4().hex[:6]}"
        client.post("/students", headers=auth_h, json={
            "student_id": self.sid, "name": "Rec Student", "current_topic": "Math"
        })
        client.post("/content", headers=auth_h, json={
            "content_id": self.cid, "title": "Rec Content",
            "topic": "Math", "difficulty": 3, "content_type": "video"
        })

    def test_recommend_returns_200(self):
        r = self.c.post("/recommend", headers=self.h,
                        json={"student_id": self.sid})
        assert r.status_code == 200

    def test_recommend_returns_content_id(self):
        data = self.c.post("/recommend", headers=self.h,
                           json={"student_id": self.sid}).json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert "content_id" in data[0]

    def test_recommend_single_always_list(self):
        for _ in range(3):
            self.c.post("/content", headers=self.h, json={
                "content_id": f"{self.cid}_x", "title": "X",
                "topic": "Math", "difficulty": 3, "content_type": "video"
            })
        r = self.c.post("/recommend", headers=self.h,
                        json={"student_id": self.sid, "top_n": 1})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert "content_id" in data[0]

    def test_recommend_top_n_3_returns_list(self):
        for i in range(3):
            self.c.post("/content", headers=self.h, json={
                "content_id": f"{self.cid}_{i}", "title": f"M{i}",
                "topic": "Math", "difficulty": 3, "content_type": "video"
            })
        r = self.c.post("/recommend", headers=self.h,
                        json={"student_id": self.sid, "top_n": 3})
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) == 3

    def test_recommend_nonexistent_student_returns_400(self):
        r = self.c.post("/recommend", headers=self.h,
                        json={"student_id": "DOES_NOT_EXIST"})
        assert r.status_code == 400

    def test_recommend_with_topic_filter(self):
        self.c.post("/content", headers=self.h, json={
            "content_id": f"{self.cid}_sci", "title": "Science",
            "topic": "Science", "difficulty": 3, "content_type": "video"
        })
        r = self.c.post("/recommend", headers=self.h,
                        json={"student_id": self.sid, "topic": "Math", "top_n": 1})
        assert r.status_code == 200

    def test_recommend_without_auth_returns_401(self):
        assert self.c.post("/recommend", json={"student_id": "X"}).status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8: UPDATE API
# ═══════════════════════════════════════════════════════════════════════════════


class TestUpdateAPI:
    @pytest.fixture(autouse=True)
    def _setup(self, client, auth_h):
        self.c = client
        self.h = auth_h
        self.sid = f"QAUPD_{uuid.uuid4().hex[:6]}"
        self.cid = f"QAUPD_C_{uuid.uuid4().hex[:6]}"
        client.post("/students", headers=auth_h,
                    json={"student_id": self.sid, "name": "Upd Student"})
        client.post("/content", headers=auth_h, json={
            "content_id": self.cid, "title": "Upd Content",
            "topic": "Math", "difficulty": 3, "content_type": "video"
        })

    def test_update_returns_200(self):
        r = self.c.post("/update", headers=self.h, json={
            "student_id": self.sid, "content_id": self.cid, "reward": 0.7
        })
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_update_nonexistent_student_returns_404(self):
        r = self.c.post("/update", headers=self.h, json={
            "student_id": "DOES_NOT_EXIST", "content_id": self.cid, "reward": 0.5
        })
        assert r.status_code == 404

    def test_update_nonexistent_content_returns_404(self):
        r = self.c.post("/update", headers=self.h, json={
            "student_id": self.sid, "content_id": "DOES_NOT_EXIST", "reward": 0.5
        })
        assert r.status_code == 404

    def test_update_negative_reward_accepted(self):
        r = self.c.post("/update", headers=self.h, json={
            "student_id": self.sid, "content_id": self.cid, "reward": -0.5
        })
        assert r.status_code == 200

    def test_update_reward_boundary_minus_1(self):
        r = self.c.post("/update", headers=self.h, json={
            "student_id": self.sid, "content_id": self.cid, "reward": -1.0
        })
        assert r.status_code == 200

    def test_update_reward_boundary_plus_1(self):
        r = self.c.post("/update", headers=self.h, json={
            "student_id": self.sid, "content_id": self.cid, "reward": 1.0
        })
        assert r.status_code == 200

    def test_update_reward_out_of_range_returns_422(self):
        r = self.c.post("/update", headers=self.h, json={
            "student_id": self.sid, "content_id": self.cid, "reward": 1.5
        })
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9: CALCULATE REWARD, SUMMARY, SAVE, TRIAGE, BULK UPDATE
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalculateRewardAPI:
    def test_reward_positive(self, client, auth_h):
        r = client.post("/calculate-reward", headers=auth_h, json={
            "before_score": 0.5, "after_score": 0.7, "completed": True,
            "time_spent_ratio": 1.0, "engaged": True, "churned": False
        })
        assert r.status_code == 200
        assert r.json()["reward"] > 0

    def test_reward_churned(self, client, auth_h):
        r = client.post("/calculate-reward", headers=auth_h, json={
            "before_score": 0.5, "after_score": 0.5, "completed": False,
            "time_spent_ratio": 1.0, "engaged": False, "churned": True
        })
        assert r.status_code == 200
        assert r.json()["reward"] == -1.0

    def test_without_auth_returns_401(self, client):
        assert client.post("/calculate-reward", json={
            "before_score": 0.5, "after_score": 0.7, "completed": True,
            "time_spent_ratio": 1.0, "engaged": True, "churned": False
        }).status_code == 401


class TestSummaryAPI:
    def test_summary_returns_200(self, client, auth_h):
        assert client.get("/summary", headers=auth_h).status_code == 200

    def test_summary_has_fields(self, client, auth_h):
        data = client.get("/summary", headers=auth_h).json()
        for f in ["student_count", "content_count", "total_sessions",
                   "model_type", "current_alpha", "current_gamma"]:
            assert f in data

    def test_summary_non_negative(self, client, auth_h):
        data = client.get("/summary", headers=auth_h).json()
        assert data["student_count"] >= 0

    def test_without_auth_returns_401(self, client):
        assert client.get("/summary").status_code == 401


class TestSaveAPI:
    def test_save_returns_200(self, client, auth_h):
        r = client.post("/save", headers=auth_h)
        assert r.status_code == 200
        assert r.json()["status"] == "saved"

    def test_without_auth_returns_401(self, client):
        assert client.post("/save").status_code == 401


class TestTriageAPI:
    def test_triage_returns_200(self, client, auth_h):
        r = client.post("/triage", headers=auth_h, json={"subject": "MATH"})
        assert r.status_code == 200
        assert "tiers" in r.json()

    def test_without_auth_returns_401(self, client):
        assert client.post("/triage", json={"subject": "MATH"}).status_code == 401


class TestBulkUpdateAPI:
    def test_bulk_update_returns_200(self, client, auth_h):
        r = client.post("/bulk-update", headers=auth_h, json={
            "entries": [{"student_id": "608041", "subject": "Math", "score": 0.8}]
        })
        assert r.status_code == 200

    def test_without_auth_returns_401(self, client):
        assert client.post("/bulk-update", json={"entries": []}).status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10: BRAIN METHODS (direct, no API)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBrainAddStudent:
    def test_add_student(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S1", "Alice")
        assert s.student_id == "S1" and "S1" in b.students

    def test_add_duplicate_returns_existing(self):
        b = Brain(model_type="hybrid")
        s1 = b.add_student("S1", "Alice")
        s2 = b.add_student("S1", "Bob")
        assert s1 is s2 and s2.name == "Alice"

    def test_add_with_kwargs(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S1", "Alice", performance_score=0.9, current_topic="Math")
        assert s.performance_score == 0.9 and s.current_topic == "Math"


class TestBrainAddContent:
    def test_add_content(self):
        b = Brain(model_type="hybrid")
        c = b.add_content("C1", "Algebra", "Math", 3, "video")
        assert c.content_id == "C1" and "C1" in b.contents

    def test_add_duplicate_returns_existing(self):
        b = Brain(model_type="hybrid")
        c1 = b.add_content("C1", "Algebra", "Math", 3, "video")
        c2 = b.add_content("C1", "Different", "Math", 3, "video")
        assert c1 is c2 and c2.title == "Algebra"


class TestBrainRecommend:
    @pytest.fixture
    def brain(self):
        b = Brain(model_type="hybrid")
        for i in range(5):
            b.add_student(f"S{i}", f"Student {i}", performance_score=0.3 + i * 0.15)
            b.add_content(f"C{i}", f"Content {i}", "Math", 2 + i % 4, "video")
        return b

    def test_returns_content(self, brain):
        rec = brain.recommend("S0")
        assert isinstance(rec, Content) and rec.content_id in brain.contents

    def test_top_n(self, brain):
        recs = brain.recommend("S0", top_n=3)
        assert isinstance(recs, list) and len(recs) == 3

    def test_nonexistent_student_raises(self, brain):
        with pytest.raises(KeyError):
            brain.recommend("DOES_NOT_EXIST")

    def test_topic_filter(self, brain):
        brain.add_content("CSCI", "Science", "Science", 3, "quiz")
        rec = brain.recommend("S0", topic="Science")
        assert rec is not None

    def test_no_matching_topic_raises(self, brain):
        with pytest.raises(ValueError):
            brain.recommend("S0", topic="NONEXISTENT")


class TestBrainUpdate:
    @pytest.fixture
    def brain(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Student 0", performance_score=0.5)
        b.add_content("C0", "Content 0", "Math", 3, "video")
        return b

    def test_increments_update_count(self, brain):
        before = brain.update_count
        brain.update("S0", "C0", 0.7)
        assert brain.update_count == before + 1

    def test_increments_student_session_count(self, brain):
        before = brain.students["S0"].session_count
        brain.update("S0", "C0", 0.7)
        assert brain.students["S0"].session_count == before + 1

    def test_records_session(self, brain):
        before = len(brain.sessions)
        brain.update("S0", "C0", 0.7)
        assert len(brain.sessions) == before + 1

    def test_updates_content_avg_reward(self, brain):
        brain.update("S0", "C0", 0.8)
        assert brain.contents["C0"].avg_reward == 0.8

    def test_adds_to_grade_history(self, brain):
        brain.update("S0", "C0", 0.9)
        assert "Math" in brain.students["S0"].grade_history

    def test_nonexistent_student_raises(self, brain):
        with pytest.raises(KeyError):
            brain.update("DOES_NOT_EXIST", "C0", 0.5)

    def test_nonexistent_content_raises(self, brain):
        with pytest.raises(KeyError):
            brain.update("S0", "DOES_NOT_EXIST", 0.5)


class TestBrainPredictGrade:
    def test_with_history(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice", grade_history={"Math": [0.6, 0.8, 0.7]})
        assert abs(b.predict_grade("S0", "Math") - 0.7) < 0.001

    def test_without_history(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice", performance_score=0.65)
        assert abs(b.predict_grade("S0", "Math") - 0.65) < 0.001

    def test_nonexistent_raises(self):
        with pytest.raises(KeyError):
            Brain(model_type="hybrid").predict_grade("X", "Math")


class TestBrainTriage:
    @pytest.fixture
    def brain(self):
        b = Brain(model_type="hybrid")
        for i, (name, perf) in enumerate([("Low", 0.2), ("Mid", 0.6), ("High", 0.9)]):
            b.add_student(f"S{i}", name, performance_score=perf)
            b.add_content(f"C{i}", f"Content {i}", "Math", 3, "video")
            b.update(f"S{i}", f"C{i}", perf)
        return b

    def test_returns_all_tiers(self, brain):
        result = brain.triage("MATH")
        for t in ["remediation", "on_track", "ahead"]:
            assert t in result["tiers"]

    def test_empty_subject(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        assert b.triage("NONEXISTENT")["total_students"] == 0

    def test_counts_match(self, brain):
        result = brain.triage("MATH")
        total = sum(t["count"] for t in result["tiers"].values())
        assert total == result["total_students"]


class TestBrainBulkUpdate:
    def test_bulk_update(self):
        b = Brain(model_type="hybrid")
        for i in range(5):
            b.add_student(f"S{i}", f"Student {i}")
            b.add_content(f"C{i}", f"Content {i}", "Math", 3, "video")
        result = b.bulk_update([
            {"student_id": "S0", "content_id": "C0", "reward": 0.8},
            {"student_id": "S1", "content_id": "C1", "reward": 0.6},
        ])
        assert result["processed"] == 2 and result["avg_reward"] > 0

    def test_empty_list(self):
        result = Brain(model_type="hybrid").bulk_update([])
        assert result["processed"] == 0

    def test_skips_missing_student_id(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        result = b.bulk_update([
            {"student_id": "S0", "content_id": "C0", "reward": 0.8},
            {},
        ])
        assert result["processed"] == 1


class TestBrainWarmStart:
    def test_warm_start(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        b.warm_start([{"student_id": "S0", "content_id": "C0", "reward": 0.8}])
        assert b.update_count == 1

    def test_skips_unknown(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        b.warm_start([
            {"student_id": "S0", "content_id": "C0", "reward": 0.8},
            {"student_id": "UNKNOWN", "content_id": "C0", "reward": 0.5},
        ])
        assert b.update_count == 1


class TestBrainNeuralScore:
    def test_returns_dict(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        b.update("S0", "C0", 0.7)
        scores = b.neural_score(verbose=False)
        assert isinstance(scores, dict) and "neural_score" in scores

    def test_in_range(self):
        b = Brain(model_type="hybrid")
        for i in range(10):
            b.add_student(f"S{i}", f"Student {i}")
            b.add_content(f"C{i}", f"Content {i}", "Math", 3, "video")
            b.update(f"S{i}", f"C{i}", 0.5 + i * 0.05)
        for k, v in b.neural_score(verbose=False).items():
            assert 0 <= v <= 10, f"{k} = {v}"


class TestBrainSummary:
    def test_returns_dict(self):
        b = Brain(model_type="hybrid")
        s = b.summary()
        assert isinstance(s, dict) and "student_count" in s

    def test_matches_state(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        s = b.summary()
        assert s["student_count"] == 1 and s["content_count"] == 1


class TestBrainSaveLoad:
    def test_save_and_load(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice", performance_score=0.8)
        b.add_content("C0", "Content", "Math", 3, "video")
        b.update("S0", "C0", 0.7)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "brain.json")
            b.save(path)
            loaded = Brain.load(path)
            assert len(loaded.students) == 1
            assert loaded.students["S0"].name == "Alice"
            assert loaded.update_count == 1

    def test_loaded_can_recommend(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        with tempfile.TemporaryDirectory() as d:
            b.save(os.path.join(d, "brain.json"))
            loaded = Brain.load(os.path.join(d, "brain.json"))
            assert loaded.recommend("S0") is not None


class TestBrainExportTeacherData:
    def test_export(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice", grade_history={"Math": [0.7, 0.8]})
        b.add_content("C0", "Content", "Math", 3, "video")
        data = b.export_teacher_data()
        assert "students" in data and "subjects" in data


class TestBrainMultiObjectiveReward:
    def test_churned(self):
        assert Brain(model_type="hybrid").calculate_multi_objective_reward(
            0.5, True, True, True) == -1.0

    def test_good_improvement(self):
        assert Brain(model_type="hybrid").calculate_multi_objective_reward(
            0.8, True, True, False) > 0

    def test_no_improvement(self):
        assert Brain(model_type="hybrid").calculate_multi_objective_reward(
            -0.5, False, False, False) < 0

    def test_always_in_range(self):
        b = Brain(model_type="hybrid")
        for imp in [-1.0, 0.0, 0.5, 1.0]:
            for comp in [True, False]:
                for eng in [True, False]:
                    for churn in [True, False]:
                        r = b.calculate_multi_objective_reward(imp, comp, eng, churn)
                        assert -1.0 <= r <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11: CONTEXT VECTORS
# ═══════════════════════════════════════════════════════════════════════════════


class TestContextVector:
    def test_dimension_is_17(self):
        assert get_context_dimension() == 17

    def test_build_context_shape(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S0", "Alice", performance_score=0.7, current_topic="Math")
        c = b.add_content("C0", "Algebra", "Math", 3, "video")
        assert build_context(s, c).shape == (17,)

    def test_split_shapes(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S0", "Alice")
        c = b.add_content("C0", "Algebra", "Math", 3, "video")
        z, x = build_context_split(s, c)
        assert z.shape == (8,) and x.shape == (9,)

    def test_not_all_zeros(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S0", "Alice", performance_score=0.7, current_topic="Math")
        c = b.add_content("C0", "Algebra", "Math", 3, "video")
        assert build_context(s, c).sum() > 0

    def test_changes_with_student(self):
        b = Brain(model_type="hybrid")
        s1 = b.add_student("S1", "Alice", performance_score=0.2)
        s2 = b.add_student("S2", "Bob", performance_score=0.9)
        c = b.add_content("C0", "Algebra", "Math", 3, "video")
        assert not np.array_equal(build_context(s1, c), build_context(s2, c))

    def test_changes_with_content(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S0", "Alice")
        c1 = b.add_content("C1", "Easy", "Math", 1, "video")
        c2 = b.add_content("C2", "Hard", "Math", 5, "quiz")
        assert not np.array_equal(build_context(s, c1), build_context(s, c2))

    def test_handles_missing_history(self):
        b = Brain(model_type="hybrid")
        s = b.add_student("S0", "Alice")
        c = b.add_content("C0", "Content", "Math", 3, "video")
        ctx = build_context(s, c)
        assert ctx.shape == (17,) and ctx.sum() > 0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 12: REWARD FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════


class TestRewardFunction:
    def test_churned(self):
        assert calculate_reward(0.5, 0.5, False, 1.0, False, True) == -1.0

    def test_improvement_positive(self):
        assert calculate_reward(0.3, 0.8, True, 1.0, True, False) > 0

    def test_decline_negative(self):
        assert calculate_reward(0.8, 0.3, False, 1.0, False, False) < 0

    def test_in_range(self):
        for b in [0.0, 0.5, 1.0]:
            for a in [0.0, 0.5, 1.0]:
                for comp in [True, False]:
                    for eng in [True, False]:
                        for churn in [True, False]:
                            assert -1.0 <= calculate_reward(b, a, comp, 1.0, eng, churn) <= 1.0

    def test_time_penalty(self):
        r_fast = calculate_reward(0.5, 0.6, True, 1.0, True, False)
        r_slow = calculate_reward(0.5, 0.6, True, 3.0, True, False)
        assert r_slow < r_fast


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 13: EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_single_content(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Only", "Math", 3, "video")
        assert b.recommend("S0").content_id == "C0"

    def test_top_n_exceeds_count(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        assert len(b.recommend("S0", top_n=100)) == 1

    def test_unicode_name(self):
        b = Brain(model_type="hybrid")
        assert b.add_student("S0", "Chidinma Okafor").name == "Chidinma Okafor"

    def test_many_updates(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        for _ in range(50):
            b.update("S0", "C0", 0.7)
        assert b.update_count == 50

    def test_recommend_after_updates(self):
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        for i in range(10):
            b.add_content(f"C{i}", f"Content {i}", "Math", 3, "video")
        for _ in range(20):
            rec = b.recommend("S0")
            b.update("S0", rec.content_id, 0.7)
        assert b.recommend("S0") is not None

    def test_topic_normalization(self):
        assert normalize_label("math") == "MATH"
        assert normalize_label("  Science  ") == "SCIENCE"
        assert normalize_label("") == ""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 14: CLUSTERING, THREAD SAFETY, DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════════════════════


class TestClusteringEngine:
    def test_returns_int(self):
        assert isinstance(ClusteringEngine(5, 17).get_cluster("S0", np.random.rand(17)), int)

    def test_in_range(self):
        ce = ClusteringEngine(5, 17)
        for i in range(20):
            assert 0 <= ce.get_cluster(f"S{i}", np.random.rand(17)) < 5

    def test_same_same(self):
        ce = ClusteringEngine(5, 17)
        v = np.random.rand(17)
        assert ce.get_cluster("S0", v) == ce.get_cluster("S0", v)


class TestThreadSafety:
    def test_concurrent_updates(self):
        import threading
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        errors = []

        def worker():
            try:
                for _ in range(10):
                    b.update("S0", "C0", 0.7)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        assert len(errors) == 0 and b.update_count == 50

    def test_concurrent_recommends(self):
        import threading
        b = Brain(model_type="hybrid")
        b.add_student("S0", "Alice")
        for i in range(5):
            b.add_content(f"C{i}", f"Content {i}", "Math", 3, "video")
        results, errors = [], []

        def worker():
            try:
                results.append(b.recommend("S0").content_id)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()
        assert len(errors) == 0 and len(results) == 10


class TestDiagnostics:
    def test_has_all_dimensions(self):
        b = Brain(model_type="hybrid")
        for i in range(10):
            b.add_student(f"S{i}", f"Student {i}")
            b.add_content(f"C{i}", f"Content {i}", "Math", 3, "video")
            b.update(f"S{i}", f"C{i}", 0.5 + i * 0.05)
        scores = b.neural_score(verbose=False)
        assert {"exploration_score", "convergence_score", "context_score",
                "precision_score", "grade_score", "neural_score"}.issubset(scores.keys())

    def test_auto_diagnose(self):
        b = Brain(model_type="hybrid", auto_diagnose_every=5)
        b.add_student("S0", "Alice")
        b.add_content("C0", "Content", "Math", 3, "video")
        for _ in range(5):
            b.update("S0", "C0", 0.7)
        assert b.last_neural_score is not None


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 15: PILOT DATA INTEGRITY
# ═══════════════════════════════════════════════════════════════════════════════


class TestPilotDataIntegrity:
    def test_pilot_students_101(self):
        from ingest import read_data_file
        assert len(read_data_file(str(PILOT_DIR / "pilot_students.csv"))) == 101

    def test_pilot_content_40(self):
        from ingest import read_data_file
        assert len(read_data_file(str(PILOT_DIR / "pilot_content.csv"))) == 40

    def test_large_students_56(self):
        from ingest import read_data_file
        assert len(read_data_file(str(LARGE_DIR / "large_students.csv"))) == 56

    def test_large_content_24(self):
        from ingest import read_data_file
        assert len(read_data_file(str(LARGE_DIR / "large_content.csv"))) == 24
