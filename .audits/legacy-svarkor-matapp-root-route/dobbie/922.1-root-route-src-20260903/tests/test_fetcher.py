"""RED tests for M2 fetcher (CONTRACT C2): pull_grocer + aggregate + fail-tolerance."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from config import GrocerConfig
from fetcher.grocer import pull_grocer
from fetcher.aggregate import aggregate


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload
        self.status_code = status_code
    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    def __init__(self, response, side_effect=None):
        self._response = response
        self._calls = []
        self._side_effect = side_effect
    def get(self, url, headers=None):
        self._calls.append((url, headers))
        if self._side_effect is not None:
            return self._side_effect()
        return self._response


def make_grocer():
    return GrocerConfig(grocer_id="ica", endpoint="https://api.ica.se", token="sekret")


def test_pull_grocer_success_parses_entries():
    sess = FakeSession(FakeResponse({"offers": [
        {"external_id": "e1", "name": "Bröd", "price": 12.5, "unit": "st",
         "valid_from": "2026-08-17", "valid_to": "2026-08-23"},
        {"external_id": "e2", "name": "Mjölk", "price": 18.0, "unit": "st",
         "valid_from": "2026-08-17", "valid_to": "2026-08-23"},
    ]}))
    feed = pull_grocer(make_grocer(), "2026-W34", session=sess)
    assert feed["grocer_id"] == "ica"
    assert feed["week_key"] == "2026-W34"
    assert len(feed["entries"]) == 2
    assert feed["entries"][0]["external_id"] == "e1"
    assert feed["entries"][0]["price"] == 12.5


def test_pull_grocer_requests_extrapris_url_with_token_and_headers():
    sess = FakeSession(FakeResponse({"offers": []}))
    g = GrocerConfig(grocer_id="willys", endpoint="https://api.willys.se",
                     token="tk", headers={"X-Custom": "1"})
    pull_grocer(g, "2026-W34", session=sess)
    url, headers = sess._calls[0]
    assert url == "https://api.willys.se/veckans-extrapris"
    assert headers["Authorization"] == "Bearer tk"
    assert headers["X-Custom"] == "1"


def test_pull_grocer_drops_malformed_entries_not_fatal():
    sess = FakeSession(FakeResponse({"offers": [
        {"external_id": "e1", "name": "Ok", "price": 10.0, "unit": "st",
         "valid_from": "2026-08-17", "valid_to": "2026-08-23"},
        {"external_id": None, "name": "missing id"},              # malformed
        {"external_id": "e3", "name": "Bad price", "price": "abc",
         "unit": "st", "valid_from": "2026-08-17", "valid_to": "2026-08-23"},  # malformed
    ]}))
    feed = pull_grocer(make_grocer(), "2026-W34", session=sess)
    assert len(feed["entries"]) == 1
    assert feed["entries"][0]["external_id"] == "e1"


def test_pull_grocer_http_failure_returns_empty_feed_not_raise():
    sess = FakeSession(FakeResponse(status_code=500))
    feed = pull_grocer(make_grocer(), "2026-W34", session=sess)
    assert feed["grocer_id"] == "ica"
    assert feed["entries"] == []


def test_pull_grocer_connect_error_returns_empty_feed_not_raise():
    class BoomSession:
        def get(self, url, headers=None):
            raise ConnectionError("down")
    feed = pull_grocer(make_grocer(), "2026-W34", session=BoomSession())
    assert feed["entries"] == []


def test_pull_grocer_bad_json_returns_empty_feed_not_raise():
    sess = FakeSession(FakeResponse())   # .json() raises
    feed = pull_grocer(make_grocer(), "2026-W34", session=sess)
    assert feed["entries"] == []


def test_aggregate_merges_feeds_and_drops_bad():
    f1 = {"grocer_id": "willys", "week_key": "2026-W34", "entries": [{"external_id": "a", "name": "A", "price": 1.0, "unit": "st", "valid_from": "2026-08-17", "valid_to": "2026-08-23"}]}
    f2 = {"grocer_id": "ica", "week_key": "2026-W34", "entries": [None, {"external_id": "b", "name": "B", "price": 2.0, "unit": "st", "valid_from": "2026-08-17", "valid_to": "2026-08-23"}]}
    out = aggregate([f1, f2])
    assert out["week_key"] == "2026-W34"
    ids = [e["external_id"] for e in out["entries"]]
    assert ids == ["a", "b"]
