"""
Hardening from the November 2026 security assessment (L3, L4, L5, L11):
API response headers, CORS origins, what /health tells strangers, and the
client address behind Cloudflare. Offline, TestClient.
"""
import os

import pytest
from fastapi.testclient import TestClient

from linucb_brain.api import app as app_module
from linucb_brain.api.app import app

OPERATOR = {"X-Operator-Key": os.environ["OPERATOR_KEY"]}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_api_responses_carry_security_headers(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["referrer-policy"] == "no-referrer"


def test_health_tells_strangers_only_that_it_is_alive(client):
    public = client.get("/health").json()
    assert public["status"] == "alive" and public["engine"] == "GradePulse"
    assert not {"version", "worker_pid", "backup_count", "backup_status"} & set(public)
    private = client.get("/health", headers=OPERATOR).json()
    assert {"version", "worker_pid", "backup_count"} <= set(private)
    assert client.get("/health", headers={"X-Operator-Key": "wrong"}).json() == public


def test_cloudflare_address_is_used_only_when_trusted(monkeypatch):
    class Req:
        headers = {"cf-connecting-ip": "198.51.100.9", "x-forwarded-for": "203.0.113.1"}

        class client:
            host = "127.0.0.1"

    monkeypatch.setattr(app_module, "TRUST_CF_CONNECTING_IP", False)
    monkeypatch.setattr(app_module, "TRUST_FORWARDED_FOR", False)
    assert app_module._client_host(Req) == "127.0.0.1"
    monkeypatch.setattr(app_module, "TRUST_CF_CONNECTING_IP", True)
    assert app_module._client_host(Req) == "198.51.100.9"


def test_cors_allows_the_site_but_not_strangers(client):
    site = app_module.FRONTEND_URL.split(",")[0].strip()
    ok = client.options("/auth/login", headers={"Origin": site, "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == site
    bad = client.options("/auth/login", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers
