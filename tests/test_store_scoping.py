"""tests.test_store_scoping — offline tests for MC 1355.16 store-level
selection per postnummer (T10b §3/§4/§8).

No network. Covers the design-specified matrix:
  * migration: guarded ALTERs add ALL THREE columns to a pre-change DB with
    rows, are idempotent, tolerate the concurrent-boot "duplicate column name"
    race, and exist on a fresh DB;
  * upsert P0 regression: a store-scoped write never overwrites a NULL
    chain-level row (both orders), and a bare-id reuse fails LOUD (T10d N1);
  * menu: store clause (NULL passes, matching store_id passes, non-matching
    dropped, errored chain = chain-level only, no-resolved = byte-identical
    no-op) and the dedup preferring the store-level row (T10d N3 casefold+
    strip, unit-ignoring key);
  * API: PUT /api/profile postal_code semantics (absent = unchanged,
    explicit null clears, malformed 422, per-chain error persisted not 500),
    GET roundtrip, and the auth-gated GET /api/stores?postal_code= preview
    (401 anonymous / 200 authenticated).
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app import auth_service, security
from src.offers_db.store import Offer, upsert_week

WEEK = "2026-W39"


# ------------------------------------------------------------- migration ----

def _prechange_engine(path: str):
    """A DB holding BOTH tables WITH rows, but WITHOUT the three new columns
    (the live-DB state the DA verified via PRAGMA table_info)."""
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE offers (offer_id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " grocer_id VARCHAR NOT NULL, external_id VARCHAR NOT NULL,"
            " week_key VARCHAR NOT NULL, name VARCHAR, price_cents INTEGER,"
            " unit VARCHAR, valid_from VARCHAR, valid_to VARCHAR,"
            " CONSTRAINT uq_offer UNIQUE (grocer_id, external_id, week_key))"))
        conn.execute(text(
            "CREATE TABLE profile (profile_id INTEGER PRIMARY KEY"
            " AUTOINCREMENT, user_id INTEGER NOT NULL UNIQUE,"
            " persons INTEGER NOT NULL, meal_days INTEGER NOT NULL,"
            " kron_budget INTEGER, selected_stores VARCHAR,"
            " updated_at DATETIME)"))
        conn.execute(text(
            "INSERT INTO offers (grocer_id, external_id, week_key, name,"
            " price_cents) VALUES ('willys','w-1','2026-W39','Grädde',100)"))
        conn.execute(text(
            "INSERT INTO profile (user_id, persons, meal_days, kron_budget)"
            " VALUES (1, 2, 5, 900)"))
    return engine


def _cols(engine, table):
    return {c["name"] for c in inspect(engine).get_columns(table)}


def test_migration_adds_all_three_columns_rows_intact(tmp_path):
    from app.db import ensure_columns

    engine = _prechange_engine(str(tmp_path / "pre.db"))
    assert "store_id" not in _cols(engine, "offers")
    assert "postal_code" not in _cols(engine, "profile")
    ensure_columns(engine)
    assert {"store_id"} <= _cols(engine, "offers")
    assert {"postal_code", "resolved_stores"} <= _cols(engine, "profile")
    # rows intact
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM offers")).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM profile")).scalar() == 1


def test_migration_idempotent(tmp_path):
    from app.db import ensure_columns

    engine = _prechange_engine(str(tmp_path / "pre.db"))
    ensure_columns(engine)
    ensure_columns(engine)  # second boot: no-op, never a raise
    assert "store_id" in _cols(engine, "offers")


def test_migration_tolerates_concurrent_boot_duplicate_column(tmp_path):
    """T10d F8: another boot adds the column between our inspect and ALTER —
    the 'duplicate column name' OperationalError is tolerated (after a
    re-inspect confirms) and the app still boots."""
    from app.db import ensure_columns

    engine = _prechange_engine(str(tmp_path / "pre.db"))
    with engine.begin() as conn:  # the "concurrent" boot wins the race
        conn.execute(text("ALTER TABLE offers ADD COLUMN store_id String"))
    ensure_columns(engine)  # must NOT raise
    assert "store_id" in _cols(engine, "offers")
    assert "postal_code" in _cols(engine, "profile")
    assert "resolved_stores" in _cols(engine, "profile")


def test_fresh_db_boot_has_all_columns(tmp_path):
    from app import db as dbm
    from database import init_db

    import app.models  # noqa: F401  (register tables)
    engine = create_engine(f"sqlite:///{tmp_path}/fresh.db")
    init_db(engine)
    dbm._engine = engine
    dbm._Session = sessionmaker(bind=engine, autoflush=False)
    try:
        dbm.boot()  # reuses the bound engine; runs init_db + ensure_columns
        assert "store_id" in _cols(engine, "offers")
        assert {"postal_code", "resolved_stores"} <= _cols(engine, "profile")
    finally:
        dbm._engine = None
        dbm._Session = None


# ------------------------------------------------- upsert P0 regression ----

def _row(ext_id, store_id=None, name="Grädde 5dl", price=1690):
    return {"grocer_id": "willys", "external_id": ext_id, "week_key": WEEK,
            "name": name, "price_cents": price, "unit": "dl",
            "valid_from": "2026-09-21", "valid_to": "2026-09-27",
            **({"store_id": store_id} if store_id else {})}


def _session(engine):
    return sessionmaker(bind=engine, autoflush=False)()


def _offers(session):
    return session.query(Offer).order_by(Offer.offer_id).all()


def test_p0_store_scoped_write_never_overwrites_chain_level_row(tmp_path):
    """THE P0 regression (T10b §8): chain-level pull then store-scoped pull of
    the same catalog — the NULL rows survive unchanged and the store-scoped
    rows are separate (prefixed external ids)."""
    engine = create_engine(f"sqlite:///{tmp_path}/p0.db")
    import app.models  # noqa: F401
    from database import init_db
    init_db(engine)
    s = _session(engine)
    try:
        # 1) chain-level pull: bare ids, store_id NULL
        upsert_week(s, [_row("hs1", name="Grädde 5dl", price=1690)], WEEK)
        # 2) store-scoped pull of the SAME catalog: prefixed id + store_id
        upsert_week(s, [_row("2103:hs1", store_id="2103",
                             name="Grädde 5dl", price=1490)], WEEK)
        rows = _offers(s)
        assert len(rows) == 2  # a SECOND row, not an overwrite
        chain_row = [r for r in rows if r.store_id is None][0]
        assert chain_row.external_id == "hs1"  # NULL row SURVIVED unchanged
        assert chain_row.price_cents == 1690
        store_row = [r for r in rows if r.store_id == "2103"][0]
        assert store_row.external_id == "2103:hs1"
        assert store_row.price_cents == 1490
        # 3) reverse order too: store-scoped first, then chain-level
        upsert_week(s, [_row("hs1", name="Grädde 5dl", price=1590)], WEEK)
        rows = _offers(s)
        assert len(rows) == 2  # still two rows
        chain_row = [r for r in rows if r.store_id is None][0]
        assert chain_row.price_cents == 1590  # chain-level updated in place
        assert [r for r in rows if r.store_id == "2103"][0].price_cents == 1490
    finally:
        s.close()


def test_upsert_bare_id_reuse_fails_loud(tmp_path):
    """T10d N1: a store-scoped payload reusing a BARE external id must fail
    LOUD (ValueError), never silently merge into or retract the NULL row."""
    engine = create_engine(f"sqlite:///{tmp_path}/loud.db")
    import app.models  # noqa: F401
    from database import init_db
    init_db(engine)
    s = _session(engine)
    try:
        upsert_week(s, [_row("hs1")], WEEK)
        with pytest.raises(ValueError, match="rule 1 violated"):
            upsert_week(s, [_row("hs1", store_id="2103")], WEEK)
        rows = _offers(s)
        assert len(rows) == 1 and rows[0].store_id is None  # NULL row intact
    finally:
        s.close()


def test_upsert_store_scoped_idempotent_per_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/idem.db")
    import app.models  # noqa: F401
    from database import init_db
    init_db(engine)
    s = _session(engine)
    try:
        upsert_week(s, [_row("2103:hs1", store_id="2103")], WEEK)
        upsert_week(s, [_row("2103:hs1", store_id="2103", price=1390)], WEEK)
        upsert_week(s, [_row("2104:hs1", store_id="2104")], WEEK)
        rows = _offers(s)
        assert len(rows) == 2  # same store re-upserts in place; other store separate
        assert {r.store_id for r in rows} == {"2103", "2104"}
        assert [r for r in rows if r.store_id == "2103"][0].price_cents == 1390
    finally:
        s.close()


# ----------------------------------------------------- menu filter/dedup ----

def _offer(ext_id, name, store_id=None, grocer="willys", price=1000):
    return Offer(grocer_id=grocer, external_id=ext_id, week_key=WEEK,
                 name=name, price_cents=price, unit="dl",
                 valid_from="2026-09-21", valid_to="2026-09-27",
                 store_id=store_id)


RESOLVED = {"resolved_at": "2026-09-26T12:00:00+00:00", "chains": {
    "willys": {"status": "ok", "stores": [
        {"chain": "willys", "store_id": "2103", "store_name": "Willys Majorna",
         "lat": 57.69, "lon": 11.91, "distance_km": 0.1}]},
    "ica": {"status": "error", "error": "token endpoint down", "stores": []},
}}


def test_store_clause_keeps_null_and_matching_drops_nonmatching():
    from app.routers.menu import _apply_store_clause

    offers = [_offer("a", "Grädde"),           # chain-level NULL -> kept
              _offer("b", "Grädde", "2103"),   # resolved store -> kept
              _offer("c", "Grädde", "9999")]   # unresolved store -> dropped
    kept = _apply_store_clause(offers, RESOLVED)
    assert [o.external_id for o in kept] == ["a", "b"]


def test_store_clause_errored_chain_contributes_chain_level_only():
    from app.routers.menu import _apply_store_clause

    offers = [_offer("a", "Krossade tomater", None, grocer="ica"),
              _offer("b", "Krossade tomater", "1726", grocer="ica")]
    kept = _apply_store_clause(offers, RESOLVED)  # ica status = error
    assert [o.external_id for o in kept] == ["a"]


def test_store_clause_no_resolved_stores_is_byte_identical_noop():
    from app.routers.menu import _apply_store_clause, _dedup_by_name

    offers = [_offer("a", "Grädde"), _offer("b", "Grädde", "2103"),
              _offer("c", "Spagetti", None, grocer="ica")]
    for resolved in (None, {}, {"chains": {}}):
        assert _apply_store_clause(offers, resolved) == offers
        assert _dedup_by_name(offers, resolved) == offers


def test_dedup_prefers_store_level_row_and_counts_once():
    from app.routers.menu import _dedup_by_name

    offers = [_offer("chain-1", "Grädde 5dl", None, price=1690),
              _offer("store-1", "GRÄDDE 5DL ", "2103", price=1490)]  # N3: casefold+strip
    kept = _dedup_by_name(offers, RESOLVED)
    assert len(kept) == 1
    assert kept[0].store_id == "2103" and kept[0].price_cents == 1490


def test_dedup_key_ignores_unit_but_not_chain():
    """T10d N3 note: the dedup key ignores ``unit`` — same name different unit
    collapses to the store-level row; different chains never collapse."""
    from app.routers.menu import _dedup_by_name

    a = _offer("chain-1", "Grädde 5dl", None)
    b = _offer("store-1", "grädde 5dl", "2103")
    b.unit = "st"
    kept = _dedup_by_name([a, b], RESOLVED)
    assert len(kept) == 1 and kept[0].store_id == "2103"
    ica_chain = _offer("i-1", "Grädde 5dl", None, grocer="ica")
    kept2 = _dedup_by_name([a, ica_chain], RESOLVED)
    assert len(kept2) == 2  # different grocer_id -> never collapsed


# ----------------------------------------------------------------- API ------

def _mkuser_and_login(client, username, password):
    from app import db as dbm
    from app.models.users import User

    if dbm._Session is None:
        dbm.boot()
    session = dbm._Session()
    try:
        if session.query(User).filter_by(username=username).first() is None:
            session.add(User(username=username,
                             password_hash=security.hash_password(password)))
            session.commit()
    finally:
        session.close()
    token = auth_service.login(username, password)
    client.cookies.set(security.SESSION_COOKIE, token)


FAKE_RESOLVE = {"resolved_at": "2026-09-26T12:00:00+00:00", "chains": {
    "willys": {"status": "ok", "stores": [
        {"chain": "willys", "store_id": "2103",
         "store_name": "Willys Majorna", "lat": 57.69, "lon": 11.91,
         "distance_km": 0.1}]},
    "ica": {"status": "error", "error": "token endpoint down", "stores": []},
}}


@pytest.fixture()
def fake_resolve(monkeypatch):
    monkeypatch.setattr("app.routers.profile.resolve_stores",
                        lambda pc: json.loads(json.dumps(FAKE_RESOLVE)))
    monkeypatch.setattr("app.routers.stores.resolve_stores_cached",
                        lambda pc: json.loads(json.dumps(FAKE_RESOLVE)))


def test_put_profile_with_postal_code_resolves_and_echoes(client, fake_resolve):
    _mkuser_and_login(client, "postaluser", "pw-postal-1")
    body = {"persons": 2, "meal_days": 5, "kron_budget": 900,
            "selected_stores": [], "postal_code": "414 51"}
    r = client.put("/api/profile", json=body)
    assert r.status_code == 200
    profile = r.json()["profile"]
    assert profile["postal_code"] == "41451"  # normalized to digits-only
    assert profile["resolved_stores"] == FAKE_RESOLVE
    # GET roundtrip returns the same persisted shape
    g = client.get("/api/profile")
    assert g.json()["postal_code"] == "41451"
    assert g.json()["resolved_stores"]["chains"]["willys"]["status"] == "ok"
    assert g.json()["resolved_stores"]["chains"]["ica"]["status"] == "error"


def test_put_profile_absent_postal_code_leaves_persisted_value(client, fake_resolve):
    """Stale-client regression (T10d F6): a PUT without postal_code must not
    wipe the saved postnummer."""
    _mkuser_and_login(client, "staleuser", "pw-stale-1")
    client.put("/api/profile", json={
        "persons": 2, "meal_days": 5, "kron_budget": 900,
        "selected_stores": [], "postal_code": "41451"})
    r = client.put("/api/profile", json={  # stale client: no postal_code key
        "persons": 3, "meal_days": 4, "kron_budget": 800,
        "selected_stores": []})
    assert r.status_code == 200
    profile = r.json()["profile"]
    assert profile["persons"] == 3
    assert profile["postal_code"] == "41451"          # unchanged
    assert profile["resolved_stores"] == FAKE_RESOLVE  # unchanged


def test_put_profile_explicit_null_clears_postal(client, fake_resolve):
    _mkuser_and_login(client, "clearuser", "pw-clear-1")
    client.put("/api/profile", json={
        "persons": 2, "meal_days": 5, "kron_budget": 900,
        "selected_stores": [], "postal_code": "41451"})
    r = client.put("/api/profile", json={
        "persons": 2, "meal_days": 5, "kron_budget": 900,
        "selected_stores": [], "postal_code": None})
    profile = r.json()["profile"]
    assert profile["postal_code"] is None
    assert profile["resolved_stores"] is None  # cleared with it


def test_put_profile_malformed_postal_422(client, fake_resolve):
    _mkuser_and_login(client, "baduser", "pw-bad-1")
    r = client.put("/api/profile", json={
        "persons": 2, "meal_days": 5, "kron_budget": 900,
        "selected_stores": [], "postal_code": "41 451"})
    assert r.status_code == 422


def test_put_profile_locator_failure_never_500(client, monkeypatch):
    """A raising locator is persisted as an error object and echoed — never a
    500 (T10b §4)."""
    _mkuser_and_login(client, "failuser", "pw-fail-1")

    def boom(pc):
        raise RuntimeError("network down")

    monkeypatch.setattr("app.routers.profile.resolve_stores", boom)
    r = client.put("/api/profile", json={
        "persons": 2, "meal_days": 5, "kron_budget": 900,
        "selected_stores": [], "postal_code": "41451"})
    assert r.status_code == 200
    resolved = r.json()["profile"]["resolved_stores"]
    assert "error" in resolved and "network down" in resolved["error"]


def test_stores_postal_code_preview_auth_gated(client, fake_resolve):
    """T10d F5: the locator pipeline is never reachable anonymously."""
    # anonymous WITH the param -> 401
    assert client.get("/api/stores?postal_code=41451").status_code == 401
    _mkuser_and_login(client, "previewuser", "pw-preview-1")
    # authenticated WITH the param -> 200 + nearby block
    r = client.get("/api/stores?postal_code=41451")
    assert r.status_code == 200
    body = r.json()
    assert body["nearby"] == FAKE_RESOLVE
    assert [s["store_id"] for s in body["stores"]] == [
        "willys", "ica", "coop", "lidl"]
    # anonymous WITHOUT the param keeps today's behavior (a plain list)
    client.cookies.clear()
    anon = client.get("/api/stores")
    assert anon.status_code == 200
    assert isinstance(anon.json(), list)


def test_menu_response_carries_offer_sources(client, fake_resolve):
    """The menu journey with a postal_code profile: offer_sources present,
    used_offer_ids unchanged in shape."""
    _mkuser_and_login(client, "menuuser2", "pw-menu-2")
    client.put("/api/profile", json={
        "persons": 2, "meal_days": 5, "kron_budget": 900,
        "selected_stores": [], "postal_code": "41451"})
    from app import db as dbm
    s = dbm._Session()
    try:
        upsert_week(s, [_row("w-1", name="Köttfärs nöt 500g", price=4990)], WEEK)
    finally:
        s.close()
    r = client.get(f"/api/menu?week={WEEK}")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("offer_sources"), list)
    for src in body["offer_sources"]:
        # MC 1355.17 (T10f DA P3-2): store_name joined for the UI display.
        assert set(src) == {"offer_id", "grocer_id", "store_id", "store_name"}
    assert all("used_offer_ids" in d
               for sug in body["suggestions"] for d in sug["days"])


def test_menu_endpoint_applies_store_clause_and_dedup(client, fake_resolve):
    """T10f DA P2-1: the store clause must run inside the ENDPOINT, not only in
    the helpers — a store-scoped row for an UNRESOLVED store (9999) is excluded
    from offer_sources while the chain-level row survives."""
    _mkuser_and_login(client, "menuuser3", "pw-menu-3")
    client.put("/api/profile", json={
        "persons": 2, "meal_days": 5, "kron_budget": 900,
        "selected_stores": [], "postal_code": "41451"})
    from app import db as dbm
    s = dbm._Session()
    try:
        upsert_week(s, [_row("w-1", name="Köttfärs nöt 500g", price=4990),
                        _row("9999:hs9", store_id="9999",
                             name="Fiskgratäng", price=3990)], WEEK)
    finally:
        s.close()
    r = client.get(f"/api/menu?week={WEEK}")
    assert r.status_code == 200
    sources = r.json()["offer_sources"]
    assert all(src["store_id"] != "9999" for src in sources)  # unresolved: dropped
    assert any(src["grocer_id"] == "willys" and src["store_id"] is None
               for src in sources)  # chain-level row survives


def test_stores_preview_rejects_malformed_and_normalizes_postal(client):
    """T10f DA P2-2: the preview param follows the SAME postnummer rule as
    PUT /api/profile — malformed -> 422, valid spaced value -> digits-only."""
    _mkuser_and_login(client, "previewuser2", "pw-preview-2")
    r = client.get("/api/stores", params={"postal_code": "abcde"})
    assert r.status_code == 422
    seen: list[str] = []

    def capture(pc):
        seen.append(pc)
        return json.loads(json.dumps(FAKE_RESOLVE))

    import app.routers.stores as stores_router
    original = stores_router.resolve_stores_cached
    stores_router.resolve_stores_cached = capture
    try:
        r = client.get("/api/stores", params={"postal_code": "414 51"})
    finally:
        stores_router.resolve_stores_cached = original
    assert r.status_code == 200
    assert seen == ["41451"]  # normalized to digits-only before the resolve



def test_menu_offer_sources_carry_store_name(client, fake_resolve):
    """T10f DA P3-2: offer_sources carries the resolved store NAME so the UI
    shows 'butik: Willys Majorna', not a raw id."""
    _mkuser_and_login(client, "menuuser4", "pw-menu-4")
    client.put("/api/profile", json={
        "persons": 2, "meal_days": 5, "kron_budget": 900,
        "selected_stores": [], "postal_code": "41451"})
    from app import db as dbm
    s = dbm._Session()
    try:
        upsert_week(s, [_row("2103:hs1", store_id="2103",
                             name="Grädde 5dl", price=1490)], WEEK)
    finally:
        s.close()
    r = client.get(f"/api/menu?week={WEEK}")
    assert r.status_code == 200
    scoped = [src for src in r.json()["offer_sources"]
              if src["store_id"] == "2103"]
    assert scoped and all(src["store_name"] == "Willys Majorna"
                          for src in scoped)
    # chain-level sources carry store_name None
    assert all(src["store_name"] is None for src in r.json()["offer_sources"]
               if src["store_id"] is None)
