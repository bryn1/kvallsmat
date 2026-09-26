# T8 — Willys+Coop offers via the Tjek squid API

MC card 1355.10 (parent 1355) · matapp · 2026-09-26 · commit **c16d0889dea519d7289bfc3b36b5fd9749f29613** (main, not pushed)

## Diff summary (commit c16d088)

- **NEW `src/fetcher/adapters/tjek.py`** (~170 lines): Tjek squid adapter behind the existing RawFeed contract. `pick_catalog` (current-catalog pick), `parse_hotspot`/`parse_hotspots` (hotspot → RawOffer), `pull` (dealer listing → hotspots, fail-tolerant: non-200, network error, bad JSON, no catalog → `entries: []`, never raises).
- `src/fetcher/adapters/__init__.py`: dispatch entries `"willys": _tjek, "coop": _tjek` — same single mechanism, no second dispatch layer.
- `app/config.py`: willys endpoint → `https://squid-api.tjek.com/v2/catalogs?dealer_id=c371GA`, coop → `...?dealer_id=6c28SD`. ica/lidl untouched.
- `tests/test_tjek_adapter.py` (NEW, offline, inline fixtures shaped after the live responses): happy path, catalog-pick (expired/future skipped, newest publish wins, 48h grace fallback), missing price dropped, non-SEK dropped, non-200/exception/bad-JSON → empty feed, single-prefix invariant.
- `tests/test_fetcher_adapters.py`: the legacy-fallback contract test retargeted from willys (which now HAS an adapter) to a genuinely adapter-less chain (`hemkop`) — the contract itself is unchanged and still tested.

## Real Tjek API shape observed (live probe 2026-09-26)

Matches T7a with two corrections/additions:

- `GET /v2/catalogs?dealer_id=<id>` → JSON list of per-store catalogs: `{id, label, offer_count, page_count, run_from, run_till, publication_date, ...}`. Willys c371GA: 24 catalogs; Stora Coop 6c28SD: 24.
- `GET /v2/catalogs/{id}/hotspots` → JSON list of records: `{id, type: "offer", heading, locations, webshop, run_from (EPOCH INT), run_till (EPOCH INT), offer: {id, ern, heading, pricing: {price, currency, pre_price}, quantity: {unit: {symbol, si: {symbol, factor}}, size: {from, to}, pieces: {...}}, run_from (ISO STRING), run_till (ISO STRING), publish}}`.
  - **The offer-level `run_from`/`run_till` are ISO strings; the hotspot-level ones are epoch ints.** The adapter reads the offer-level ones.
  - Units observed: g→si kg (0.001), ml/cl/dl→si l, kg→kg, l→l, pcs→si pcs. Adapter maps si symbol, `pcs`→`st`.
- **Deviation from the research description:** Coop's dealer listing had ALREADY rotated the current week's leaflet out (all 24 listed catalogs start 2026-09-27T22:00Z; the current `8TeMm7nX` is no longer listed), while Willys' listing still contained the current one. A strict "covers now" pick would serve coop zero offers all week. Adaptation: `pick_catalog` prefers catalogs covering now (newest publish wins) and falls back to the nearest catalog starting within **48h** (GRACE_HOURS) so the grocer serves the upcoming week instead of nothing; expired-only listings still yield None. Recorded as a test (`test_pick_catalog_grace_fallback`).
- external_id is the bare hotspot/offer id (e.g. `s7a0G8aaB36--QVXTrP0x`) — the single-prefix invariant holds: `chain_mapper` owns the CHAIN_MAP prefix, the adapter never prefixes (tested).

## Live sanity (real network, through `pull_grocer`, 2026-09-26)

Raw JSON saved at `.audits/202609260913-e6190a72/T8-live-sanity.json`.

- **willys: 111 entries** — sample: `{"external_id": "G3OtoFf8EiBVZlYRAhmwU", "name": "GOUDA", "price": 49.9, "unit": "kg", "valid_from": "2026-09-20", "valid_to": "2026-09-27"}`
- **coop: 97 entries** (next week's catalog via the grace fallback, valid 2026-09-27→10-04) — sample: `{"external_id": "EYpDtdFT22Ky3ojCEQFIC", "name": "Frönuftig", "price": 20.0, "unit": "kg", "valid_from": "2026-09-27", "valid_to": "2026-10-04"}`

## Test evidence

Fresh caches removed (`__pycache__`, `.pytest_cache`), then:
`/srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q` (note: the task said `/srv/workspace/Hotell/...`; the actual path on this host is lowercase `hotell` — same venv, the only working python):

```
59 passed, 3 warnings in 6.57s
EXIT=0
```

## Commit

`c16d0889dea519d7289bfc3b36b5fd9749f29613` on `main` (parent c6979be), authored `code (MC 1355.7) <code@agent-town.local>` per repo convention, NOT pushed.

# VERDICT: PASS
