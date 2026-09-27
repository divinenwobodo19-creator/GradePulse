"""
API Integration Tests for GradePulse API
Uses FastAPI's TestClient to test all endpoints with JWT auth.
"""
import os
import uuid
from fastapi.testclient import TestClient

# Clean stale lock files
for _lf in ["brain_state.json.lock", "class_config.json.lock"]:
    _lp = os.path.join(os.getcwd(), _lf)
    if os.path.exists(_lp):
        os.remove(_lp)

os.environ.setdefault("BACKUP_ENABLED", "false")
os.environ.setdefault("BRAIN_STATE_PATH", "/tmp/test_api_brain.json")
os.environ.setdefault("CONFIG_PATH", "/tmp/test_api_config.json")

from linucb_brain.api.app import app

TEST_EMAIL = f"apitest_{uuid.uuid4().hex[:8]}@test.com"
TEST_PASSWORD = "TestPass123!"


def _get_token(client):
    r = client.post("/auth/signup", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD, "school_name": "API Test School"
    })
    if r.status_code == 200:
        return r.json()["token"]
    r = client.post("/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    return r.json()["token"]


def test_read_root():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "alive"
        assert "engine" in data


def test_get_summary():
    with TestClient(app) as client:
        token = _get_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/summary", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "student_count" in data
        assert "content_count" in data
        assert "total_sessions" in data
        assert "model_type" in data


def test_add_student():
    with TestClient(app) as client:
        token = _get_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        sid = f"api_{uuid.uuid4().hex[:6]}"
        student_data = {
            "student_id": sid,
            "name": "Test Student One",
            "performance_score": 0.7,
            "grade_history": {"Math": [0.6, 0.7, 0.8]},
            "current_topic": "Algebra",
            "metadata": {"notes": "Test student"}
        }
        response = client.post("/students", json=student_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["student_id"] == sid


def test_add_content():
    with TestClient(app) as client:
        token = _get_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        cid = f"api_c_{uuid.uuid4().hex[:6]}"
        content_data = {
            "content_id": cid,
            "title": "Test Video Lesson",
            "topic": "Algebra",
            "difficulty": 3,
            "content_type": "video"
        }
        response = client.post("/content", json=content_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["content_id"] == cid


def test_recommendation_endpoint():
    with TestClient(app) as client:
        token = _get_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        sid = f"api_rec_{uuid.uuid4().hex[:6]}"
        cid = f"api_rec_c_{uuid.uuid4().hex[:6]}"
        client.post("/students", json={
            "student_id": sid, "name": "Rec Student", "current_topic": "Math"
        }, headers=headers)
        client.post("/content", json={
            "content_id": cid, "title": "Rec Content",
            "topic": "Math", "difficulty": 3, "content_type": "video"
        }, headers=headers)
        response = client.post("/recommend", json={
            "student_id": sid, "top_n": 1
        }, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert "content_id" in data[0]
        assert "times_recommended" in data[0]
        assert data[0]["times_recommended"] >= 1


def test_calculate_reward_endpoint():
    with TestClient(app) as client:
        token = _get_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        request_data = {
            "before_score": 0.5,
            "after_score": 0.7,
            "completed": True,
            "time_spent_ratio": 1.0,
            "engaged": True,
            "churned": False
        }
        response = client.post("/calculate-reward", json=request_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "reward" in data
        assert isinstance(data["reward"], float)


if __name__ == "__main__":
    print("=== Running API Integration Tests ===\n")

    print("Test 1: Root endpoint")
    test_read_root()
    print("✅ Passed\n")

    print("Test 2: Summary endpoint")
    test_get_summary()
    print("✅ Passed\n")

    print("Test 3: Calculate reward endpoint")
    test_calculate_reward_endpoint()
    print("✅ Passed\n")

    print("Test 4: Add student endpoint")
    test_add_student()
    print("✅ Passed\n")

    print("Test 5: Add content endpoint")
    test_add_content()
    print("✅ Passed\n")

    print("Test 6: Recommendation endpoint")
    test_recommendation_endpoint()
    print("✅ Passed\n")

    print("=== All API Integration Tests PASSED! ✅ ===")
