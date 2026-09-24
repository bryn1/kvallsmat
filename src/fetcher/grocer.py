"""M2 fetcher.grocer — CONTRACT C2 part 1.

pull_grocer(grocer_cfg, week_key[, session]) -> RawFeed

One HTTP pull per grocer to ``{base}/veckans-extrapris``. FAIL-TOLERANT per REV6 §2/§6:
a single grocer's HTTP error, bad JSON, or malformed entries never fail the whole run —
they yield an empty feed (entries=[]) instead of raising. Malformed/RawOffer entries are
dropped, not fatal.

RawFeed = {"grocer_id", "week_key", "entries": [RawOffer ...]}
RawOffer = {"external_id", "name", "price", "unit", "valid_from", "valid_to"}
  price kept as the raw float here; the normalizer (C4) owns price/identity mapping.

``session`` is injected for tests and is an httpx-like object exposing
``get(url, headers=None)`` returning an object with ``.status_code`` and ``.json()``.
"""
from __future__ import annotations

import httpx


_REQUIRED = ("external_id", "name", "price", "valid_from", "valid_to")


def pull_grocer(grocer_cfg, week_key: str, session=None) -> dict:
    # Real per-grocer adapters first (MC 1355.4); None = no adapter for this
    # chain -> fall through to the legacy {base}/veckans-extrapris pull.
    from .adapters import fetch as adapter_fetch

    adapted = adapter_fetch(grocer_cfg, week_key, session)
    if adapted is not None:
        return adapted

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
        if not all(e.get(k) is not None for k in _REQUIRED):
            continue  # malformed entry -> drop, not fatal
        try:
            float(e["price"])
        except (TypeError, ValueError):
            continue  # unparsable price -> drop early, not fatal (C4 also guards)
        clean.append({k: e[k] for k in _REQUIRED})
    return {"grocer_id": grocer_cfg.grocer_id, "week_key": week_key, "entries": clean}
