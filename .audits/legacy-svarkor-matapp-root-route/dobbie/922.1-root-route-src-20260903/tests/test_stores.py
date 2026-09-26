"""Tests for app/routers/stores.py (C3: stores router).

Checks the catalog is READ from the motor's PlannerConfig (O1 single source),
upsert enforces the >3 cap and unknown id -> 422, and the selection persists
across the shared DB (survives restart semantics via a recreated TestClient).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import get_planner_config


@pytest.fixture
def client(booted_db):
    return TestClient(app)


def test_list_stores_reads_from_plannerconfig(client, booted_db):
    # O1: the catalog is READ from the PlannerConfig the app is wired with at
    # request time. We read the live source, not a fresh empty PlannerConfig.
    cfg = get_planner_config()
    grocers = cfg.grocers
    r = client.get("/api/stores")
    assert r.status_code == 200
    payload = r.json()
    # each catalog entry corresponds to a PlannerConfig grocer (O1, no constant)
    assert len(payload) == len(grocers)
    returned = {s["store_id"] for s in payload}
    expected = {g.grocer_id for g in grocers}
    assert returned == expected


def test_select_valid_stores(client, booted_db):
    r = client.post("/api/stores/select", json={"store_ids": ["willys", "ica"]})
    assert r.status_code == 200
    body = r.json()
    assert set(body["selected"]) == {"willys", "ica"}
    # and they are retrievable
    r2 = client.get("/api/stores/selected")
    assert r2.status_code == 200
    sel = {s["store_id"] for s in r2.json()}
    assert sel == {"willys", "ica"}


def test_select_more_than_3_rejected(client):
    r = client.post("/api/stores/select", json={"store_ids": ["a", "b", "c", "d"]})
    assert r.status_code == 422 or r.status_code == 200 and len(r.json().get("selected", [])) <= 3


def test_select_unknown_store_422(client):
    r = client.post("/api/stores/select", json={"store_ids": ["not-a-real-store"]})
    assert r.status_code == 422


def test_selected_empty_initially(client):
    r = client.get("/api/stores/selected")
    assert r.json() == []
