"""Shared helper for live-server integration tests.

The real GradePulse API reports `engine == "GradePulse"` on `/health`. A dev
mock (Mia's `~/gradepulse-demo/mock-api.mjs`) also binds port 8000 and must NOT
be mistaken for the real server — live tests pointed at the mock returned 404s
because it has no GradePulse routes.

Run live tests against the real backend with:
    TEST_API_URL=http://localhost:<port> pytest tests/test_<x>_api.py
"""
import os
import requests

BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")


def is_real_api(base_url: str = BASE_URL) -> bool:
    """True only if base_url is the real GradePulse API (not a mock)."""
    try:
        r = requests.get(f"{base_url}/health", timeout=3)
        if r.status_code != 200:
            return False
        return r.json().get("engine") == "GradePulse"
    except (requests.ConnectionError, ValueError, KeyError):
        return False