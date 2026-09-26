"""Tests for app/main.py (C1: web main), app/db.py (C2: session+boot)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(booted_db):
    return TestClient(app)


def test_health_returns_ok(client, booted_db):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["app"] == "kvallsmats"
    assert body["motor"] is True
    assert body["motor_resolved"] is True


def test_health_motor_resolved_flag(booted_db):
    # presence of the field on the response is enough here (resolved iff motor found)
    from app.config import MOTOR_RESOLVED
    assert MOTOR_RESOLVED is True


def test_root_serves_index_html(client, booted_db):
    """GET / (and /index.html) serves the menu-ui template (templates/index.html)."""
    for path in ("/", "/index.html"):
        r = client.get(path)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
        assert "Kvällsmat" in r.text
        assert "Veckomeny" in r.text
