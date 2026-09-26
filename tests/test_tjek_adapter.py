"""tests.test_tjek_adapter — offline unit tests for the Tjek squid adapter
(MC 1355.10).

No network: fixtures are inline dicts shaped after the LIVE API responses
fetched 2026-09-26 (audit T7a + the T8 shape probe): /v2/catalogs?dealer_id=
lists per-store catalogs; /v2/catalogs/{id}/hotspots carries per-offer records
with offer.pricing.price, offer.quantity.unit.si and offer-level ISO
run_from/run_till (the hotspot-level run_from/run_till are epoch ints).
Covers: happy path, catalog-pick logic (expired/future skipped, newest publish
wins), missing price dropped, non-SEK dropped, non-200/exception -> empty feed,
and the single-prefix invariant (bare external_id — chain_mapper owns the
prefix).
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from src.config import PlannerConfig
from src.fetcher.adapters import tjek
from src.fetcher.grocer import pull_grocer

WILLYS_CFG = PlannerConfig.grocer(
    "willys", "https://squid-api.tjek.com/v2/catalogs?dealer_id=c371GA",
    chain="willys")

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)

CATALOGS = [
    {"id": "OLD", "label": "Willys X", "run_from": "2026-09-13T22:00:00+0000",
     "run_till": "2026-09-20T21:59:59+0000", "publication_date": None},
    {"id": "CUR", "label": "Willys Y", "run_from": "2026-09-20T22:00:00+0000",
     "run_till": "2026-09-27T21:59:59+0000",
     "publication_date": "2026-09-21T01:55:07+0000"},
    {"id": "FUT", "label": "Willys Z", "run_from": "2026-09-28T22:00:00+0000",
     "run_till": "2026-10-04T21:59:59+0000", "publication_date": None},
]

HOTSPOTS = [
    {"id": "hs1", "type": "offer", "heading": "GOUDA",
     "run_from": 1789941600, "run_till": 1790546399,
     "offer": {"id": "s7a0G8aaB36--QVXTrP0x", "heading": "GOUDA",
               "pricing": {"price": 49.9, "currency": "SEK", "pre_price": None},
               "quantity": {"unit": {"symbol": "kg",
                                     "si": {"symbol": "kg", "factor": 1}},
                            "size": {"from": 1, "to": 1}},
               "run_from": "2026-09-20T22:00:00+0000",
               "run_till": "2026-09-27T21:59:59+0000"}},
    {"id": "hs2", "type": "offer", "heading": "Bryggkaffe",
     "offer": {"id": "CJKedWUWfSZjj2Epg9Xb4", "heading": "Bryggkaffe",
               "pricing": {"price": 109, "currency": "SEK"},
               "quantity": {"unit": {"symbol": "g",
                                     "si": {"symbol": "kg", "factor": 0.001}},
                            "size": {"from": 450, "to": 500}},
               "run_from": "2026-09-20T22:00:00+0000",
               "run_till": "2026-09-27T21:59:59+0000"}},
    {"id": "hs3", "type": "offer", "heading": "No price",
     "offer": {"id": "noprice", "heading": "No price",
               "pricing": {"price": None, "currency": "SEK"},
               "quantity": {"unit": {"symbol": "st", "si": {"symbol": "pcs",
                                                            "factor": 1}}},
               "run_from": "2026-09-20T22:00:00+0000",
               "run_till": "2026-09-27T21:59:59+0000"}},
    {"id": "hs4", "type": "offer", "heading": "Wrong currency",
     "offer": {"id": "eur", "heading": "Wrong currency",
               "pricing": {"price": 5, "currency": "EUR"},
               "quantity": {}, "run_from": "2026-09-20T22:00:00+0000",
               "run_till": "2026-09-27T21:59:59+0000"}},
]


class FakeResp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class FakeSession:
    """Routes URLs to canned bodies; raises on URLs in ``boom``."""

    def __init__(self, routes: dict, boom: set = frozenset()):
        self.routes = routes
        self.boom = boom

    def get(self, url, headers=None):
        if url in self.boom:
            raise httpx.ConnectError("boom")
        return FakeResp(200, self.routes.get(url, ""))


def test_pick_catalog_skips_expired_and_future():
    cat = tjek.pick_catalog(CATALOGS, now=NOW)
    assert cat is not None and cat["id"] == "CUR"


def test_pick_catalog_newest_publish_wins():
    dup = [dict(CATALOGS[1], id="CUR2",
                publication_date="2026-09-22T10:00:00+0000"),
           CATALOGS[1]]
    assert tjek.pick_catalog(dup, now=NOW)["id"] == "CUR2"
    assert tjek.pick_catalog([], now=NOW) is None
    assert tjek.pick_catalog([CATALOGS[0]], now=NOW) is None  # expired only


def test_pick_catalog_grace_fallback():
    # Observed (MC 1355.10): Coop's dealer listing rotated the current leaflet
    # out mid-week, holding only next week's catalogs. The nearest future
    # catalog within the 48h grace window is picked instead of serving nothing.
    # ...but only within the grace window: 24h ahead is picked, 4 days is not.
    soon = dict(CATALOGS[2], id="SOON",
                run_from="2026-09-25T12:00:00+0000")
    assert tjek.pick_catalog([soon], now=NOW)["id"] == "SOON"
    far = dict(CATALOGS[2], run_from="2026-09-28T22:00:00+0000")
    assert tjek.pick_catalog([far], now=NOW) is None


def test_parse_hotspots_happy_and_drops():
    entries = tjek.parse_hotspots(HOTSPOTS, "2026-09-21")
    assert [e["external_id"] for e in entries] == [
        "s7a0G8aaB36--QVXTrP0x", "CJKedWUWfSZjj2Epg9Xb4"]
    gouda, kaffe = entries
    assert gouda["name"] == "GOUDA" and gouda["price"] == 49.9
    assert gouda["unit"] == "kg"
    assert gouda["valid_from"] == "2026-09-20"
    assert gouda["valid_to"] == "2026-09-27"
    assert kaffe["unit"] == "kg"  # g + si kg factor 0.001 -> comparison unit
    # single-prefix invariant: the adapter NEVER prefixes — chain_mapper owns it
    for e in entries:
        assert not e["external_id"].startswith(("willys-", "coop-"))


def test_pull_happy_path_through_pull_grocer():
    session = FakeSession({
        "https://squid-api.tjek.com/v2/catalogs?dealer_id=c371GA":
            httpx.Response(200, json=CATALOGS).text,
        "https://squid-api.tjek.com/v2/catalogs/CUR/hotspots":
            httpx.Response(200, json=HOTSPOTS).text,
    })
    feed = pull_grocer(WILLYS_CFG, "2026-W39", session=session)
    assert feed["grocer_id"] == "willys"
    assert len(feed["entries"]) == 2


def test_pull_fail_tolerant():
    base = "https://squid-api.tjek.com/v2/catalogs"

    class _S:
        def __init__(self, routes=None, boom=frozenset()):
            self.routes = routes or {}
            self.boom = boom

        def get(self, url, headers=None):
            if url in self.boom:
                raise httpx.ConnectError("boom")
            return FakeResp(200, self.routes.get(url, ""))

    # non-200 on the catalog list
    class _E:
        def get(self, url, headers=None):
            return FakeResp(500, "")
    assert pull_grocer(WILLYS_CFG, "2026-W39", session=_E())["entries"] == []
    # network exception mid-pull
    boom = _S(boom={f"{base}?dealer_id=c371GA"})
    assert pull_grocer(WILLYS_CFG, "2026-W39", session=boom)["entries"] == []
    # bad JSON body
    bad = _S({f"{base}?dealer_id=c371GA": "not json"})
    assert pull_grocer(WILLYS_CFG, "2026-W39", session=bad)["entries"] == []
    # no covering catalog -> empty feed, never a raise
    none = _S({f"{base}?dealer_id=c371GA":
               httpx.Response(200, json=[CATALOGS[0]]).text})
    assert pull_grocer(WILLYS_CFG, "2026-W39", session=none)["entries"] == []
