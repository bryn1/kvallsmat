"""src.locator.willys — Willys store locator (T10a §2a, T10b §2).

Willys' own 258-store list (axfood/rest/v2/store) carries coordinates; the
Tjek store list is NOT the physical store universe (24 vs 258, T10a CAUTION),
so the locator uses the Willys list and haversine. The first list element is
an online/dummy store with zero coordinates — filtered. Fail-tolerant: any
failure yields [].
"""
from __future__ import annotations

import httpx

from src.fetcher.adapters._common import get_json
from src.locator.geo import haversine_km

_STORES_URL = "https://www.willys.se/axfood/rest/v2/store"


def locate(lat: float, lon: float, session=None) -> list:
    """Nearest 3 physical Willys stores to (lat, lon) as ResolvedStore objects."""
    from .models import ResolvedStore

    own = session is None
    client = session if session is not None else httpx.Client()
    try:
        data = get_json(client, _STORES_URL, {"Accept": "application/json"})
    finally:
        if own and hasattr(client, "close"):
            client.close()
    scored = []
    for store in data if isinstance(data, list) else []:
        parsed = _parse(store, lat, lon)
        if parsed is not None:
            scored.append(parsed)
    scored.sort(key=lambda t: t[0])
    return [store for _dist, store in scored[:3]]


def _parse(store, lat: float, lon: float):
    from .models import ResolvedStore

    if not isinstance(store, dict) or store.get("onlineStore"):
        return None  # online/dummy row
    geo = store.get("geoPoint") or {}
    try:
        slat, slon = float(geo["latitude"]), float(geo["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    if slat == 0.0 and slon == 0.0:
        return None  # zero-coord dummy (T10a §2a)
    if not store.get("storeId") or not store.get("name"):
        return None
    return (haversine_km(lat, lon, slat, slon),
            ResolvedStore(chain="willys", store_id=str(store["storeId"]),
                          store_name=str(store["name"]), lat=slat, lon=slon,
                          distance_km=round(haversine_km(lat, lon, slat, slon), 3)))
