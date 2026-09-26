"""src.locator.coop — Coop store locator via the proxy store API (T10a §3a).

The basic 787-store list carries NO coordinates, so shortlisting before the
per-store detail fetch is impossible (T10b §10-F4): the design is a daily,
persisted cache of ALL store details, then haversine over the cached
coordinates. Cold-start policy (T10d N2 — stated, not hidden):

  * The cache is file-backed app state (NOT in-process only), so a cold boot
    does not re-issue the ~787 detail requests.
  * The first resolve after a cache wipe warms it LAZILY inside that resolve —
    a stated POC limitation: that one call is slow. It is deliberately NOT run
    synchronously inside boot; the boot ingest stays offer-only.
  * A failed/partial detail run persists NOTHING and the next resolve
    re-fetches from scratch (simple, correct — no resume semantics).

The APIM subscription key is fetched at resolve time from the coopSettings
blob on www.coop.se/butiker-erbjudanden/ (public — it ships in the page HTML
to every visitor) and cached WITH the store cache — never a copied constant
that rots silently (T10b §10-F9).
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone

import httpx

from src.fetcher.adapters._common import get_json, get_text
from src.locator.geo import haversine_km

_COOP_PAGE = "https://www.coop.se/butiker-erbjudanden/"
_STORES_URL = "https://proxy.api.coop.se/external/store/stores?api-version=v1"
_DETAIL_URL = ("https://proxy.api.coop.se/external/store/stores/{ledger}"
               "?api-version=v1")
_KEY_RE = re.compile(r'"storeApiSubscriptionKey"\s*:\s*"([0-9a-f]+)"')
_MAX_AGE_H = 24


def default_cache_path() -> str:
    """File-backed cache location, next to the DB (env-overridable).

    Reuses the ONE state-dir knob the app already has (MATAPP_DB_URL, set by
    server.py to $STATE_DIRECTORY/.data on vm106) instead of a second env var:
    the deployed repo tree is READ-ONLY, so a cache under the app dir fails
    with Errno 30 (live finding, MC 1355.18). Falls back to the app-local
    .data dir for bare local runs.
    """
    override = os.environ.get("MATAPP_COOP_CACHE")
    if override:
        return override
    db_url = os.environ.get("MATAPP_DB_URL", "")
    if db_url.startswith("sqlite:///"):
        db_file = db_url[len("sqlite:///"):]
        return os.path.join(os.path.dirname(os.path.abspath(db_file)),
                            "coop_store_cache.json")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), ".data", "coop_store_cache.json")


def locate(lat: float, lon: float, session=None,
           cache_path: str | None = None) -> list:
    """Nearest 3 Coop stores to (lat, lon), from the daily detail cache."""
    from .models import ResolvedStore

    path = cache_path or default_cache_path()
    own = session is None
    client = session if session is not None else httpx.Client()
    try:
        cached = _load_cache(path)
        if cached is not None and _fresh(cached):
            details = cached["stores"]
        else:
            details = _fetch_all_details(client)  # raises on a partial run
            _write_cache(path, details)
    finally:
        if own and hasattr(client, "close"):
            client.close()
    scored = []
    for ledger, detail in details.items():
        try:
            slat, slon = float(detail["latitude"]), float(detail["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        scored.append((haversine_km(lat, lon, slat, slon), detail, slat, slon))
    scored.sort(key=lambda t: t[0])
    return [ResolvedStore(chain="coop", store_id=str(d["ledgerAccountNumber"]),
                          store_name=str(d.get("name") or ""),
                          lat=slat, lon=slon, distance_km=round(dist, 3))
            for dist, d, slat, slon in scored[:3]]


def _fetch_all_details(client) -> dict:
    """Key -> basic list -> EVERY store detail. All-or-nothing: any failed
    detail raises, so a partial run never reaches the cache (T10d N2)."""
    key = _apim_key(client)
    if not key:
        raise RuntimeError("coop APIM key not found in coopSettings")
    headers = {"Ocp-Apim-Subscription-Key": key}
    basic = get_json(client, _STORES_URL, headers)
    # Live response (verified 2026-09-26): the list is WRAPPED —
    # {"stores": [...]}; tolerate a bare list too.
    if isinstance(basic, dict):
        basic = basic.get("stores")
    if not isinstance(basic, list) or not basic:
        raise RuntimeError("coop store list unavailable")
    details: dict = {}
    for row in basic:
        ledger = row.get("ledgerAccountNumber") if isinstance(row, dict) else None
        if not ledger:
            continue
        detail = get_json(client, _DETAIL_URL.format(ledger=ledger), headers)
        if not isinstance(detail, dict) or "latitude" not in detail:
            raise RuntimeError(f"coop detail fetch incomplete ({ledger})")
        details[str(ledger)] = detail
    if not details:
        raise RuntimeError("coop store list carried no usable rows")
    return details


def _apim_key(client) -> str | None:
    page = get_text(client, _COOP_PAGE)
    if not page:
        return None
    match = _KEY_RE.search(page)
    return match.group(1) if match else None


def _load_cache(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("stores"), dict):
        return None
    return data


def _fresh(cache: dict) -> bool:
    try:
        fetched = datetime.fromisoformat(cache["fetched_at"])
    except (KeyError, TypeError, ValueError):
        return False
    age = datetime.now(timezone.utc) - fetched
    return age.total_seconds() < _MAX_AGE_H * 3600


def _write_cache(path: str, details: dict) -> None:
    """Persist the completed run only (a partial run writes nothing — N2)."""
    payload = {"fetched_at": datetime.now(timezone.utc).isoformat(),
               "stores": details}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    os.replace(tmp, path)
