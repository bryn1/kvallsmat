"""RED tests for M3 normalizer (CONTRACT C4): chain-aware mapping + running-week owner."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from normalizer.chain_mapper import normalize, iso_week_bounds


RAW = {
    "grocer_id": "ica",
    "week_key": "2026-W34",
    "entries": [
        {"external_id": "e1", "name": "Bröd", "price": 12.5, "unit": "st",
         "valid_from": "2026-08-17", "valid_to": "2026-08-23"},
        {"external_id": "e2", "name": "Gammalt", "price": 9.0, "unit": "st",
         "valid_from": "2026-08-01", "valid_to": "2026-08-09"},      # outside week 34
        {"external_id": "e3", "name": "Framtida", "price": 40.0, "unit": "st",
         "valid_from": "2026-09-01", "valid_to": "2026-09-07"},      # outside week 34
    ],
}


def test_iso_week_bounds():
    start, end = iso_week_bounds("2026-W34")
    assert (start.isoformat(), end.isoformat()) == ("2026-08-17", "2026-08-23")


def test_normalize_keeps_only_in_week_offers():
    res = normalize("ica", RAW, "2026-W34")
    assert len(res) == 1
    assert res[0]["external_id"] == "ica-e1"      # ica chain -> "ica-" prefix
    assert res[0]["week_key"] == "2026-W34"
    assert res[0]["grocer_id"] == "ica"


def test_normalize_converts_price_to_cents_and_rounds_per_chain():
    # ica chain has no rounding -> 12.5 SEK = 1250 cents
    res = normalize("ica", RAW, "2026-W34")
    assert res[0]["price"] == 1250


def test_normalize_chain_edge_touching_bounds_included():
    raw = {"grocer_id": "willys", "week_key": "2026-W34", "entries": [
        # ends exactly on week_end (Sunday 08-23) -> keep
        {"external_id": "edge-end", "name": "P", "price": 5.0, "unit": "st",
         "valid_from": "2026-08-17", "valid_to": "2026-08-23"},
        # starts exactly on week_start (Monday 08-17) -> keep
        {"external_id": "edge-start", "name": "Q", "price": 6.0, "unit": "st",
         "valid_from": "2026-08-17", "valid_to": "2026-08-23"},
    ]}
    res = normalize("willys", raw, "2026-W34")
    assert len(res) == 2


def test_normalize_unknown_chain_identity_no_prefix():
    raw = {"grocer_id": "lidl", "week_key": "2026-W34", "entries": [
        {"external_id": "x", "name": "Sak", "price": 7.25, "unit": "st",
         "valid_from": "2026-08-17", "valid_to": "2026-08-23"},
    ]}
    res = normalize("lidl", raw, "2026-W34")
    assert len(res) == 1
    assert res[0]["external_id"] == "x"          # unknown chain -> no prefix
    assert res[0]["price"] == 725                # no rounding -> exact cents


def test_normalize_is_pure_deterministic():
    a = normalize("ica", RAW, "2026-W34")
    b = normalize("ica", RAW, "2026-W34")
    assert a == b
