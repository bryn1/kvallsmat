"""tests.test_menu_kid_friendly — MC 1355.18 (T11) planner/menu fixtures.

Offline fixture tests for the kid-friendly boost (rank tiebreak, NOT a filter)
and the additive MenuDay.kid_friendly field. All via the temp-DB ``client``
fixture or direct ``plan_menu`` calls — no network.
"""
from __future__ import annotations

from types import SimpleNamespace

from app import security
from app.optimizer.optimizer import FamilyPrefs
from app.optimizer.recipes import recipes as roster
from src.planner.menu import plan_menu

WEEK = "2026-W37"
KID_TITLE = "Köttbullar med gräddsås och potatis"


def _offer(oid: int, name: str):
    """Minimal offer stand-in: plan_menu reads only offer_id and name."""
    return SimpleNamespace(offer_id=oid, name=name)


def _tie_offers():
    """Offers that hit a kid-friendly AND a non-kid dish EQUALLY (1 hit each)
    — a genuine tie the boost must break."""
    return [_offer(1, "Köttbullar 500g"), _offer(2, "Laxfilé 600g")]


# ------------------------------------------------- MenuDay carries the flag

def test_menu_day_carries_kid_friendly_flag(client):
    from src.offers_db.store import upsert_week

    r = client.post("/api/auth/register",
                    json={"username": "kiduser", "password": "pw-kid-1"})
    assert r.status_code == 200
    # Secure cookie + http://testserver: replay the Set-Cookie explicitly.
    token = r.headers["set-cookie"].split(";")[0].split("=")[1]
    client.cookies.set(security.SESSION_COOKIE, token)
    rows = [
        {"grocer_id": "willys", "external_id": "w-1", "week_key": WEEK,
         "name": "Köttbullar 500g", "price_cents": 4990, "unit": "g",
         "valid_from": "2026-09-07", "valid_to": "2026-09-13"},
    ]
    from app import db as dbm
    session = dbm._Session()
    try:
        upsert_week(session, rows, WEEK)
    finally:
        session.close()
    resp = client.get(f"/api/menu?week={WEEK}")
    assert resp.status_code == 200
    days = resp.json()["suggestions"][0]["days"]
    # The offer hits the kid-friendly köttbullar — day 1 must carry the flag.
    assert days[0]["dish_id"] == KID_TITLE
    assert days[0]["kid_friendly"] is True
    # And a non-kid day renders false (additive field always present).
    assert all(isinstance(d["kid_friendly"], bool) for d in days)


# ------------------------------------------------- boost breaks ties

def test_prefer_kid_friendly_boosts_kid_dishes_on_ties():
    offers = _tie_offers()
    base = dict(meal_days=2, persons=4)
    off = plan_menu(WEEK, offers, roster(), FamilyPrefs(**base), seed=103)
    on = plan_menu(WEEK, offers, roster(), FamilyPrefs(**base,
                   prefer_kid_friendly=True), seed=103)
    # Deterministic, different orders; the kid dish is promoted with the flag.
    assert off["days"][0]["dish_id"] != on["days"][0]["dish_id"]
    assert on["days"][0]["dish_id"] == KID_TITLE
    # Same seed twice -> byte-identical (determinism guard).
    on2 = plan_menu(WEEK, offers, roster(), FamilyPrefs(**base,
                    prefer_kid_friendly=True), seed=103)
    assert on["days"] == on2["days"]


def test_menu_plan_deterministic_same_seed():
    offers = _tie_offers()
    family = FamilyPrefs(meal_days=3, persons=4, prefer_kid_friendly=True)
    a = plan_menu(WEEK, offers, roster(), family, seed=202)
    b = plan_menu(WEEK, offers, roster(), family, seed=202)
    assert a["days"] == b["days"]


# ------------------------------------------------- no kid recipes: no break

def test_menu_without_kid_friendly_recipes_still_200_full_week(client, monkeypatch):
    """All-roster-0 plan: the menu must NOT break — 200, full week, and the
    plan is identical to the flag-off plan (structural regression guard)."""
    import app.routers.menu as menu_router

    all_zero = [type(r)(**{**r.__dict__, "kid_friendly": 0}) for r in roster()]
    monkeypatch.setattr(menu_router, "recipes", lambda: all_zero)

    from app import db as dbm
    from app.models.recipes_db import Recipe

    # MC 10037 (P1-a0): the menu now serves the DB recipes table when
    # non-empty (boot seeds it) — empty it here so the monkeypatched static
    # ROSTER accessor is what actually serves this no-kid-recipes scenario.
    _s = dbm._Session()
    try:
        _s.query(Recipe).delete()
        _s.commit()
    finally:
        _s.close()

    r = client.post("/api/auth/register",
                    json={"username": "nokid", "password": "pw-nokid-1"})
    assert r.status_code == 200
    token = r.headers["set-cookie"].split(";")[0].split("=")[1]
    client.cookies.set(security.SESSION_COOKIE, token)
    assert client.put("/api/profile", json={
        "persons": 2, "meal_days": 5, "kron_budget": 900,
        "selected_stores": [], "prefer_kid_friendly": 1,
    }).status_code == 200
    resp = client.get(f"/api/menu?week={WEEK}")
    assert resp.status_code == 200
    days = resp.json()["suggestions"][0]["days"]
    assert len(days) == 5
    assert all(d["kid_friendly"] is False for d in days)
    # Identical to the flag-off plan on the same roster (boost is a no-op here).
    family_off = FamilyPrefs(meal_days=5, persons=2)
    family_on = FamilyPrefs(meal_days=5, persons=2, prefer_kid_friendly=True)
    off = plan_menu(WEEK, [], all_zero, family_off, seed=103)
    on = plan_menu(WEEK, [], all_zero, family_on, seed=103)
    assert off["days"] == on["days"]
