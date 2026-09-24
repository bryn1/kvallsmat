"""M2 fetcher adapter — ICA (MC 1355.4).

Parses the real weekly offers embedded server-side in
https://www.ica.se/erbjudanden/ (window.__INITIAL_DATA__ -> offers.weeklyOffers).
Replaces the fictional ``{base}/veckans-extrapris`` JSON API (audit T1 P1-3 /
T2 §1). Honours the RawFeed contract: parse problems yield no entries, never
raise; the network wrapper in pull_ica is fail-tolerant like pull_grocer.
"""
from __future__ import annotations

import json
import re

from ._common import get_text, week_start

MARKER = "window.__INITIAL_DATA__"


def sanitize_js_object(blob: str) -> str:
    """Make ICA's raw JS object literal parseable as strict JSON.

    The page ships bare ``undefined`` values and ``new Map([...])`` literals;
    replace them (undefined -> null, new Map(...) -> {}) before json.loads.
    """
    sanitized = re.sub(r"new Map\(\[[^\]]*\]\)", "{}", blob)
    sanitized = re.sub(r"\bundefined\b", "null", sanitized)
    return sanitized


def _extract_blob(html: str) -> str | None:
    """Return the balanced-brace object literal after the INITIAL_DATA marker."""
    idx = html.find(MARKER)
    if idx < 0:
        return None
    start = html.find("{", idx)
    if start < 0:
        return None
    depth = 0
    instr = None
    i = start
    while i < len(html):
        c = html[i]
        if instr:
            if c == "\\":
                i += 2
                continue
            if c == instr:
                instr = None
        elif c in "\"'":
            instr = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return html[start:i + 1]
        i += 1
    return None


def _price_and_unit(item: dict) -> tuple | None:
    """(price, unit) from parsedMechanics, falling back to mechanicInfo text."""
    mech = item.get("parsedMechanics")
    if isinstance(mech, dict) and mech.get("value2"):
        try:
            price = float(mech["value2"])
        except (TypeError, ValueError):
            price = None
        if price is not None:
            unit = str(mech.get("value4") or "/st").strip("/").strip() or "st"
            return price, unit
    info = item.get("details", {}).get("mechanicInfo") or ""
    m = re.match(r"\s*(\d+(?:[.,]\d+)?)\s*kr\s*/\s*(\S+)", info)
    if m:
        return float(m.group(1).replace(",", ".")), m.group(2)
    return None


def parse_ica_offers(html: str, week_start: str = "") -> list[dict]:
    """Parse the erbjudanden page into RawOffer-shaped dicts (no network)."""
    blob = _extract_blob(html)
    if not blob:
        return []
    try:
        data = json.loads(sanitize_js_object(blob))
    except (ValueError, RecursionError):
        return []
    offers = data.get("offers") or {}
    items = offers.get("weeklyOffers") if isinstance(offers, dict) else None
    if not isinstance(items, list):
        return []
    entries = []
    for item in items:
        if not isinstance(item, dict):
            continue
        details = item.get("details") or {}
        ext_id = item.get("id")
        name = " ".join(p for p in (details.get("brand"), details.get("name")) if p)
        price_unit = _price_and_unit(item)
        valid_to = item.get("validTo")
        if not ext_id or not name or price_unit is None or not valid_to:
            continue  # malformed entry -> drop, not fatal
        price, unit = price_unit
        entries.append({
            "external_id": f"ica-{ext_id}",
            "name": name,
            "price": price,
            "unit": unit,
            "valid_from": week_start or str(valid_to)[:10],
            "valid_to": str(valid_to)[:10],
        })
    return entries


def pull(grocer_cfg, week_key: str, session=None) -> dict:
    """RawFeed pull for ICA: one GET of the erbjudanden page, fail-tolerant."""
    import httpx

    url = grocer_cfg.endpoint.rstrip("/") + "/"
    own = session is None
    client = session if session is not None else httpx.Client()
    try:
        html = get_text(client, url, dict(grocer_cfg.headers or {}))
    finally:
        if own and hasattr(client, "close"):
            client.close()
    entries = parse_ica_offers(html, week_start=week_start(week_key)) if html else []
    return {"grocer_id": grocer_cfg.grocer_id, "week_key": week_key, "entries": entries}
