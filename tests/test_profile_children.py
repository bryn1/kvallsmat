"""tests.test_profile_children — MC 1355.18 (T11) profile field fixtures.

Offline fixture tests for the two new profile fields (num_children,
prefer_kid_friendly): absent-means-unchanged PUT semantics (the postal_code
rule), explicit-null clear, 422 validation, and GET echo. All via the temp-DB
``client`` fixture — no network.
"""
from __future__ import annotations

from app import auth_service, security

BASE = {"persons": 2, "meal_days": 5, "kron_budget": 900, "selected_stores": []}


def _login(client, username: str = "famuser", password: str = "pw-fam-1") -> None:
    """Register a fresh user through the EXISTING endpoint and use its session."""
    r = client.post("/api/auth/register",
                    json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    # Secure cookie + http://testserver: replay the Set-Cookie explicitly
    # (same TestClient jar artifact T5 attack 4 documented for login).
    token = r.headers["set-cookie"].split(";")[0].split("=")[1]
    client.cookies.set(security.SESSION_COOKIE, token)


def test_num_children_absent_means_unchanged(client):
    _login(client)
    r1 = client.put("/api/profile", json={**BASE, "num_children": 2})
    assert r1.status_code == 200
    assert r1.json()["profile"]["num_children"] == 2
    # PUT WITHOUT the field: the persisted value must survive.
    r2 = client.put("/api/profile", json=dict(BASE))
    assert r2.status_code == 200
    r3 = client.get("/api/profile")
    assert r3.status_code == 200
    assert r3.json()["num_children"] == 2


def test_num_children_explicit_null_clears(client):
    _login(client)
    assert client.put("/api/profile",
                      json={**BASE, "num_children": 3}).status_code == 200
    r = client.put("/api/profile", json={**BASE, "num_children": None})
    assert r.status_code == 200
    assert client.get("/api/profile").json()["num_children"] is None


def test_num_children_negative_422(client):
    _login(client)
    r = client.put("/api/profile", json={**BASE, "num_children": -1})
    assert r.status_code == 422


def test_prefer_kid_friendly_absent_means_unchanged_and_roundtrip(client):
    _login(client)
    assert client.put("/api/profile",
                      json={**BASE, "prefer_kid_friendly": 1}).status_code == 200
    # Absent field = unchanged.
    assert client.put("/api/profile", json=dict(BASE)).status_code == 200
    assert client.get("/api/profile").json()["prefer_kid_friendly"] == 1
    # Explicit 0 = an active "not prefer" (checkbox semantics), stored.
    assert client.put("/api/profile",
                      json={**BASE, "prefer_kid_friendly": 0}).status_code == 200
    assert client.get("/api/profile").json()["prefer_kid_friendly"] == 0
    # Explicit null = clear.
    assert client.put("/api/profile",
                      json={**BASE, "prefer_kid_friendly": None}).status_code == 200
    assert client.get("/api/profile").json()["prefer_kid_friendly"] is None


def test_prefer_kid_friendly_out_of_range_422(client):
    _login(client)
    r = client.put("/api/profile", json={**BASE, "prefer_kid_friendly": 2})
    assert r.status_code == 422


def test_profile_get_echoes_new_fields(client):
    _login(client)
    assert client.put(
        "/api/profile",
        json={**BASE, "num_children": 2, "prefer_kid_friendly": 1},
    ).status_code == 200
    body = client.get("/api/profile").json()
    assert body["num_children"] == 2
    assert body["prefer_kid_friendly"] == 1
