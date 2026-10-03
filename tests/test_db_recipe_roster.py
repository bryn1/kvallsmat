"""tests.test_db_recipe_roster — MC 10037 (PORT-PLAN P1-a0) DB recipes served.

Offline temp-DB ``client`` fixture tests for the three P1-a0 claims:

  1. boot seeds the starter roster into the DB ``recipes`` table when empty
     (app.db.seed_recipes_if_empty), and re-seeding is idempotent;
  2. /api/menu plans from the DB rows when the table is non-empty (the static
     Phase-6 ROSTER accessor is NOT consulted);
  3. with the table emptied, the static ROSTER fallback still serves a full
     week (200, meal_days days, no in-week repeats).

No network, no new deps.
"""
from __future__ import annotations

from types import SimpleNamespace

from app import db as dbm
from app import security
from app.models.recipes_db import Recipe

WEEK = "2026-W37"


def _login(client, username: str, password: str) -> None:
    r = client.post("/api/auth/register",
                    json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    token = r.headers["set-cookie"].split(";")[0].split("=")[1]
    client.cookies.set(security.SESSION_COOKIE, token)


def _recipe_count() -> int:
    session = dbm._Session()
    try:
        return session.query(Recipe).count()
    finally:
        session.close()


def _sentinels(n: int, prefix: str):
    """Plain C-RDB-shaped stand-ins: only the attributes _allowed/plan/
    andel_extrapris read (servings>=persons default 4, JSON text cols)."""
    return [SimpleNamespace(
        title=f"{prefix} {i}", category="test", servings=8, vegetarian=0,
        budget_tier="budget", kid_friendly=0,
        ingredients_json="[]", allergens_json="[]") for i in range(n)]


# ------------------------------------------------- 1. boot seeds when empty

def test_boot_seeds_starter_recipes_when_empty(client):
    """The boot contract: create_all on an empty table then seed_starter once.

    (The conftest TestClient is yielded without entering its context, so the
    lifespan never runs in tests — existing suites drive the boot seam
    explicitly, same staging; the live uvicorn boot takes the same db.boot().)
    """
    from src.recipes.seed import STARTER_ROSTER
    assert _recipe_count() == 0, "fixture DB starts with an empty recipes table"
    dbm.boot()
    assert _recipe_count() == len(STARTER_ROSTER), \
        "boot did not seed the empty recipes table via seed_starter"
    # Idempotent: re-running the boot seam writes nothing new.
    assert dbm.seed_recipes_if_empty(dbm._engine) == 0
    assert _recipe_count() == len(STARTER_ROSTER)


# --------------------------------------------- 2. DB rows are what is served

def test_menu_serves_db_rows_not_static_roster(client, monkeypatch):
    import app.routers.menu as menu_router

    dbm.boot()  # boot-seed the starter rows (the P1-a0 served source)
    # Sentinel via the static accessor only: if the menu still plans DB
    # dishes, the ROSTER path was not taken (non-empty table wins).
    monkeypatch.setattr(menu_router, "recipes",
                        lambda: _sentinels(1, "ZZZ Sentinel T-rollmat"))
    _login(client, "dbuser", "pw-dbroster-1")
    resp = client.get(f"/api/menu?week={WEEK}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    titles = {d["dish_id"] for s in body["suggestions"] for d in s["days"]}
    assert titles, "menu planned no dishes from the non-empty DB roster"
    assert "ZZZ Sentinel T-rollmat" not in titles
    session = dbm._Session()
    try:
        db_titles = {r.title for r in session.query(Recipe).all()}
    finally:
        session.close()
    assert titles <= db_titles, "served dishes must come from the DB table"


# ------------------------------------------------------ 3. ROSTER fallback

def test_menu_falls_back_to_static_roster_when_table_empty(client, monkeypatch):
    import app.routers.menu as menu_router

    session = dbm._Session()
    try:
        session.query(Recipe).delete()
        session.commit()
    finally:
        session.close()
    sents = _sentinels(5, "Fallback rattärta")
    monkeypatch.setattr(menu_router, "recipes", lambda: sents)
    _login(client, "fbuser", "pw-fallback-1")
    resp = client.get(f"/api/menu?week={WEEK}")
    assert resp.status_code == 200, resp.text
    days = resp.json()["suggestions"][0]["days"]
    assert len(days) == 5, "empty DB must still fill meal_days via fallback"
    titles = [d["dish_id"] for d in days]
    assert len(set(titles)) == 5 and set(titles) <= {s.title for s in sents}
