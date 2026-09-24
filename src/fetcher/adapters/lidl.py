"""M2 fetcher adapter — Lidl (MC 1355.4).

Parses the real offers from https://www.lidl.se/c/erbjudanden: the index page
links campaign pages (``/c/<slug>/a<id>``), and each campaign page embeds one
HTML-escaped JSON blob per product tile in a ``data-grid-data`` attribute with
``regionsPrices`` -> ``currentLidlPlusPrice`` -> ``price`` (audit T2 §4).
Replaces the fictional ``{base}/veckans-extrapris`` JSON API. Honours the
RawFeed contract: parse problems yield no entries, never raise.
"""
from __future__ import annotations

import html as html_mod
import json
import re

from ._common import get_text, week_start

INDEX_PATH = "/c/erbjudanden"
_CAMPAIGN_RE = re.compile(r'href="(/c/[a-z0-9-]+/a\d+)"')
_TILE_RE = re.compile(r'data-grid-data="([^"]*)"')


def find_campaign_urls(index_html: str) -> list[str]:
    """Deduplicated campaign paths from the offers index page, in page order."""
    seen: set[str] = set()
    urls = []
    for m in _CAMPAIGN_RE.finditer(index_html):
        path = m.group(1)
        if path not in seen:
            seen.add(path)
            urls.append(path)
    return urls


def _tile_price(tile: dict) -> tuple | None:
    """(price, unit, valid_from, valid_to, regular_price) from a tile, or None.

    ``regular_price`` is the tile's ``price.discount.deletedPrice`` (T2 §4) —
    the pre-campaign reference price — or None when the tile carries none.
    """
    regions = tile.get("regionsPrices")
    if not isinstance(regions, dict) or not regions:
        return None
    for region in sorted(regions):
        plus = (regions[region] or {}).get("currentLidlPlusPrice") or {}
        price = plus.get("price") or {}
        try:
            amount = float(price.get("price"))
        except (TypeError, ValueError):
            continue  # missing/unparsable price -> drop the tile
        try:
            regular = float((price.get("discount") or {}).get("deletedPrice"))
        except (TypeError, ValueError):
            regular = None
        base = price.get("basePrice") or {}
        # basePrice.text is "/kg" or a full comparison string like "39,80 kr/kg"
        m = re.search(r"/\s*([A-Za-z]+)\s*$", str(base.get("text") or ""))
        unit = m.group(1) if m else "st"
        start = str(price.get("startDate") or "")[:10]
        end = str(price.get("endDate") or "")[:10]
        return amount, unit, start, end, regular
    return None


def parse_lidl_campaign(campaign_html: str, week_start: str = "") -> list[dict]:
    """Parse one campaign page into RawOffer-shaped dicts (no network)."""
    entries = []
    for m in _TILE_RE.finditer(campaign_html):
        try:
            tile = json.loads(html_mod.unescape(m.group(1)))
        except ValueError:
            continue  # unparsable blob -> drop the tile, not fatal
        if not isinstance(tile, dict):
            continue
        parsed = _tile_price(tile)
        title = tile.get("title")
        product_id = tile.get("productId")
        if parsed is None or not title or not product_id:
            continue
        price, unit, start, end, regular = parsed
        # MC 1355.7 (T5 attack 5): bare product id — chain_mapper owns the prefix.
        entries.append({
            "external_id": str(product_id),
            "name": str(title),
            "price": price,
            "unit": unit,
            "valid_from": start or week_start,
            "valid_to": end,
        })
        if regular is not None:
            entries[-1]["regular_price"] = regular
    return entries


def pull(grocer_cfg, week_key: str, session=None) -> dict:
    """RawFeed pull for Lidl: index page -> campaign pages, fail-tolerant."""
    import httpx

    base = grocer_cfg.endpoint.rstrip("/")
    origin = base.split(INDEX_PATH)[0] or "https://www.lidl.se"
    if not base.endswith(INDEX_PATH):
        base = base + INDEX_PATH
    headers = dict(grocer_cfg.headers or {})
    own = session is None
    client = session if session is not None else httpx.Client()
    try:
        index_html = get_text(client, base, headers)
        if index_html is None:
            return {"grocer_id": grocer_cfg.grocer_id, "week_key": week_key,
                    "entries": []}
        entries = []
        for path in find_campaign_urls(index_html):
            page = get_text(client, origin + path, headers)
            if page is not None:
                entries.extend(parse_lidl_campaign(page, week_start(week_key)))
    finally:
        if own and hasattr(client, "close"):
            client.close()
    return {"grocer_id": grocer_cfg.grocer_id, "week_key": week_key,
            "entries": entries}
