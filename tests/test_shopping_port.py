"""tests.test_shopping_port — MC 10037 P1-b/P2-a/P2-b (shopping + memory + staples).

Offline, temp-DB via the shared ``client`` fixture; login idiom from
test_menu_wiring. Covers the port DoD:

  1. 401 on EVERY shopping/staples endpoint without a session;
  2. add = normalize + categorize; longest-keyword-first (tomatpuré → torrvaror);
  3. dedupe + quantity merge on the same week+item;
  4. toggle -> purchase recorded in shopping_memory (avg-interval math ported);
  5. habitual injection appears only on a FRESH week, never duplicates, staples
     win a name collision;
  6. staple CRUD + due injection + reset of last_bought on buy;
  7. malformed / not-a-real week -> 422 (same boundary as the menu router).

Point 4 of the child-B brief (build-from-accepted-plan) ships with commit A's
recipe_usage and is NOT asserted here — DEFERRED (see CHILD-B-RESULT.md).
"""
from __future__ import annotations

from datetime import date, timedelta

from app import auth_service, db as dbm, security
from app.models.shopping import ShoppingMemory, ShoppingItem, Staple
from app.models.users import User

WEEK = "2026-W20"


def _mkuser_and_login(client, username="anna", password="hemligt1") -> int:
    """Insert a user row and log in (same idiom as test_menu_wiring)."""
    if dbm._Session is None:
        dbm.boot()
    session = dbm._Session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if user is None:
            user = User(username=username,
                        password_hash=security.hash_password(password))
            session.add(user)
            session.commit()
        uid = user.user_id
    finally:
        session.close()
    token = auth_service.login(username, password)
    assert token is not None
    client.cookies.set(security.SESSION_COOKIE, token)
    return uid


def _items(client, week=WEEK) -> list[dict]:
    r = client.get(f"/api/shopping?week={week}")
    assert r.status_code == 200, r.text
    return r.json()


# ─── 1. auth gate ────────────────────────────────────────────────────────────


def test_every_endpoint_401_without_session(client):
    assert client.get("/api/shopping").status_code == 401
    assert client.post("/api/shopping", json={"item": "mjölk"}).status_code == 401
    assert client.delete("/api/shopping/mjölk").status_code == 401
    assert client.post("/api/shopping/toggle",
                       json={"item": "mjölk"}).status_code == 401
    assert client.get("/api/staples").status_code == 401
    assert client.post("/api/staples",
                       json={"item": "salt", "interval_days": 30}).status_code == 401
    assert client.delete("/api/staples/salt").status_code == 401


# ─── 2. normalize + categorize (matapp expectations ported) ──────────────────


def test_add_normalizes_and_categorizes(client):
    _mkuser_and_login(client)
    for raw, want_item, want_cat in [
        ("Röda lökar", "lök", "frukt/grönt"),        # adjective + synonym map
        ("tomatpuré", "tomatpuré", "torrvaror"),      # longest keyword wins
        ("crème fraiche", "crème fraiche", "mejeri"),
        ("tofu", "tofu", "övrigt"),
    ]:
        r = client.post(f"/api/shopping?week={WEEK}", json={"item": raw})
        assert r.status_code == 200, r.text
        row = r.json()
        assert row["item"] == want_item, raw
        assert row["category"] == want_cat, raw
        assert row["source"] == "manual" and row["added_manually"] == 1


# ─── 3. dedupe + merge ───────────────────────────────────────────────────────


def test_add_merges_quantity_same_week(client):
    _mkuser_and_login(client)
    client.post(f"/api/shopping?week={WEEK}",
                json={"item": "mjölk", "quantity": "500 g"})
    r = client.post(f"/api/shopping?week={WEEK}",
                    json={"item": "Mjölk", "quantity": "300 g"})
    assert r.json()["quantity"] == "800 g"
    rows = _items(client)
    assert [x["item"] for x in rows] == ["mjölk"]      # deduped, one row


# ─── 4. toggle = purchase → memory (+ avg interval math) ─────────────────────


def test_toggle_records_purchase_with_avg_interval(client):
    uid = _mkuser_and_login(client)
    client.post(f"/api/shopping?week={WEEK}", json={"item": "grädde"})
    d_old = (date.today() - timedelta(days=30)).isoformat()
    d_mid = (date.today() - timedelta(days=10)).isoformat()
    session = dbm._Session()
    try:  # two past purchases: one 20-day gap; buying today adds a 10-day gap
        session.add(ShoppingMemory(
            user_id=uid, item="grädde", last_bought=d_mid, times_bought=2,
            avg_interval_days=20.0,
            bought_dates='["%s", "%s"]' % (d_old, d_mid)))
        session.commit()
    finally:
        session.close()

    r = client.post("/api/shopping/toggle",
                    json={"item": "Grädde", "week": WEEK})
    assert r.status_code == 200 and r.json()["checked"] == 1

    session = dbm._Session()
    try:
        mem = session.query(ShoppingMemory).filter_by(user_id=uid,
                                                      item="grädde").first()
        assert mem.times_bought == 3
        assert mem.last_bought == date.today().isoformat()
        assert mem.avg_interval_days == 15.0     # avg(20-day gap, 10-day gap)
    finally:
        session.close()


# ─── 5. habitual injection: fresh week only, never duplicates ────────────────


def _seed_habit(uid, item, days_ago=10, avg=7.0, times=4):
    last = (date.today() - timedelta(days=days_ago)).isoformat()
    session = dbm._Session()
    try:
        session.add(ShoppingMemory(
            user_id=uid, item=item, last_bought=last, times_bought=times,
            avg_interval_days=avg, bought_dates='["%s"]' % last))
        session.commit()
    finally:
        session.close()


def test_habitual_injection_fresh_week_only(client):
    uid = _mkuser_and_login(client)
    _seed_habit(uid, "kaffe")

    rows = _items(client, "2026-W30")
    injected = [x for x in rows if x["item"] == "kaffe"]
    assert len(injected) == 1 and injected[0]["source"] == "memory"

    rows = _items(client, "2026-W30")                    # GET again: no dupes
    assert sum(1 for x in rows if x["item"] == "kaffe") == 1

    client.post("/api/shopping?week=2026-W31",
                json={"item": "kanel"})                  # W31 no longer fresh
    rows = _items(client, "2026-W31")
    assert all(x["item"] != "kaffe" for x in rows)       # no re-injection


# ─── 6. staples: CRUD + due injection + reset on buy ─────────────────────────


def test_staples_inject_and_reset_on_buy(client):
    uid = _mkuser_and_login(client)
    r = client.post("/api/staples",
                    json={"item": "Havregryn", "interval_days": 14})
    assert r.status_code == 200
    assert r.json()["last_bought"] is None
    assert client.post("/api/staples",
                       json={"item": "salt", "interval_days": 0}).status_code == 422

    rows = _items(client, "2026-W40")
    stap = [x for x in rows if x["item"] == "havregryn"]
    assert len(stap) == 1 and stap[0]["source"] == "staple"

    r = client.post("/api/shopping/toggle",
                    json={"item": "havregryn", "week": "2026-W40"})
    assert r.json()["checked"] == 1

    session = dbm._Session()
    try:
        st = session.query(Staple).filter_by(user_id=uid,
                                             item="havregryn").first()
        assert st.last_bought == date.today().isoformat()
    finally:
        session.close()

    rows = _items(client, "2026-W41")                    # next fresh week
    assert all(x["item"] != "havregryn" for x in rows)   # not due yet

    assert client.delete("/api/staples/havregryn").status_code == 200
    assert client.delete("/api/staples/havregryn").status_code == 404


def test_staple_wins_name_collision_with_memory(client):
    uid = _mkuser_and_login(client)
    _seed_habit(uid, "socker")
    client.post("/api/staples", json={"item": "socker", "interval_days": 30})
    rows = _items(client, "2026-W45")
    sugar = [x for x in rows if x["item"] == "socker"]
    assert len(sugar) == 1 and sugar[0]["source"] == "staple"


# ─── 7. week-key boundary + delete ───────────────────────────────────────────


def test_week_validation_and_delete(client):
    _mkuser_and_login(client)
    for bad in ("abc", "2026-W54", "2026-W00", "9999-W99"):
        assert client.get(f"/api/shopping?week={bad}").status_code == 422, bad
    client.post(f"/api/shopping?week={WEEK}", json={"item": " salt "})
    assert client.delete(f"/api/shopping/Salt?week={WEEK}").status_code == 200
    assert client.delete(f"/api/shopping/salt?week={WEEK}").status_code == 404
