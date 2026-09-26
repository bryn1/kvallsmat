"""src.locator.lidl — Lidl store locator (T10a §4a, T10b §2).

Lidl's Schwarz stores API has a NATIVE nearby-search
(``nearby=lat,lon:radiusKm``, radius 1-100), so no haversine is needed — the
server returns ``distance`` per store. The ``x-apikey`` is a static public
key shipped in the lidl.se site JS (T10a §4a), not a secret. Fail-tolerant:
any failure yields [].
"""
from __future__ import annotations

import httpx

from src.fetcher.adapters._common import get_json

_API_URL = ("https://live.api.schwarz/odj/stores-api/v2/myapi"
            "/stores-frontend/stores")
# Static public key shipped in lidl.se's storesearch-frontend bundle (T10a §4a).
_X_APIKEY = "16QaHsGX3Uc3JLhNlS2ZG1CmosbzVPs2"


def locate(lat: float, lon: float, session=None) -> list:
    """Nearest 3 Lidl stores to (lat, lon) as ResolvedStore objects."""
    from .models import ResolvedStore

    own = session is None
    client = session if session is not None else httpx.Client()
    try:
        url = (f"{_API_URL}?limit=3&offset=0&country_code=SE"
               f"&nearby={lat},{lon}:15&expand=GENERAL_HOURS")
        data = get_json(client, url, {"x-apikey": _X_APIKEY}) or {}
    finally:
        if own and hasattr(client, "close"):
            client.close()
    stores = []
    for item in data.get("items") or []:
        store = _to_resolved(item)
        if store is not None:
            stores.append(store)
    return stores


def _to_resolved(item) -> "ResolvedStore | None":
    from .models import ResolvedStore

    if not isinstance(item, dict):
        return None
    address = item.get("address") or {}
    try:
        return ResolvedStore(
            chain="lidl",
            store_id=str(item["objectNumber"]),
            store_name=str(item.get("storeName") or ""),
            lat=float(address["latitude"]),
            lon=float(address["longitude"]),
            distance_km=float(item.get("distance") or 0.0),
        )
    except (KeyError, TypeError, ValueError):
        return None
