"""tests.test_rotation_accept — MC 10037 (PORT-PLAN P1-a) rotation + accept + ratings.

Offline temp-DB tests for the accept-recorded 42-day rotation:

  * POST /api/menu/accept recomputes the offered plan for its seed EXACTLY
    (one shared assembly), records usage, replaces on re-accept; 401/422 gates;
  * GET /api/menu never repeats a title accepted for weeks N+1..N+5, and lets
    it return at N+6 (exactly 42 days — owner-quoted matapp rule);
  * thin strict pool -> relax oldest-used-first fills meal_days + one WARNING
    (the matapp GT-5rz lesson: never silent starvation);
  * POST /api/recipe/rate upserts per user; 1..7 pydantic bounds; 401 gates.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

from app import db as dbm
from app import security
from app.models.recipe_usage import RecipeUsage, list_usage
from app.models.recipes_db import Recipe

WEEK = "2026-W37"
FOLLOWING = ["2026-W38", "2026-W39", "2026-W40", "2026-W41", "2026-W42"]
ALLOWING = "2026-W43"  # N+6: monday difference is exactly 42 days -> may return


def _login(client, username: str, password: str = "pw-rotation-1") -> None:
    r = client.post("/api/auth/register",
                    json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    token = r.headers["set-cookie"].split(";")[0].split("=")[1]
    client.cookies.set(security.SESSION_COOKIE, token)


def _served_titles(resp_json, seed=None) -> list[str]:
    out = []
    for s in resp_json["suggestions"]:
        if seed is None or s["seed"] == seed:
            out.extend(d["dish_id"] for d in s["days"])
    return out


def _offer(client, week: str, seed: int) -> list[str]:
    """What GET /api/menu currently serves for (week, seed) — the dishes the
    client must echo back to accept (DA P1-A)."""
    return _served_titles(client.get(f"/api/menu?week={week}").json(), seed=seed)


def _accept(client, seed: int, week: str = WEEK, dishes=None):
    if dishes is None:
        dishes = _offer(client, week, seed)
    return client.post("/api/menu/accept",
                       json={"seed": seed, "week": week, "dishes": dishes})


# ------------------------------------------------------- accept: exact recompute

def test_accept_recomputes_offered_plan_and_records_usage(client):
    dbm.boot()
    _login(client, "accuser")
    offered = client.get(f"/api/menu?week={WEEK}").json()
    seed101 = _served_titles(offered, seed=101)
    assert len(seed101) == 5  # meal_days default

    r = _accept(client, 101, dishes=seed101)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"ok": True, "week_key": WEEK, "dishes": seed101}

    session = dbm._Session()
    try:
        rows = list_usage(session, 1)  # first registered user
    finally:
        session.close()
    assert [row.title for row in rows] == seed101
    assert all(row.seed == 101 and row.week_key == WEEK for row in rows)


def test_accept_replaces_rows_for_same_week(client):
    dbm.boot()
    _login(client, "repuser")
    offered = client.get(f"/api/menu?week={WEEK}").json()
    seed202 = _served_titles(offered, seed=202)

    assert _accept(client, 101).status_code == 200
    r = _accept(client, 202, dishes=seed202)
    assert r.status_code == 200, r.text
    assert r.json()["dishes"] == seed202

    session = dbm._Session()
    try:
        rows = list_usage(session, 1)
    finally:
        session.close()
    # replace-all: only the seed-202 plan remains, no seed-101 leftovers.
    assert all(row.seed == 202 for row in rows)
    assert [row.title for row in rows] == seed202


def test_accept_gates_401_and_422(client):
    dbm.boot()
    # anonymous -> 401, never 200 (gate C6 line)
    r = client.post("/api/menu/accept", json={"seed": 101, "week": WEEK})
    assert r.status_code == 401

    _login(client, "gateuser")
    # dishes is REQUIRED (DA P1-A): omitting the echo is a contract violation,
    # not a silent record.
    assert client.post("/api/menu/accept",
                       json={"seed": 101, "week": WEEK}).status_code == 422
    assert client.post("/api/menu/accept",
                       json={"seed": "not-an-int", "week": WEEK,
                             "dishes": []}).status_code == 422
    assert client.post("/api/menu/accept",
                       json={"seed": 101, "week": "garbage",
                             "dishes": []}).status_code == 422
    assert client.post("/api/menu/accept",
                       json={"seed": 101, "week": "2026-W54",
                             "dishes": []}).status_code == 422
    assert client.post("/api/menu/accept",
                       json={"seed": 999, "week": WEEK,
                             "dishes": ["x"]}).status_code == 422


# --------------------------------------------- DA P1-A: divergence never lands

def test_accept_divergence_409_and_records_nothing(client):
    dbm.boot()
    _login(client, "divuser")
    offered = _offer(client, WEEK, 101)

    # Offers move after the GET (boot-ingest on a restart reproduces exactly
    # this): the seed-101 plan the user saw is no longer the plan on disk.
    from src.offers_db.store import upsert_week
    s = dbm._Session()
    try:
        upsert_week(s, [{"grocer_id": "ica", "external_id": "p-div",
                         "week_key": WEEK, "name": "Laxfilé 600g",
                         "price_cents": 8990, "regular_price_cents": 12990,
                         "valid_from": "2026-09-07", "valid_to": "2026-09-13"}],
                    WEEK)
        s.commit()
    finally:
        s.close()

    r = client.post("/api/menu/accept",
                    json={"seed": 101, "week": WEEK, "dishes": offered})
    assert r.status_code == 409, r.text

    session = dbm._Session()
    try:
        assert list_usage(session, 1) == [], \
            "a divergent accept must NEVER land usage rows (DA P1-A)"
    finally:
        session.close()

    # The honest path still works: accept the plan as CURRENTLY served.
    fresh = _offer(client, WEEK, 101)
    assert fresh != offered, "probe setup failed: offers did not move the plan"
    assert _accept(client, 101, dishes=fresh).status_code == 200


# ------------------------------------------------- DA P2-B: bounds + no empty week

def test_profile_fields_are_bounded_422(client):
    _login(client, "bounduser")
    base = {"selected_stores": []}
    for bad in ({"persons": 0, "meal_days": 5, "kron_budget": 900},
                {"persons": 99999, "meal_days": 5, "kron_budget": 900},
                {"persons": 2, "meal_days": 0, "kron_budget": 900},
                {"persons": 2, "meal_days": 8, "kron_budget": 900},
                {"persons": 2, "meal_days": 5, "kron_budget": -1}):
        assert client.put("/api/profile", json={**base, **bad}).status_code == 422, bad
    # the bounds themselves are inclusive
    assert client.put("/api/profile", json={
        **base, "persons": 12, "meal_days": 7, "kron_budget": 900,
    }).status_code == 200


def test_in_range_but_unsatisfiable_profile_409_not_empty_week(client):
    dbm.boot()
    _login(client, "bigfam")
    assert client.put("/api/profile", json={
        "persons": 12, "meal_days": 5, "kron_budget": 900,
        "selected_stores": [],
    }).status_code == 200  # in-range (DA P2-B bounds) ...
    r = client.get(f"/api/menu?week={WEEK}")
    # ... yet every roster serving is < 12 -> zero eligible recipes. The
    # guarantee: never a 200 with [0,0,0]-day suggestions.
    assert r.status_code == 409, r.text
    assert "no eligible recipes" in r.json()["detail"]


# --------------------------------------------------- 42-day rotation semantics

def test_rotation_excludes_accepted_titles_for_five_weeks_returns_at_six(client):
    dbm.boot()
    _login(client, "rotuser")
    offered = client.get(f"/api/menu?week={WEEK}").json()
    accepted = _served_titles(offered, seed=101)
    assert _accept(client, 101).status_code == 200

    for wk in FOLLOWING:
        titles = set(_served_titles(client.get(f"/api/menu?week={wk}").json()))
        assert titles, f"week {wk} planned nothing"
        assert not (set(accepted) & titles), \
            f"accepted dish leaked into {wk}: {set(accepted) & titles}"

    # N+6: usage is exactly 42 days old -> the plan may be offered again, and
    # determinism recomputes the SAME seed-101 dishes (same pool, same seed).
    later = client.get(f"/api/menu?week={ALLOWING}").json()
    assert _served_titles(later, seed=101) == accepted


def test_rotation_is_per_user(client):
    dbm.boot()
    _login(client, "owner1")
    accepted = _served_titles(client.get(f"/api/menu?week={WEEK}").json(),
                              seed=101)
    assert _accept(client, 101).status_code == 200
    client.cookies.clear()

    _login(client, "owner2")  # second household sees the full pool
    titles = set(_served_titles(client.get("/api/menu?week=2026-W38").json()))
    assert set(accepted) & titles, \
        "another user's accept must not shrink this user's pool"


# ------------------------------------- thin pool: relax oldest-first + warning

def _sentinels(n: int):
    return [SimpleNamespace(
        title=f"Rot testratt {i}", category="test", servings=8, vegetarian=0,
        budget_tier="budget", kid_friendly=0,
        ingredients_json="[]", allergens_json="[]") for i in range(n)]


def test_thin_pool_relaxes_oldest_first_and_warns(client, monkeypatch, caplog):
    import app.routers.menu as menu_router

    dbm.boot()
    _login(client, "thinuser")
    assert client.put("/api/profile", json={
        "persons": 2, "meal_days": 5, "kron_budget": 900,
        "selected_stores": [], "prefer_kid_friendly": 0,
    }).status_code == 200

    sents = _sentinels(5)
    monkeypatch.setattr(menu_router, "recipes", lambda: sents)
    session = dbm._Session()
    try:
        session.query(Recipe).delete()          # force the ROSTER fallback
        from app.models.users import User
        uid = session.query(User).filter_by(username="thinuser").one().user_id
        # four of the five dishes accepted LAST week -> strict pool is 1 of 5
        used = sents[:4]
        for offset, s in enumerate(used):
            session.add(RecipeUsage(user_id=uid, title=s.title,
                                    week_key=f"2026-W{35 - offset:02d}",
                                    seed=101))
        session.commit()
    finally:
        session.close()

    with caplog.at_level(logging.WARNING, logger="kvallsmat.app.menu"):
        resp = client.get(f"/api/menu?week={WEEK}")
    assert resp.status_code == 200, resp.text
    days = resp.json()["suggestions"][0]["days"]
    assert len(days) == 5, "relaxation must refill meal_days, not starve"
    assert {d["dish_id"] for d in days} == {s.title for s in sents}
    warns = [rec for rec in caplog.records
             if rec.levelno == logging.WARNING and "relax" in rec.getMessage()]
    assert warns, "silent relaxation is the GT-5rz failure mode"


# ------------------------------------------------------------- ratings: 1..7

def test_rate_upsert_and_gates(client):
    _login(client, "rateuser")
    assert client.get("/api/recipe/ratings").json() == []

    r = client.post("/api/recipe/rate",
                    json={"title": "Köttbullar med gräddsås och potatis",
                          "rating": 5})
    assert r.status_code == 200, r.text
    # upsert: same title re-rates, never duplicates
    assert client.post("/api/recipe/rate",
                       json={"title": "Köttbullar med gräddsås och potatis",
                             "rating": 7}).status_code == 200
    ratings = client.get("/api/recipe/ratings").json()
    assert len(ratings) == 1 and ratings[0]["rating"] == 7

    # bounds: matapp's 1..7 scale enforced at the pydantic boundary
    for bad in (0, 8, "x"):
        assert client.post("/api/recipe/rate",
                           json={"title": "T", "rating": bad}).status_code == 422
    assert client.post("/api/recipe/rate",
                       json={"title": "", "rating": 3}).status_code == 422


def test_rate_and_ratings_require_auth(client):
    assert client.post("/api/recipe/rate",
                       json={"title": "T", "rating": 3}).status_code == 401
    assert client.get("/api/recipe/ratings").status_code == 401
