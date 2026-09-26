"""Tests for app/routers/menu.py (C4: menu router).

The load-bearing motor seam: binds plan_menu to GET /api/menu with NO business
logic in the router. The N7 digest check runs the IDENTICAL fixture that run_motor
proves (2026-W34, 4 offers, 18 recipes, seed=1234, meal_days=5, persons=4,
vegetarian=false, budget_tier=budget) and asserts the byte-identical digest
0b308db1390cd466 (sha256 of sorted plan JSON, first 16 hex chars).
"""
from __future__ import annotations

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

N7_DIGEST = "0b308db1390cd466"


@pytest.fixture
def client(booted_db):
    return TestClient(app)


def _digest(payload) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()[:16]


def test_menu_n7_digest_identical_to_motor(client):
    r = client.get(
        "/api/menu",
        params={
            "week": "2026-W34",
            "meal_days": 5,
            "persons": 4,
            "vegetarian": False,
            "budget_tier": "budget",
            "seed": 1234,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["week_key"] == "2026-W34"
    assert len(body["days"]) == 5
    assert _digest(body) == N7_DIGEST


def test_menu_rejects_bad_week(client):
    r = client.get("/api/menu", params={"week": "not-a-week"})
    assert r.status_code in (400, 422)


def test_menu_rejects_out_of_range_counts(client):
    r = client.get("/api/menu", params={"week": "2026-W34", "meal_days": 0})
    assert r.status_code in (400, 422)
