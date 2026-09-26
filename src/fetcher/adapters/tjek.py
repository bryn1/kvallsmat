"""M2 fetcher adapter — Willys + Coop via the Tjek squid API (MC 1355.10).

Both chains publish their veckoblad through Tjek (tjek.com, ex-ShopGun) and
Tjek's PUBLIC squid API serves the leaflet offers as structured JSON, no auth
(audit T7a, MC 1355.8). Replaces the fictional ``{base}/veckans-extrapris``
pull for willys/coop. Honours the RawFeed contract: any network error,
non-200 response or unparsable record yields no entries, never a raise.

Observed API shape (live, 2026-09-26):
  GET /v2/catalogs?dealer_id=<id>  -> [ {id, label, offer_count, page_count,
      run_from, run_till, publication_date, ...} ]  (per-store catalogs)
  GET /v2/catalogs/{id}/hotspots   -> [ {id, heading, type, offer: {
      id, heading, pricing: {price, currency, pre_price},
      quantity: {unit: {symbol, si: {symbol, factor}}, size: {from, to}},
      run_from, run_till}, run_from (epoch), run_till (epoch), ...} ]

The offer-level ``run_from``/``run_till`` are ISO strings; the hotspot-level
ones are epoch ints — the adapter reads the offer-level ones.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ._common import week_start

_CATALOGS_PATH = "/v2/catalogs"
# A dealer listing can rotate the current leaflet out before it expires
# (observed for Coop, MC 1355.10): accept the nearest future catalog within
# this many hours so the grocer serves the upcoming week instead of nothing.
GRACE_HOURS = 48


def _parse_iso(value) -> datetime | None:
    """Parse Tjek's ISO run timestamps ("2026-09-20T22:00:00+0000")."""
    try:
        return datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%S%z")
    except (ValueError, TypeError):
        return None


def pick_catalog(catalogs, now: datetime | None = None) -> dict | None:
    """Pick the CURRENT catalog: run_from/run_till covers ``now``.

    When several cover now, the newest publish wins (publication_date, then
    run_from as tiebreaker). Observed reality (MC 1355.10 live probe): a
    dealer listing can rotate the current leaflet out early — Coop's listing
    held ONLY next week's catalogs mid-week — so when nothing covers now we
    fall back to the nearest catalog starting within GRACE_HOURS, rather than
    serving an empty week. Expired-only listings still yield None.
    """
    now = now or datetime.now(timezone.utc)
    covering, near = [], []
    for cat in catalogs if isinstance(catalogs, list) else []:
        if not isinstance(cat, dict):
            continue
        start = _parse_iso(cat.get("run_from"))
        end = _parse_iso(cat.get("run_till"))
        if start is None or end is None:
            continue
        publish = _parse_iso(cat.get("publication_date")) or start
        if start <= now <= end:
            covering.append((publish, start, cat))
        elif timedelta(hours=GRACE_HOURS) >= start - now > timedelta(0):
            near.append((start, publish, cat))
    if covering:
        covering.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return covering[0][2]
    if near:
        near.sort(key=lambda t: (t[0], t[1]))
        return near[0][2]
    return None


def _unit(quantity: dict) -> str:
    """Comparison unit from quantity.unit + its SI factor ("g"->"kg", "pcs"->"st")."""
    unit = quantity.get("unit") if isinstance(quantity, dict) else None
    if not isinstance(unit, dict):
        return "st"
    si = unit.get("si") or {}
    symbol = str(si.get("symbol") or unit.get("symbol") or "st")
    return "st" if symbol == "pcs" else symbol


def parse_hotspot(hotspot) -> dict | None:
    """One hotspot record -> RawOffer-shaped dict, or None when unusable."""
    if not isinstance(hotspot, dict):
        return None
    offer = hotspot.get("offer")
    if not isinstance(offer, dict):
        offer = hotspot  # tolerate a flat record
    pricing = offer.get("pricing") or {}
    currency = pricing.get("currency")
    if currency is not None and currency != "SEK":
        return None  # wrong currency -> drop, not fatal
    try:
        price = float(pricing.get("price"))
    except (TypeError, ValueError):
        return None  # missing/unparsable price -> drop the offer
    ext_id = offer.get("id") or hotspot.get("id")
    name = offer.get("heading") or hotspot.get("heading")
    if not ext_id or not name:
        return None
    start = str(offer.get("run_from") or "")[:10]
    end = str(offer.get("run_till") or "")[:10]
    return {
        # MC 1355.7 (T5 attack 5): bare id — chain_mapper owns the CHAIN_MAP
        # id_prefix, so the final external_id carries exactly one prefix.
        "external_id": str(ext_id),
        "name": str(name),
        "price": price,
        "unit": _unit(offer.get("quantity") or {}),
        "valid_from": start,
        "valid_to": end,
    }


def parse_hotspots(records, week_start: str = "") -> list[dict]:
    """Hotspot list -> RawOffer entries (unparsable records dropped)."""
    entries = []
    for rec in records if isinstance(records, list) else []:
        entry = parse_hotspot(rec)
        if entry is None:
            continue
        if not entry["valid_from"]:
            entry["valid_from"] = week_start
        entries.append(entry)
    return entries


def _dealer_urls(endpoint: str) -> tuple[str, str | None]:
    """(catalogs_base_url, dealer_id) from a configured dealer endpoint."""
    base, _, query = endpoint.partition("?")
    dealer_id = None
    for part in query.split("&"):
        key, _, value = part.partition("=")
        if key == "dealer_id":
            dealer_id = value
    return base.rstrip("/") or _CATALOGS_PATH, dealer_id


def pull(grocer_cfg, week_key: str, session=None) -> dict:
    """RawFeed pull for a Tjek dealer: current catalog -> hotspots, fail-tolerant."""
    import httpx

    from ._common import get_text

    empty = {"grocer_id": grocer_cfg.grocer_id, "week_key": week_key, "entries": []}
    base, dealer_id = _dealer_urls(grocer_cfg.endpoint)
    if not dealer_id:
        return empty
    headers = dict(grocer_cfg.headers or {})
    own = session is None
    client = session if session is not None else httpx.Client()
    try:
        import json

        catalogs_raw = get_text(client, f"{base}?dealer_id={dealer_id}", headers)
        if catalogs_raw is None:
            return empty
        try:
            catalogs = json.loads(catalogs_raw)
        except ValueError:
            return empty
        catalog = pick_catalog(catalogs)
        if catalog is None or not catalog.get("id"):
            return empty
        hotspots_raw = get_text(
            client, f"{base}/{catalog['id']}/hotspots", headers)
        if hotspots_raw is None:
            return empty
        try:
            records = json.loads(hotspots_raw)
        except ValueError:
            return empty
    finally:
        if own and hasattr(client, "close"):
            client.close()
    entries = parse_hotspots(records, week_start(week_key))
    return {"grocer_id": grocer_cfg.grocer_id, "week_key": week_key,
            "entries": entries}


def pull_store_scoped(grocer_cfg, week_key: str, store_id: str,
                      store_label: str, session=None) -> dict:
    """Store-scoped RawFeed pull for ONE physical store (MC 1355.16, T10b §3).

    Tjek catalogs are labeled per store and the catalog list carries
    ``store_id: null`` (T10a §2b), so the catalog is matched on the store's
    label string (casefold + strip). RULE 1 (T10b §3 / T10d N1): the
    store-scoped entries are stamped ``external_id = f"{store_id}:{id}"`` AND
    ``store_id`` — they can never collide with (or overwrite) a chain-level
    bare-id row. An unmatched store yields an empty feed and is LOGGED, never
    silently dropped (T10b §10-F9).
    """
    import httpx
    import json
    import logging

    from ._common import get_text

    logger = logging.getLogger(__name__)
    empty = {"grocer_id": grocer_cfg.grocer_id, "week_key": week_key,
             "entries": []}
    if not store_id or not store_label:
        raise ValueError("pull_store_scoped requires store_id and store_label")
    base, dealer_id = _dealer_urls(grocer_cfg.endpoint)
    if not dealer_id:
        return empty
    headers = dict(grocer_cfg.headers or {})
    own = session is None
    client = session if session is not None else httpx.Client()
    try:
        catalogs_raw = get_text(client, f"{base}?dealer_id={dealer_id}", headers)
        if catalogs_raw is None:
            return empty
        try:
            catalogs = json.loads(catalogs_raw)
        except ValueError:
            return empty
        catalog = _catalog_for_store(catalogs, store_label)
        if catalog is None:
            # loud, not silent: the store has no Tjek catalog this week
            logger.warning(
                "no Tjek catalog labeled %r for dealer %s — store %s falls "
                "back to chain-level offers", store_label, dealer_id, store_id)
            return empty
        hotspots_raw = get_text(
            client, f"{base}/{catalog['id']}/hotspots", headers)
        if hotspots_raw is None:
            return empty
        try:
            records = json.loads(hotspots_raw)
        except ValueError:
            return empty
    finally:
        if own and hasattr(client, "close"):
            client.close()
    entries = parse_hotspots(records, week_start(week_key))
    for entry in entries:
        # RULE 1: store-scoped ids are ALWAYS prefixed — asserted, never assumed.
        entry["external_id"] = f"{store_id}:{entry['external_id']}"
        entry["store_id"] = str(store_id)
    return {"grocer_id": grocer_cfg.grocer_id, "week_key": week_key,
            "entries": entries}


def _catalog_for_store(catalogs, store_label: str) -> dict | None:
    """The current catalog whose label matches the store name (casefold+strip)."""
    wanted = store_label.casefold().strip()
    current = pick_catalog(catalogs)
    if current is not None and _label_matches(current, wanted):
        return current
    # The current dealer-wide catalog may belong to ANOTHER store; look for a
    # covering catalog labeled for THIS store specifically.
    now = datetime.now(timezone.utc)
    for cat in catalogs if isinstance(catalogs, list) else []:
        if isinstance(cat, dict) and _label_matches(cat, wanted):
            start = _parse_iso(cat.get("run_from"))
            end = _parse_iso(cat.get("run_till"))
            if start is not None and end is not None and start <= now <= end:
                return cat
    return None


def _label_matches(catalog: dict, wanted: str) -> bool:
    label = catalog.get("label")
    return isinstance(label, str) and label.casefold().strip() == wanted
