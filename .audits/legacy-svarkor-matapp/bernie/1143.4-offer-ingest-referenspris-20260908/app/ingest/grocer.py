"""app.ingest.grocer — feed-fetch for the matapp offer-ingest line (Phase 4 T3).

CONTRACT C2 part 1 (POC M2 fetcher.grocer), EXTENDED so RawOffer now carries the
seller's advertised REFERENCE price (closure-gap 1, PHASE0.md §A). The willys feed
bears BOTH the sale price and the reference price (comparePrice / lowestHistoricalPrice /
conditionLabel — VERIFIED live, PHASE0-research Q4), so the offer-ingest line can persist
regular_price_cents and let Phase 6 measure the >=50%-extrapris ratio.

pull_grocer(grocer_cfg, week_key[, session]) -> RawFeed
  One HTTP pull per grocer to "{base}/veckans-extrapris". FAIL-TOLERANT per REV6 §2/§6:
  a single grocer's HTTP error, bad JSON, or malformed entries never fail the whole run —
  they yield an empty feed (entries=[]) instead of raising. Malformed entries are dropped,
  not fatal.

RawFeed = {"grocer_id", "week_key", "entries": [RawOffer ...]}
RawOffer = {external_id, name, price, regular_price_cents, unit, valid_from, valid_to}
  price / regular_price_cents are integer cents here; the normalizer (C4) owns identity
  mapping. regular_price_cents is None when the feed offers no reference price.

HAL-seam: ``session`` is injected for tests and is an httpx-like object exposing
``get(url, headers=None)`` returning an object with ``.status_code`` and ``.json()``.
The host-mock for tests is exactly this injected session (map line 72); the device is the
real chain API.
"""
from __future__ import annotations

import re

import httpx  # runtime dep (DA FIX-1: httpx pinned in requirements.txt, NOT dev-only)

from app.config import GrocerConfig

_REQUIRED = ("external_id", "name", "price", "valid_from", "valid_to")

# comparePrice arrives as a Swedish-formatted string, e.g. "71,29 kr" (comma decimal).
_CP_RE = re.compile(r"([0-9]+)(?:[,.]([0-9]{1,2}))?\s*(?:kr)?", re.IGNORECASE)


def parse_swedish_kr(value) -> int | None:
    """Parse a Swedish price string/number like '71,29 kr' or 66.9 into integer cents.

    Returns None for unparsable input (caller treats as 'no reference price').
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(round(float(value) * 100))
    m = _CP_RE.match(str(value).strip())
    if not m:
        return None
    whole = int(m.group(1))
    frac = m.group(2) or "0"
    frac = (frac + "00")[:2]  # right-pad to 2 digits for cents
    return whole * 100 + int(frac)


def _raw_offer(e: dict) -> dict | None:
    """Extract a clean RawOffer dict from one feed entry, carrying reference price.

    Reference price wins in this order: explicit 'regular_price_cents' (tests/synthetic),
    then comparePrice (willys VERIFIED), then lowestHistoricalPrice.value. Falling back to
    lowestHistorical is a documented OPS decision — comparePrice absent -> historical low
    is the best available proxy for "ordinary price".
    """
    if not all(e.get(k) is not None for k in _REQUIRED):
        return None
    try:
        price_cents = int(round(float(e["price"]) * 100))
    except (TypeError, ValueError):
        return None
    if price_cents < 0:
        return None
    regular_cents = e.get("regular_price_cents")
    if regular_cents is None:
        regular_cents = parse_swedish_kr(e.get("comparePrice"))
    if regular_cents is None:
        regular_cents = parse_swedish_kr(
            (e.get("lowestHistoricalPrice") or {}).get("value")
        )
    return {
        "external_id": e["external_id"],
        "name": e["name"],
        "price": price_cents,
        "regular_price_cents": regular_cents,
        "unit": e.get("unit"),
        "valid_from": e["valid_from"],
        "valid_to": e["valid_to"],
    }


def pull_grocer(grocer_cfg: GrocerConfig, week_key: str, session=None) -> dict:
    base = grocer_cfg.endpoint.rstrip("/")
    url = f"{base}/veckans-extrapris"
    headers = dict(grocer_cfg.headers or {})
    if grocer_cfg.token:
        headers["Authorization"] = f"Bearer {grocer_cfg.token}"

    own_session = session is None
    client = session if session is not None else httpx.Client()
    try:
        resp = client.get(url, headers=headers)
        if resp.status_code != 200:
            return {"grocer_id": grocer_cfg.grocer_id, "week_key": week_key, "entries": []}
        payload = resp.json()
    except Exception:
        # network error, timeout, bad JSON -> fail-tolerant empty feed
        return {"grocer_id": grocer_cfg.grocer_id, "week_key": week_key, "entries": []}
    finally:
        if own_session and hasattr(client, "close"):
            client.close()

    entries = payload.get("offers") or [] if isinstance(payload, dict) else []
    clean = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        ro = _raw_offer(e)
        if ro is None:
            continue
        clean.append(ro)
    return {"grocer_id": grocer_cfg.grocer_id, "week_key": week_key, "entries": clean}
