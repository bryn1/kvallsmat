"""tests.test_locator — offline unit tests for the src/locator package
(MC 1355.16, T10b §2/§8).

No network: every locator gets an injected fake session (the httpx-like idiom
of src/fetcher/grocer.py: ``get(url, headers)`` -> ``.status_code``/``.text``)
with fixture payloads shaped after the LIVE responses recorded in audit T10a.
Covers: per-chain locate() mapping + nearest-3 ordering, dummy-store
filtering, fail-tolerance (one chain raising never fails the resolve), the
geocode cache (hit issues no second request, TTL expiry re-requests), the Coop
daily detail cache (cold-start-once, zero detail requests on the second
resolve, cache survives a "reboot", partial run persists nothing), and the
bounded resolve-result cache (T10d N4).
"""
from __future__ import annotations

import json

import httpx
import pytest

from src.locator import (
    CHAIN_LOCATORS,
    clear_caches,
    resolve_stores,
    resolve_stores_cached,
)
from src.locator import coop, geocode, ica, lidl, willys


class FakeResp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class FakeSession:
    """Routes URLs to canned bodies; raises on URLs in ``boom``; counts gets."""

    def __init__(self, routes: dict, boom: set = frozenset()):
        self.routes = routes
        self.boom = boom
        requests: list[str] = []

        def get(url, headers=None):
            requests.append(url)
            if url in boom:
                raise httpx.ConnectError("boom")
            return FakeResp(200, routes.get(url, ""))

        self.get = get
        self.requests = requests


def _j(payload) -> str:
    return json.dumps(payload)


# --------------------------------------------------------------- geocode ----

GEO_URL = ("https://nominatim.openstreetmap.org/search"
           "?postalcode=41451&country=Sweden&format=json&limit=1")


def test_geocode_resolves_and_caches():
    clear_caches()
    session = FakeSession({GEO_URL: _j([{"lat": "57.6914", "lon": "11.9134"}])})
    assert geocode.geocode_postal("41451", session=session) == (57.6914, 11.9134)
    # cache hit: no second request
    geocode.geocode_postal("41451", session=session)
    assert len(session.requests) == 1


def test_geocode_ttl_expiry_re_requests():
    clear_caches()
    session = FakeSession({GEO_URL: _j([{"lat": "57.6914", "lon": "11.9134"}])})
    geocode.geocode_postal("41451", session=session, ttl_seconds=3600)
    # ttl 0 = immediately stale -> re-requests
    geocode.geocode_postal("41451", session=session, ttl_seconds=0)
    assert len(session.requests) == 2


def test_geocode_failure_paths_return_none():
    clear_caches()
    assert geocode.geocode_postal(
        "41451", session=FakeSession({GEO_URL: _j([])})) is None  # 404-ish empty
    assert geocode.geocode_postal(
        "41451", session=FakeSession({}, boom={GEO_URL})) is None  # network
    assert geocode.geocode_postal(
        "41451", session=FakeSession({GEO_URL: "not json"})) is None  # bad json


# ------------------------------------------------------------------ ICA -----

ICA_TOKEN = "https://www.ica.se/e11/public-access-token"
ICA_SEARCH = ("https://apim-pub.gw.ica.se/sverige/digx/storesearch/v1"
              "/searchbyquery?query=*&lon=11.91&lat=57.69&take=3&offset=0"
              "&maxdistance=15000")

ICA_DOCS = {"documents": [
    {"id": 1726, "name": "ICA Nära Heden", "marketingName": "ICA Nära Heden",
     "latitude": "57.70201", "longitude": "11.98227"},
    {"id": 1003913, "marketingName": "ICA Supermarket Majorna",
     "latitude": "57.69", "longitude": "11.91"},
]}


def test_ica_locate_maps_token_and_search():
    session = FakeSession({ICA_TOKEN: _j({"publicAccessToken": "tok-1"}),
                           ICA_SEARCH: _j(ICA_DOCS)})
    stores = ica.locate(57.69, 11.91, session=session)
    assert [s.store_name for s in stores] == [
        "ICA Nära Heden", "ICA Supermarket Majorna"]
    assert stores[0].store_id == "1726" and stores[0].chain == "ica"
    # the search carried the bearer token
    # (FakeSession records only urls; the header path is exercised by 200 flow)


def test_ica_locate_fail_tolerant():
    assert ica.locate(57.69, 11.91,
                      session=FakeSession({}, boom={ICA_TOKEN})) == []
    assert ica.locate(57.69, 11.91,
                      session=FakeSession({ICA_TOKEN: "not json"})) == []


# --------------------------------------------------------------- Willys -----

WILLYS_URL = "https://www.willys.se/axfood/rest/v2/store"

WILLYS_STORES = [
    {"name": "Willys Online", "storeId": 1, "onlineStore": True,
     "geoPoint": {"latitude": 0.0, "longitude": 0.0}},
    {"name": "Willys Majorna", "storeId": 2103,
     "geoPoint": {"latitude": 57.692, "longitude": 11.91}},
    {"name": "Willys Borås Knalleland", "storeId": 2104,
     "geoPoint": {"latitude": 57.7339, "longitude": 12.9331}},
    {"name": "Willys Zero-coord dummy", "storeId": 2105,
     "geoPoint": {"latitude": 0.0, "longitude": 0.0}},
    {"name": "Willys Liseberg", "storeId": 2106,
     "geoPoint": {"latitude": 57.693, "longitude": 11.92}},
]


def test_willys_locate_filters_dummies_and_orders_nearest():
    session = FakeSession({WILLYS_URL: _j(WILLYS_STORES)})
    stores = willys.locate(57.6914, 11.9134, session=session)
    names = [s.store_name for s in stores]
    assert names[0] == "Willys Majorna"          # nearest first
    assert len(stores) == 3                       # nearest 3
    assert "Willys Online" not in names           # onlineStore filtered
    assert "Willys Zero-coord dummy" not in names  # zero-coord filtered
    assert stores[0].store_id == "2103"
    assert stores[0].distance_km < stores[1].distance_km


def test_willys_locate_fail_tolerant():
    assert willys.locate(57.69, 11.91,
                         session=FakeSession({}, boom={WILLYS_URL})) == []


# ----------------------------------------------------------------- Coop -----

COOP_PAGE = "https://www.coop.se/butiker-erbjudanden/"
COOP_LIST = "https://proxy.api.coop.se/external/store/stores?api-version=v1"


def _coop_detail(ledger, lat, lon):
    return {"ledgerAccountNumber": ledger, "name": f"Coop {ledger}",
            "latitude": lat, "longitude": lon}


def _coop_routes():
    return {
        COOP_PAGE: 'window.coopSettings = {"storeApiSubscriptionKey":'
                   '"abc123def4567890abcd"};',
        # Live shape (verified 2026-09-26): the list is WRAPPED in {"stores": [...]}
        COOP_LIST: _j({"stores": [{"storeId": 1, "ledgerAccountNumber": "196183"},
                                  {"storeId": 2, "ledgerAccountNumber": "196184"}]}),
        COOP_LIST.replace("stores?", f"stores/196183?"): _j(_coop_detail("196183", 57.69, 11.91)),
        COOP_LIST.replace("stores?", f"stores/196184?"): _j(_coop_detail("196184", 57.74, 12.93)),
    }


def test_coop_cold_start_fetches_all_details_once_then_caches(tmp_path):
    clear_caches()
    cache = str(tmp_path / "coop_cache.json")
    session = FakeSession(_coop_routes())
    stores = coop.locate(57.6914, 11.9134, session=session, cache_path=cache)
    assert [s.store_id for s in stores] == ["196183", "196184"]
    detail_gets = [u for u in session.requests if "/stores/19" in u]
    assert len(detail_gets) == 2  # cold start: every detail fetched once
    assert (tmp_path / "coop_cache.json").exists()


def test_coop_second_resolve_zero_detail_requests(tmp_path):
    clear_caches()
    cache = str(tmp_path / "coop_cache.json")
    coop.locate(57.69, 11.91, session=FakeSession(_coop_routes()), cache_path=cache)
    # "reboot": a brand-new session with NO routes must still resolve (cache)
    rebooted = FakeSession({})
    stores = coop.locate(57.69, 11.91, session=rebooted, cache_path=cache)
    assert [s.store_id for s in stores] == ["196183", "196184"]
    assert rebooted.requests == []  # zero requests at all from the cache


def test_coop_partial_run_persists_nothing(tmp_path):
    clear_caches()
    cache = str(tmp_path / "coop_cache.json")
    routes = _coop_routes()
    del routes[COOP_LIST.replace("stores?", "stores/196184?")]  # one detail 404s
    session = FakeSession(routes)
    with pytest.raises(RuntimeError, match="incomplete"):
        coop.locate(57.69, 11.91, session=session, cache_path=cache)
    assert not (tmp_path / "coop_cache.json").exists()  # N2: nothing persisted


# ----------------------------------------------------------------- Lidl -----

LIDL_URL = ("https://live.api.schwarz/odj/stores-api/v2/myapi"
            "/stores-frontend/stores?limit=3&offset=0&country_code=SE"
            "&nearby=57.69,11.91:15&expand=GENERAL_HOURS")

LIDL_PAYLOAD = {"meta": {"total": 15}, "items": [
    {"objectNumber": "SE00346", "storeName": "Gbg Nordstan",
     "distance": 0.2,
     "address": {"latitude": 57.70874, "longitude": 11.97095}},
    {"objectNumber": "SE00347", "storeName": "Gbg Majorna",
     "distance": 1.1,
     "address": {"latitude": 57.69, "longitude": 11.91}},
]}


def test_lidl_locate_maps_server_distance():
    session = FakeSession({LIDL_URL: _j(LIDL_PAYLOAD)})
    stores = lidl.locate(57.69, 11.91, session=session)
    assert [s.store_id for s in stores] == ["SE00346", "SE00347"]
    assert stores[0].distance_km == 0.2 and stores[0].chain == "lidl"


def test_lidl_locate_fail_tolerant():
    assert lidl.locate(57.69, 11.91,
                       session=FakeSession({}, boom={LIDL_URL})) == []


# -------------------------------------------------------- resolve_stores ----

def test_resolve_stores_fail_tolerant_per_chain(monkeypatch, tmp_path):
    clear_caches()
    # isolate the Coop file cache — this test must never touch .data/
    monkeypatch.setattr(coop, "default_cache_path",
                        lambda: str(tmp_path / "coop_cache.json"))
    monkeypatch.setattr("src.locator.geocode_postal",
                        lambda pc, session=None: (57.69, 11.91))
    monkeypatch.setitem(CHAIN_LOCATORS, "willys",
                        lambda lat, lon, session=None: (_ for _ in ()).throw(
                            RuntimeError("willys down")))
    result = resolve_stores("41451", session=FakeSession(_coop_routes()))
    assert result["chains"]["willys"]["status"] == "error"
    assert "willys down" in result["chains"]["willys"]["error"]
    assert result["chains"]["coop"]["status"] == "ok"
    assert [s["store_id"] for s in result["chains"]["coop"]["stores"]] == [
        "196183", "196184"]
    assert result["chains"]["ica"]["status"] == "ok"  # no token route -> []
    assert result["chains"]["ica"]["stores"] == []
    assert result["resolved_at"]


def test_resolve_stores_empty_store_list_is_ok_not_error(monkeypatch):
    clear_caches()
    monkeypatch.setattr("src.locator.geocode_postal",
                        lambda pc, session=None: (57.69, 11.91))
    monkeypatch.setitem(CHAIN_LOCATORS, "ica",
                        lambda lat, lon, session=None: [])
    result = resolve_stores("41451", chains=["ica"], session=FakeSession({}))
    assert result["chains"]["ica"]["status"] == "ok"
    assert result["chains"]["ica"]["stores"] == []


def test_resolve_stores_unknown_chain_reported_not_fatal():
    clear_caches()
    result = resolve_stores("41451", chains=["ica", "ica2"],
                            session=FakeSession({}))
    assert result["chains"]["ica2"]["status"] == "error"
    assert "no locator" in result["chains"]["ica2"]["error"]


def test_resolve_stores_geocode_failure_errors_every_chain():
    clear_caches()
    result = resolve_stores("00000", session=FakeSession({}))
    assert all(c["status"] == "error" for c in result["chains"].values())
    assert all("geocode failed" in c["error"] for c in result["chains"].values())


# ------------------------------------------------- resolve-result cache ----

def test_resolve_cache_bounded_ttl_and_size(monkeypatch):
    clear_caches()
    calls = []
    monkeypatch.setattr("src.locator.resolve_stores",
                        lambda pc, chains=None, session=None:
                        calls.append(pc) or {"pc": pc})
    first = resolve_stores_cached("41451")
    second = resolve_stores_cached("41451")
    assert first == second == {"pc": "41451"}  # cached
    assert len(calls) == 1                     # one underlying resolve
    for i in range(200):                       # size bound: evicts oldest > 128
        resolve_stores_cached(f"{10000 + i}")
    from src.locator import _resolve_cache, _RESOLVE_MAX_ENTRIES
    assert len(_resolve_cache) == _RESOLVE_MAX_ENTRIES == 128
    assert "41451" not in _resolve_cache  # oldest evicted
    clear_caches()
    assert not _resolve_cache
