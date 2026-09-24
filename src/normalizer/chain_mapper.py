"""M3 normalizer — CONTRACT C4 (REV6 §4, module M3).

SINGLE executable owner of the running-week predicate and the identity/price mapping
(REV6 invariants N1/N3/N4): the same (chain, raw, week_key) always yields the same list.

THIS module is the only place that derives the week window from ``week_key`` via ISO
arithmetic and drops out-of-week offers (valid_to < week_start or valid_from > week_end).
Offers-db (M4) and the planner read (C-OW) do NOT re-filter — see offers_db/store.py.

PURE: no I/O, no wall-clock. Deterministic for the same inputs.
"""
from __future__ import annotations

from datetime import date, timedelta

try:  # app/test context: repo root on path (MC 1355.5 boot ingest imports src.*)
    from src.config import CHAIN_MAP, CHAIN_DEFAULT
except ImportError:  # motor context: src/ itself on path (run_motor.py)
    from config import CHAIN_MAP, CHAIN_DEFAULT


def iso_week_bounds(week_key: str) -> tuple[date, date]:
    """Return (Monday, Sunday) of the ISO week encoded as ``YYYY-Www``.

    Uses the Jan-4 rule: the ISO week containing Jan 4 of the year; Monday start.
    """
    year_s, week_s = week_key.split("-W")
    year, week = int(year_s), int(week_s)
    jan4 = date(year, 1, 4)
    monday_of_week1 = jan4 - timedelta(days=jan4.isoweekday() - 1)
    monday = monday_of_week1 + timedelta(weeks=week - 1)
    return monday, monday + timedelta(days=6)


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _to_cents(price, round_cents=None) -> int | None:
    try:
        cents = int(round(float(price) * 100))
    except (TypeError, ValueError):
        return None
    if round_cents:
        cents = int(round(cents / round_cents) * round_cents)
    return cents


def normalize(chain: str, raw: dict, week_key: str) -> list[dict]:
    """Map one raw feed dictionary into in-week NormalizedOffers for ``chain``.

    raw:  {"grocer_id": str, "entries": [ RawOffer ... ]}
        RawOffer = {external_id, name, price, unit, valid_from, valid_to}
    Returns 0..n normalized dicts:
        {grocer_id, external_id, week_key, name, price, unit, valid_from, valid_to}
    where ``price`` is integer cents (chain round applied) and only offers whose
    window overlaps the running ISO week survive.
    """
    rule = CHAIN_MAP.get(chain, CHAIN_DEFAULT)
    week_start, week_end = iso_week_bounds(week_key)
    grocer_id = raw.get("grocer_id", chain)
    out: list[dict] = []
    for entry in raw.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        ext_id = entry.get("external_id")
        name = entry.get("name")
        if ext_id is None or name is None:
            continue  # identity required (C2 also drops, defensive here)
        cents = _to_cents(entry.get("price"), rule["round_cents"])
        if cents is None:
            continue  # unparsable price -> drop, not fatal
        vf = _parse_date(entry.get("valid_from"))
        vt = _parse_date(entry.get("valid_to"))
        if vf is None or vt is None:
            continue  # unparsable dates -> drop (REV6 §7: parse dates defensively)
        if vt < week_start or vf > week_end:
            continue  # outside the running week -> the single filter owner
        out.append({
            "grocer_id": grocer_id,
            "external_id": rule["id_prefix"] + ext_id,
            "week_key": week_key,
            "name": name,
            "price": cents,
            "unit": entry.get("unit"),
            "valid_from": vf.isoformat(),
            "valid_to": vt.isoformat(),
        })
    return out
