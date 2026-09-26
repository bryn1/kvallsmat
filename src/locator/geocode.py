"""src.locator.geocode — postnummer -> (lat, lon) via Nominatim (T10b §2).

The ONE geocode mechanism for the locator package. The in-process dict cache
is keyed by postal_code with a 24 h TTL (T10b §10-F7): a bad cached geocode
must not outlive the data. Returns None on any failure — the caller reports
"unresolved"; this module never raises.
"""
from __future__ import annotations

import time

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "matapp-locator/1.0 (store-level selection per postnummer)"
_TTL_SECONDS = 24 * 3600  # 24 h — a stale geocode must not outlive the data

# postal_code -> (monotonic_ts, (lat, lon))
_cache: dict[str, tuple[float, tuple[float, float]]] = {}


def clear_geocode_cache() -> None:
    """Test hook: drop every cached geocode (cache isolation between tests)."""
    _cache.clear()


def geocode_postal(postal_code: str, session=None,
                   ttl_seconds: int | None = None):
    """Resolve a Swedish postnummer to (lat, lon); None when unresolvable.

    Cached per postal_code with a 24 h TTL (``ttl_seconds`` overrides it, for
    tests). ``session`` is injected for offline tests — the httpx-like idiom
    of ``src/fetcher/grocer.py`` (``get(url, headers)``).
    """
    ttl = _TTL_SECONDS if ttl_seconds is None else ttl_seconds
    now = time.monotonic()
    hit = _cache.get(postal_code)
    if hit is not None and now - hit[0] < ttl:
        return hit[1]
    coords = _fetch(postal_code, session)
    if coords is not None:
        _cache[postal_code] = (now, coords)
    return coords


def _fetch(postal_code: str, session=None):
    url = (f"{NOMINATIM_URL}?postalcode={postal_code}"
           f"&country=Sweden&format=json&limit=1")
    from src.fetcher.adapters._common import get_json

    own = session is None
    client = session if session is not None else httpx.Client()
    try:
        docs = get_json(client, url, {"User-Agent": USER_AGENT})
    finally:
        if own and hasattr(client, "close"):
            client.close()
    if not isinstance(docs, list) or not docs:
        return None
    try:
        return (float(docs[0]["lat"]), float(docs[0]["lon"]))
    except (KeyError, TypeError, ValueError, IndexError):
        return None
