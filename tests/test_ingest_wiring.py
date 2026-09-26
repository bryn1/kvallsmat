"""tests.test_ingest_wiring — the Willys store-scoped ingest WIRING
(MC 1355.17, T10f cycle 1): pull_store_scoped's PRODUCTION caller.

No network. Covers T10b §3 Population as wired in src/scheduler/periodic.py:
  * collect_resolved_willys: only ok-status chains contribute, dedupe on
    store_id across profiles;
  * the label join: storeflyer endpoint first (the design's flyerURL
    store-number join), the store's own name string as fallback;
  * run_store_scoped_ingest: upserts WITH store_id (RULE 1 prefixed ids),
    the chain-level NULL row untouched, fail-tolerant per store;
  * periodic.main consumes the saved resolved_stores list (the boot-ingest
    seam — T10b §6 step 5 fires).
"""
from __future__ import annotations

import httpx
import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.offers_db.store import Offer, upsert_week
from src.scheduler.periodic import collect_resolved_willys, run_store_scoped_ingest

WEEK = "2026-W39"


class FakeResp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class FakeSession:
    """Routes URLs to canned bodies; raises on URLs in ``boom``; counts gets."""

    def __init__(self, routes: dict, boom: set = frozenset()):
        self.routes = routes
        self.boom = boom
        self.requests: list[str] = []

        def get(url, headers=None):
            self.requests.append(url)
            if url in boom:
                raise httpx.ConnectError("boom")
            return FakeResp(200, routes.get(url, ""))

        self.get = get


def _row(ext_id, store_id=None, name="Grädde 5dl", price=1690):
    return {"grocer_id": "willys", "external_id": ext_id, "week_key": WEEK,
            "name": name, "price_cents": price, "unit": "dl",
            "valid_from": "2026-09-21", "valid_to": "2026-09-27",
            **({"store_id": store_id} if store_id else {})}


def _willys_cfg():
    from src.config import PlannerConfig
    return PlannerConfig(grocers=[PlannerConfig.grocer(
        "willys", "https://squid-api.tjek.com/v2/catalogs?dealer_id=c371GA",
        chain="willys")])


def _tjek_routes(label="Willys Alingsås Hagaplan"):
    """Storeflyer + Tjek catalog/hotspot fixtures for store 2149 (WEEK 39)."""
    return {
        "https://www.willys.se/axfood/rest/v2/storeflyer/2149":
            json.dumps({"name": label}),
        "https://squid-api.tjek.com/v2/catalogs?dealer_id=c371GA":
            json.dumps([{"id": "cat1", "label": label,
                         "run_from": "2026-09-21T00:00:00+0000",
                         "run_till": "2026-09-27T00:00:00+0000",
                         "publication_date": "2026-09-20T00:00:00+0000"}]),
        "https://squid-api.tjek.com/v2/catalogs/cat1/hotspots":
            json.dumps([{"id": "hs1", "offer": {
                "id": "off1", "heading": "GOUDA",
                "pricing": {"price": 49.9, "currency": "SEK"},
                "quantity": {"unit": {"symbol": "kg",
                                      "si": {"symbol": "kg", "factor": 1}}},
                "run_from": "2026-09-21T00:00:00+0000",
                "run_till": "2026-09-27T00:00:00+0000"}}]),
    }


def _ingest_engine(tmp_path):
    """A real offers DB (all tables registered) for the ingest wiring tests."""
    import app.models  # noqa: F401  (registers users/profile/offers on Base)
    from database import init_db

    engine = create_engine(f"sqlite:///{tmp_path}/ingest.db")
    init_db(engine)
    return engine, sessionmaker(bind=engine)


def test_collect_resolved_willys_dedups_and_skips_errored():
    """Only ok-status willys chains contribute; stores dedupe on store_id."""
    resolved = [
        {"chains": {"willys": {"status": "ok", "stores": [
            {"store_id": "2149", "store_name": "Willys Alingsås Hagaplan"},
            {"store_id": "2842", "store_name": "Willys Hemma Majorna"}]}}},
        {"chains": {"willys": {"status": "ok", "stores": [
            {"store_id": "2149", "store_name": "dup"}]}},   # deduped
         "ica": {"status": "error"}},
        {"chains": {"willys": {"status": "error", "error": "down",
                               "stores": [{"store_id": "1"}]}},  # skipped
         "ica": {"status": "ok", "stores": [{"store_id": "ica-1"}]}},  # not willys
    ]
    stores = collect_resolved_willys(resolved)
    assert [s["store_id"] for s in stores] == ["2149", "2842"]
    assert collect_resolved_willys([None, {}, {"chains": {}}]) == []


def test_store_scoped_ingest_wires_pull_store_scoped(tmp_path):
    """The production caller: resolved store -> storeflyer label join ->
    store-scoped pull -> upsert WITH store_id; the chain-level NULL row is
    untouched (P0 invariant holds through the new write path)."""
    engine, S = _ingest_engine(tmp_path)
    conn = S()
    try:
        upsert_week(conn, [_row("w-1", name="Köttfärs", price=4990)], WEEK)
        fake = FakeSession(_tjek_routes())
        written = run_store_scoped_ingest(
            conn, WEEK,
            [{"chains": {"willys": {"status": "ok", "stores": [
                {"store_id": "2149",
                 "store_name": "Willys Alingsås Hagaplan"}]}}}],
            session=fake, cfg=_willys_cfg())
        assert written == 1
        rows = conn.query(Offer).filter(Offer.store_id == "2149").all()
        assert len(rows) == 1
        assert rows[0].external_id == "2149:off1"  # RULE 1 prefix intact
        assert rows[0].name == "GOUDA"
        # the storeflyer label join fired (the design's flyerURL store-number
        # join), then the Tjek label matched the catalog
        assert any("/storeflyer/2149" in u for u in fake.requests)
        # chain-level NULL row survives unchanged
        null_row = (conn.query(Offer).filter(Offer.store_id.is_(None))
                    .filter(Offer.external_id == "w-1").one())
        assert null_row.name == "Köttfärs"
    finally:
        conn.close()


def test_store_scoped_ingest_label_falls_back_to_store_name(tmp_path):
    """Storeflyer gives no usable name -> the store's own name string is the
    Tjek label (the design's name-string join fallback, T10b §3)."""
    engine, S = _ingest_engine(tmp_path)
    conn = S()
    try:
        fake = FakeSession(_tjek_routes(label="Willys Borås Knalleland"))
        # storeflyer body is empty -> json parse fails -> label None -> fallback
        written = run_store_scoped_ingest(
            conn, WEEK,
            [{"chains": {"willys": {"status": "ok", "stores": [
                {"store_id": "2149",
                 "store_name": "Willys Borås Knalleland"}]}}}],
            session=fake, cfg=_willys_cfg())
        assert written == 1  # the fallback label matched the catalog
    finally:
        conn.close()


def test_store_scoped_ingest_fail_tolerant_per_store(tmp_path, monkeypatch):
    """A store whose pull RAISES is logged and skipped — the pass never raises
    (fail-tolerant-per-chain rule)."""
    from src.scheduler import periodic

    engine, S = _ingest_engine(tmp_path)
    conn = S()
    try:
        def boom(*a, **k):
            raise RuntimeError("feed exploded")

        monkeypatch.setattr(periodic, "pull_store_scoped", boom)
        written = run_store_scoped_ingest(
            conn, WEEK,
            [{"chains": {"willys": {"status": "ok", "stores": [
                {"store_id": "2149",
                 "store_name": "Willys Alingsås Hagaplan"}]}}}],
            cfg=_willys_cfg())
        assert written == 0  # skipped loudly, no exception
    finally:
        conn.close()


def test_periodic_main_runs_store_scoped_pass(tmp_path):
    """periodic.main consumes the saved resolved_stores list: the boot-ingest
    seam now produces store-scoped rows (T10b §6 step 5 fires)."""
    from src.scheduler.periodic import main as periodic_main

    fake = FakeSession(_tjek_routes())
    # only the willys grocer configured: the chain-level loop is empty, so the
    # store-scoped pass is the only writer — it must still find its grocer cfg
    rc = periodic_main(cfg=_willys_cfg(),
                       session=fake,
                       db_url=f"sqlite:///{tmp_path}/periodic.db",
                       resolved_stores=[
                           {"chains": {"willys": {"status": "ok", "stores": [
                               {"store_id": "2149",
                                "store_name": "Willys Alingsås Hagaplan"}]}}}])
    assert rc == 0
    engine = create_engine(f"sqlite:///{tmp_path}/periodic.db")
    with engine.connect() as c:
        rows = c.execute(text(
            "SELECT external_id, store_id FROM offers")).fetchall()
    assert ("2149:off1", "2149") in rows
