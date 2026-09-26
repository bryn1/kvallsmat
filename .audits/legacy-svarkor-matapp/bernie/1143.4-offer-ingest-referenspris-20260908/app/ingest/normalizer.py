"""app.ingest.normalizer — RawOffer -> NormalizedOffer for the offer-ingest line (Phase 4 T3).

CONTRACT C4 (POC M3 normalizer.chain_mapper), EXTENDED to carry the reference price
(closure-gap 1, map line 71: "referenspris/rabatt måste bäras genom RawOffer→NormalizedOffer→Offer")
and the PER-INGREDIENT EXTRAPRIS FLAG.

The per-ingredient extrapris flag is COMPUTED HERE (in the normalisation step), NOT stored
in the DB (map open-question 2, line 224: "Per-ingrediens-flaggan lagras var? Föreslås i
normaliserings-steget (T3), ej i DB"). A normalized offer is 'extrapris' if, and only if,
it has a reference price STRICTLY greater than the sale price (regular_price_cents >
price_cents) — i.e. a measurable discount. Offers with no reference price or no discount
are NOT extrapris (so a normalizer that drops the reference price fails to flag anything).

SINGLE executable owner of the running-week predicate + identity/price mapping (REV6
N1/N3/N4) — same as POC chain_mapper; deterministic for the same inputs, PURE, no I/O.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.config import CHAIN_DEFAULT, CHAIN_MAP


def iso_week_bounds(week_key: str) -> tuple[date, date]:
    """Return (Monday, Sunday) of the ISO week encoded as ``YYYY-Www`` (Jan-4 rule)."""
    year_s, week_s = week_key.split("-W")
    year, week = int(year_s), int(week_s)
    jan4 = date(year, 1, 4)
    monday_of_week1 = jan4 - timedelta(days=jan4.isoweekday() - 1)
    monday = monday_of_week1 + timedelta(weeks=week - 1)
    return monday, monday + timedelta(days=6)


def _parse_date(value) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def normalize(chain: str, raw: dict, week_key: str) -> list[dict]:
    """Map one raw feed dictionary into in-week NormalizedOffers for ``chain``.

    raw:  {"grocer_id": str, "entries": [ RawOffer ... ]}
        RawOffer = {external_id, name, price, regular_price_cents, unit, valid_from, valid_to}
    Returns 0..n normalized dicts:
        {grocer_id, external_id, week_key, name,
         price, regular_price_cents, savings_cents, is_extraprice,
         unit, valid_from, valid_to}
    where prices are integer cents (chain round applied), and only offers whose window
    overlaps the running ISO week survive.
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
            continue  # identity required
        cents = entry.get("price")
        if cents is None:
            continue
        if rule["round_cents"]:
            cents = int(round(cents / rule["round_cents"]) * rule["round_cents"])
        vf = _parse_date(entry.get("valid_from"))
        vt = _parse_date(entry.get("valid_to"))
        if vf is None or vt is None:
            continue  # unparsable dates -> drop
        if vt < week_start or vf > week_end:
            continue  # outside the running week -> single filter owner

        regular_cents = entry.get("regular_price_cents")
        # Reference price kept EXACT (not chain-rounded): it is the advertised ordinary
        # price, and preserving it raw keeps savings_cents precise for Phase 6's ratio +
        # kron-savings measurement. Only the sale price follows the chain round rule (POC).
        savings_cents = None
        if regular_cents is not None:
            savings_cents = max(regular_cents - cents, 0)
        # PER-INGREDIENT EXTRAPRIS FLAG (normalisation step, not DB): measurable discount
        # iff reference price strictly exceeds sale price.
        is_extraprice = bool(regular_cents is not None and regular_cents > cents)

        out.append({
            "grocer_id": grocer_id,
            "external_id": rule["id_prefix"] + ext_id,
            "week_key": week_key,
            "name": name,
            "price": cents,
            "regular_price_cents": regular_cents,
            "savings_cents": savings_cents,
            "is_extraprice": is_extraprice,
            "unit": entry.get("unit"),
            "valid_from": vf.isoformat(),
            "valid_to": vt.isoformat(),
        })
    return out
