"""src.locator.ica — ICA store locator (T10a §1a, T10b §2).

Flow (all VERIFIED live in T10a): anonymous public-access-token -> storesearch
searchbyquery with lon/lat (the postnummer itself is NOT a valid query value).
The token is short-lived, so it is fetched per run. Fail-tolerant: any failure
yields [] — the caller records the per-chain error, never a raise.
"""
from __future__ import annotations

import httpx

from src.fetcher.adapters._common import get_json, get_text

_TOKEN_URL = "https://www.ica.se/e11/public-access-token"
_SEARCH_URL = ("https://apim-pub.gw.ica.se/sverige/digx/storesearch/v1"
               "/searchbyquery")


def locate(lat: float, lon: float, session=None) -> list:
    """Nearest 3 ICA stores to (lat, lon) as ResolvedStore objects."""
    from .models import ResolvedStore

    own = session is None
    client = session if session is not None else httpx.Client()
    try:
        token = _public_access_token(client)
        if not token:
            return []
        url = (f"{_SEARCH_URL}?query=*&lon={lon}&lat={lat}"
               f"&take=3&offset=0&maxdistance=15000")
        docs = get_json(client, url,
                        {"Authorization": f"Bearer {token}"}) or {}
    finally:
        if own and hasattr(client, "close"):
            client.close()
    stores = []
    for doc in docs.get("documents") or []:
        store = _to_resolved(doc)
        if store is not None:
            stores.append(store)
    return stores


def _public_access_token(client) -> str | None:
    data = get_json(client, _TOKEN_URL)
    if not isinstance(data, dict):
        return None
    token = data.get("publicAccessToken")
    return str(token) if token else None


def _to_resolved(doc) -> "ResolvedStore | None":
    from .models import ResolvedStore

    if not isinstance(doc, dict) or doc.get("id") is None:
        return None
    try:
        return ResolvedStore(
            chain="ica",
            store_id=str(doc["id"]),
            store_name=str(doc.get("marketingName") or doc.get("name") or ""),
            lat=float(doc["latitude"]),
            lon=float(doc["longitude"]),
            distance_km=0.0,  # ICA's search returns no distance; ranked server-side
        )
    except (KeyError, TypeError, ValueError):
        return None
