"""src.locator — postnummer -> nearest stores per chain (T10b §2, MC 1355.16).

``resolve_stores(postal_code, chains, session=None)`` geocodes the postnummer
once (Nominatim, TTL-cached) and runs each chain's locator inside try/except,
collecting per-chain results AND per-chain status (``ok`` / ``error: <reason>``)
— fail-tolerant, never fatal. Chains not in the registry are reported as an
error entry, never fatal. The returned shape is the JSON persisted on the
profile row:

    {"resolved_at": iso, "chains": {chain: {"status": "ok"|"error",
                                            "error": str?, "stores": [...]}}}

``resolve_stores_cached`` adds the per-process resolve-result cache for the
preview path (T10b §4): same 24 h TTL as the geocode cache and a bounded size
of 128 postal codes (T10d N4) — auth-gated callers only, but bounded anyway.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from . import coop, ica, lidl, willys  # noqa: F401  (register the locators)
from .geocode import clear_geocode_cache, geocode_postal
from .models import ChainStatus, ResolvedStore  # noqa: F401  (re-exported)

# chain key -> locate(lat, lon, session) -> list[ResolvedStore]
CHAIN_LOCATORS = {
    "ica": ica.locate,
    "willys": willys.locate,
    "coop": coop.locate,
    "lidl": lidl.locate,
}

_RESOLVE_TTL_SECONDS = 24 * 3600  # same TTL as the geocode cache (T10d N4)
_RESOLVE_MAX_ENTRIES = 128        # bounded size (T10d N4)

# postal_code -> (monotonic_ts, resolve_stores output)
_resolve_cache: dict[str, tuple[float, dict]] = {}


def resolve_stores(postal_code: str, chains=None, session=None) -> dict:
    """Resolve a postnummer to the nearest stores per chain — never raises.

    A chain whose locator fails (or an unknown chain, or a failed geocode)
    yields ``{"status": "error", "error": ..., "stores": []}``; the other
    chains still resolve. ``session`` is injected for offline tests.
    """
    chain_names = list(CHAIN_LOCATORS) if chains is None else list(chains)
    latlon = geocode_postal(postal_code, session=session)
    out = {"resolved_at": datetime.now(timezone.utc).isoformat(),
           "chains": {}}
    for chain in chain_names:
        locator = CHAIN_LOCATORS.get(chain)
        if locator is None:
            out["chains"][chain] = _error_entry(
                f"no locator for chain {chain!r}")
        elif latlon is None:
            out["chains"][chain] = _error_entry(
                "geocode failed (postnummer unresolved)")
        else:
            try:
                stores = locator(latlon[0], latlon[1], session)
                out["chains"][chain] = {
                    "status": "ok",
                    "stores": [s.to_dict() for s in stores],
                }
            except Exception as exc:  # fail-tolerant per chain (T10b §2)
                out["chains"][chain] = _error_entry(
                    f"{type(exc).__name__}: {exc}")
    return out


def resolve_stores_cached(postal_code: str, chains=None, session=None) -> dict:
    """``resolve_stores`` behind the bounded per-process cache (T10d N4)."""
    now = time.monotonic()
    hit = _resolve_cache.get(postal_code)
    if hit is not None and now - hit[0] < _RESOLVE_TTL_SECONDS:
        return hit[1]
    result = resolve_stores(postal_code, chains, session)
    if len(_resolve_cache) >= _RESOLVE_MAX_ENTRIES:
        oldest = min(_resolve_cache, key=lambda k: _resolve_cache[k][0])
        del _resolve_cache[oldest]
    _resolve_cache[postal_code] = (now, result)
    return result


def clear_caches() -> None:
    """Test hook: drop the geocode cache AND the resolve-result cache."""
    clear_geocode_cache()
    _resolve_cache.clear()


def _error_entry(reason: str) -> dict:
    return {"status": "error", "error": reason, "stores": []}
