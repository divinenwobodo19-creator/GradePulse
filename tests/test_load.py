"""
Load tests for GradePulse API.
Tests concurrent access, data integrity under load, and response times.

Usage:
    1. Start the API: PYTHONPATH=. uvicorn linucb_brain.api.app:app --host 0.0.0.0 --port 8000
    2. Run tests: PYTHONPATH=. python -m pytest tests/test_load.py -v

These tests require a running API server. They are skipped if the server is unreachable.
"""
import os
import time
import threading
import statistics
import pytest
import requests

BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")
TEST_EMAIL = "loadtest@gradepulse.com"
TEST_PASSWORD = "loadtest123"

# ── Helpers ────────────────────────────────────────────────────────────────────

def _api_available():
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=2)
        return r.status_code == 200
    except requests.ConnectionError:
        return False


def _get_token():
    resp = requests.post(f"{BASE_URL}/auth/signup", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD, "school_name": "Load Test School"
    })
    if resp.status_code == 200:
        return resp.json()["token"]
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD
    })
    return resp.json()["token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _seed_students(token, count=10):
    students = []
    for i in range(count):
        sid = f"LOADStudent{i:04d}"
        resp = requests.post(f"{BASE_URL}/students", json={
            "student_id": sid, "name": f"Student {i}",
            "performance_score": 0.3 + (i % 7) * 0.1,
            "current_topic": ["Math", "Science", "English", "History"][i % 4],
        }, headers=_headers(token))
        if resp.status_code == 200:
            students.append(sid)
    return students


def _seed_content(token, count=8):
    content = []
    topics = ["Math", "Science", "English", "History"]
    types = ["video", "quiz", "exercise", "reading"]
    for i in range(count):
        cid = f"LOADContent{i:04d}"
        resp = requests.post(f"{BASE_URL}/content", json={
            "content_id": cid, "title": f"Content {i}",
            "topic": topics[i % 4], "difficulty": (i % 5) + 1,
            "content_type": types[i % 4],
        }, headers=_headers(token))
        if resp.status_code == 200:
            content.append(cid)
    return content


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def api_ready():
    if not _api_available():
        pytest.skip("API server not running — start with: PYTHONPATH=. uvicorn linucb_brain.api.app:app --port 8000")


@pytest.fixture(scope="module")
def token(api_ready):
    return _get_token()


@pytest.fixture(scope="module")
def seeded_data(token):
    students = _seed_students(token, 10)
    content = _seed_content(token, 8)
    return {"students": students, "content": content}


# ── Test: Concurrent Recommendations ──────────────────────────────────────────

class TestConcurrentRecommendations:
    def test_concurrent_recommend_no_errors(self, token, seeded_data):
        students = seeded_data["students"]
        errors = []
        latencies = []

        def worker(sid):
            start = time.time()
            resp = requests.post(f"{BASE_URL}/recommend", json={
                "student_id": sid, "top_n": 3
            }, headers=_headers(token))
            latencies.append(time.time() - start)
            if resp.status_code != 200:
                errors.append(f"{sid}: {resp.status_code}")

        threads = [threading.Thread(target=worker, args=(sid,)) for sid in students]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Errors: {errors}"
        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        print(f"\n  Recommend latency — p50: {p50:.3f}s, p95: {p95:.3f}s, max: {max(latencies):.3f}s")

    def test_concurrent_recommend_same_student(self, token, seeded_data):
        sid = seeded_data["students"][0]
        errors = []

        def worker():
            resp = requests.post(f"{BASE_URL}/recommend", json={
                "student_id": sid, "top_n": 1
            }, headers=_headers(token))
            if resp.status_code != 200:
                errors.append(resp.status_code)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Errors: {errors}"


# ── Test: Concurrent Bulk Updates ─────────────────────────────────────────────

class TestConcurrentBulkUpdates:
    def test_concurrent_bulk_update_data_integrity(self, token, seeded_data):
        students = seeded_data["students"]
        results = []
        lock = threading.Lock()

        def worker(batch_id, student_subset):
            entries = [
                {"student_id": sid, "subject": "Math", "score": 0.5 + batch_id * 0.05}
                for sid in student_subset
            ]
            start = time.time()
            resp = requests.post(f"{BASE_URL}/bulk-update", json={
                "entries": entries
            }, headers=_headers(token))
            latency = time.time() - start
            with lock:
                results.append({
                    "batch": batch_id,
                    "status": resp.status_code,
                    "latency": latency,
                    "processed": resp.json().get("processed", 0) if resp.status_code == 200 else 0,
                })

        batch_size = 3
        threads = []
        for i in range(0, len(students), batch_size):
            subset = students[i:i + batch_size]
            threads.append(threading.Thread(target=worker, args=(i // batch_size, subset)))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        errors = [r for r in results if r["status"] != 200]
        assert len(errors) == 0, f"Bulk update errors: {errors}"

        total_processed = sum(r["processed"] for r in results)
        assert total_processed == len(students), f"Expected {len(students)} processed, got {total_processed}"

        latencies = [r["latency"] for r in results]
        print(f"\n  Bulk-update latency — p50: {statistics.median(latencies):.3f}s, max: {max(latencies):.3f}s")


# ── Test: Concurrent Read/Write Mix ───────────────────────────────────────────

class TestConcurrentReadWrite:
    def test_mixed_read_write_load(self, token, seeded_data):
        students = seeded_data["students"]
        content = seeded_data["content"]
        errors = []
        lock = threading.Lock()

        def reader():
            resp = requests.get(f"{BASE_URL}/students", headers=_headers(token))
            with lock:
                if resp.status_code != 200:
                    errors.append(f"read: {resp.status_code}")

        def writer(batch_id):
            sid = students[batch_id % len(students)]
            cid = content[batch_id % len(content)]
            resp = requests.post(f"{BASE_URL}/update", json={
                "student_id": sid, "content_id": cid, "reward": 0.6
            }, headers=_headers(token))
            with lock:
                if resp.status_code != 200:
                    errors.append(f"write-{batch_id}: {resp.status_code}")

        def recommender():
            sid = students[0]
            resp = requests.post(f"{BASE_URL}/recommend", json={
                "student_id": sid, "top_n": 2
            }, headers=_headers(token))
            with lock:
                if resp.status_code != 200:
                    errors.append(f"recommend: {resp.status_code}")

        threads = []
        for i in range(10):
            threads.append(threading.Thread(target=reader))
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=recommender))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert len(errors) == 0, f"Errors under mixed load: {errors}"


# ── Test: Response Time Under Load ────────────────────────────────────────────

class TestResponseTimes:
    def test_recommend_response_time_under_load(self, token, seeded_data):
        sid = seeded_data["students"][0]
        latencies = []

        def worker():
            start = time.time()
            resp = requests.post(f"{BASE_URL}/recommend", json={
                "student_id": sid, "top_n": 3
            }, headers=_headers(token))
            latencies.append(time.time() - start)

        threads = [threading.Thread(target=worker) for _ in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]

        print(f"\n  30 concurrent recommends — p50: {p50:.3f}s, p95: {p95:.3f}s, p99: {p99:.3f}s")
        assert p95 < 5.0, f"p95 latency {p95:.3f}s exceeds 5s threshold"

    def test_bulk_update_response_time(self, token, seeded_data):
        students = seeded_data["students"]
        entries = [{"student_id": sid, "subject": "Math", "score": 0.7} for sid in students]
        latencies = []

        def worker():
            start = time.time()
            resp = requests.post(f"{BASE_URL}/bulk-update", json={
                "entries": entries
            }, headers=_headers(token))
            latencies.append(time.time() - start)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        print(f"\n  5 concurrent bulk-updates (10 students each) — p50: {p50:.3f}s, p95: {p95:.3f}s")
        assert p95 < 10.0, f"p95 latency {p95:.3f}s exceeds 10s threshold"


# ── Test: API Stability Under Sustained Load ──────────────────────────────────

class TestSustainedLoad:
    def test_sustained_requests_no_corruption(self, token, seeded_data):
        students = seeded_data["students"]
        content = seeded_data["content"]
        total_requests = 0
        total_errors = 0
        lock = threading.Lock()

        def sustained_worker(worker_id):
            nonlocal total_requests, total_errors
            for i in range(10):
                sid = students[(worker_id + i) % len(students)]
                cid = content[(worker_id + i) % len(content)]

                resp = requests.post(f"{BASE_URL}/recommend", json={
                    "student_id": sid, "top_n": 1
                }, headers=_headers(token))
                with lock:
                    total_requests += 1
                    if resp.status_code != 200:
                        total_errors += 1

                resp = requests.post(f"{BASE_URL}/update", json={
                    "student_id": sid, "content_id": cid, "reward": 0.5 + (i % 3) * 0.1
                }, headers=_headers(token))
                with lock:
                    total_requests += 1
                    if resp.status_code != 200:
                        total_errors += 1

        threads = [threading.Thread(target=sustained_worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        error_rate = total_errors / total_requests if total_requests > 0 else 0
        print(f"\n  Sustained load: {total_requests} requests, {total_errors} errors ({error_rate:.1%})")
        assert error_rate < 0.01, f"Error rate {error_rate:.1%} exceeds 1% threshold"
