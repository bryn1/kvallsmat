"""tests.test_fixround_offers — MC 1355.7 fixround regressions (T5 DA verdict FIX).

Covers the three offers-side fixes named by audit/T5-DA-verdict.md:

* P1-1 silent total failure: periodic.main WARNS when a grocer yields 0
  entries, and /health carries an offers signal (offers_current_week +
  per-grocer counts) so a dead feed is visible, not green-silent.
* P1-2 extrapris rule dead: adapters/normalizer populate regular_price_cents
  + savings_cents from fixture data so andel_extrapris can be non-zero.
* P2 double external_id prefix: the final external_id carries exactly ONE
  chain prefix (the CHAIN_MAP id_prefix, owned by chain_mapper alone).

All offline: fixture HTML/JSON and a temp sqlite DB (conftest client fixture).
"""
from __future__ import annotations

import logging

from src.normalizer.chain_mapper import iso_week_bounds, normalize
from src.offers_db.store import upsert_week


# ------------------------------------------------------------- P1-1 warning

def test_periodic_warns_when_grocer_yields_zero_entries(tmp_path, monkeypatch, caplog):
    """A grocer whose feed degrades to 0 entries must log a WARNING (T5 attack 2)."""
    from src.config import PlannerConfig
    from src.scheduler import periodic

    cfg = PlannerConfig()
    monkeypatch.setattr(periodic, "pull_grocer",
                        lambda g, wk, session=None: {"grocer_id": g.grocer_id,
                                                     "week_key": wk, "entries": []})
    with caplog.at_level(logging.WARNING, logger="src.scheduler.periodic"):
        periodic.main(cfg=cfg, db_url=f"sqlite:///{tmp_path}/offers.db")
    warnings = [r for r in caplog.records
                if r.levelno == logging.WARNING and "0 offers" in r.getMessage()]
    assert {g.grocer_id for g in cfg.grocers} <= {
        r.getMessage().split()[1] for r in warnings}, \
        "every zero-entry grocer must be named in a warning"


# ------------------------------------------------------- P1-1 health signal

def test_health_offers_signal_empty_then_populated(client):
    """/health reports offers_current_week (0 on an empty DB, >0 after ingest)."""
    import app.db as dbm
    from src.offers_db.store import Offer

    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["offers_current_week"] == 0
    assert body["offers_by_grocer"] == {}
    assert body["offers_week"]  # current ISO week key is reported

    week = body["offers_week"]
    monday, sunday = iso_week_bounds(week)
    session = dbm._Session()
    try:
        upsert_week(session, [
            {"grocer_id": "ica", "external_id": "ica-1", "week_key": week,
             "name": "Köttfärs nöt 500g", "price_cents": 4990,
             "regular_price_cents": 6990, "savings_cents": 2000,
             "valid_from": monday.isoformat(), "valid_to": sunday.isoformat()},
            {"grocer_id": "lidl", "external_id": "lidl-1", "week_key": week,
             "name": "Bananer", "price_cents": 1490,
             "valid_from": monday.isoformat(), "valid_to": sunday.isoformat()},
        ], week)
    finally:
        session.close()

    body = client.get("/health").json()
    assert body["offers_current_week"] == 2
    assert body["offers_by_grocer"] == {"ica": 1, "lidl": 1}


# ------------------------------------------------ P1-2 regular price + ratio

def test_regular_price_populated_from_lidl_fixture():
    """Lidl deletedPrice flows through normalize into regular/savings cents."""
    raw = {"grocer_id": "lidl", "entries": [{
        "external_id": "66000056", "name": "Bananer", "price": 14.9,
        "unit": "kg", "regular_price": 18.8,
        "valid_from": "2026-09-21", "valid_to": "2026-09-27",
    }]}
    rows = normalize("lidl", raw, "2026-W39")
    assert len(rows) == 1
    row = rows[0]
    assert row["price"] == 1490
    assert row["regular_price_cents"] == 1880
    assert row["savings_cents"] == 390


def test_ica_entry_without_regular_price_stays_null():
    """No regular price on the page -> NULL regular/savings, never invented."""
    raw = {"grocer_id": "ica", "entries": [{
        "external_id": "5004009053", "name": "Fryst torskryggfilé",
        "price": 119.0, "unit": "st",
        "valid_from": "2026-09-21", "valid_to": "2026-09-27",
    }]}
    row = normalize("ica", raw, "2026-W39")[0]
    assert row["regular_price_cents"] is None
    assert row["savings_cents"] is None


def test_andel_extrapris_nonzero_after_ingest(client):
    from app.optimizer.optimizer import andel_extrapris, is_extraprice
    from app.optimizer.recipes import recipes

    week = client.get("/health").json()["offers_week"]
    monday, sunday = iso_week_bounds(week)
    import app.db as dbm
    session = dbm._Session()
    try:
        upsert_week(session, [{
            "grocer_id": "willys", "external_id": "w-1", "week_key": week,
            "name": "Köttfärs nöt 500g", "price_cents": 4990,
            "regular_price_cents": 9990, "savings_cents": 5000,
            "valid_from": monday.isoformat(), "valid_to": sunday.isoformat(),
        }], week)
        from src.offers_db.store import list_offers_in_week
        offers = list_offers_in_week(session, week)
    finally:
        session.close()

    assert any(is_extraprice(o) for o in offers), "ingested offer must be extrapris"
    köttbullar = next(r for r in recipes() if "Köttbullar" in r.title)
    assert andel_extrapris(köttbullar, offers) > 0.0, \
        "andel_extrapris must be non-zero once a regular price is ingested"


# ------------------------------------------------- P2 single-prefix invariant

def test_external_id_carries_exactly_one_prefix():
    """Adapter emits a bare id; chain_mapper adds the ONE CHAIN_MAP prefix."""
    ica_raw = {"grocer_id": "ica", "entries": [{
        "external_id": "5004009053", "name": "Fryst torskryggfilé",
        "price": 119.0, "unit": "st",
        "valid_from": "2026-09-21", "valid_to": "2026-09-27"}]}
    lidl_raw = {"grocer_id": "lidl", "entries": [{
        "external_id": "66000056", "name": "Bananer", "price": 14.9,
        "unit": "kg", "valid_from": "2026-09-21", "valid_to": "2026-09-27"}]}

    ica_row = normalize("ica", ica_raw, "2026-W39")[0]
    lidl_row = normalize("lidl", lidl_raw, "2026-W39")[0]
    assert ica_row["external_id"] == "ica-5004009053"
    assert lidl_row["external_id"] == "lidl-66000056"
    for row in (ica_row, lidl_row):
        assert not row["external_id"].startswith(("ica-ica-", "lidl-lidl-")), \
            "double prefix must never come back"
