# T4a — Real offer fetchers (ICA + Lidl) + Lidl in the store catalog (MC 1355.4)

Parent: MC 1355. Repo: `/srv/workspace/svarkor-matapp-audit-2026`, branch `main`.
Builds on audit T1 (P1-3: mock-only motor) and T2 (VERIFIED data-source research).

## Commit

`49f0914` — `matapp: real ICA+Lidl offer fetchers + Lidl in catalog (MC 1355.4)`
(on `main`, NOT pushed)

Diff summary (9 files, +535/−5):
- `src/fetcher/adapters/__init__.py` (new, 28 L) — dispatch `fetch(grocer_cfg, week_key, session)` by chain; returns None for chains without an adapter so `pull_grocer` falls back to the legacy path.
- `src/fetcher/adapters/_common.py` (new, 28 L) — `week_start` (ISO week → Monday) + `get_text` (fail-tolerant GET: non-200/exception → None).
- `src/fetcher/adapters/ica.py` (new, 128 L) — parses `window.__INITIAL_DATA__` → `offers.weeklyOffers` from the real `https://www.ica.se/erbjudanden/` page; sanitizer for bare `undefined` → `null` and `new Map([...])` → `{}`; balanced-brace blob extraction; price/unit from `parsedMechanics` (fallback: `mechanicInfo` regex); `external_id` = `ica-<id>`, name = brand + name.
- `src/fetcher/adapters/lidl.py` (new, 109 L) — offers index → deduped campaign links (`/c/<slug>/a<id>`) → per-page HTML-escaped `data-grid-data` JSON tiles → `regionsPrices.currentLidlPlusPrice.price` (price/endDate/startDate/basePrice); missing price → tile dropped; `external_id` = `lidl-<productId>`.
- `src/fetcher/grocer.py` (+8) — contract owner unchanged; `pull_grocer` now tries the adapter dispatch first, falls back to the legacy `{base}/veckans-extrapris` pull. Same RawFeed dict shape, same fail-tolerant semantics.
- `src/config.py` (+1) — `CHAIN_MAP["lidl"] = {"id_prefix": "lidl-", "round_cents": None}`.
- `app/config.py` — ica endpoint is now the real `https://www.ica.se/erbjudanden/`; new `lidl` entry `https://www.lidl.se/c/erbjudanden`; willys/coop kept.
- `tests/test_fetcher_adapters.py` (new, 225 L) — offline fixtures only, no network.
- `tests/test_stores_portback.py` — `EXPECTED_STORES` now includes `lidl` (catalog grew to 4).

## Live-fetch sanity (run once this session, real network)

- ICA: `pull_grocer(ica_cfg, "2026-W39")` → **11 entries parsed**; first: `ica-5004009053 / Findus Fryst torskryggfilé / 119.0 kr / st / 2026-09-21→2026-09-27`.
- Lidl: `pull_grocer(lidl_cfg, "2026-W39")` → **132 entries parsed** across the campaign pages; first: `lidl-66000175 / Röda kärnfria druvor / 19.9 kr / kg / 2026-09-08→2026-09-27`; units seen: kg, l, st.
- One live-driven fix: Lidl `basePrice.text` is sometimes a full comparison string ("39,80 kr/kg") — unit extraction now takes the token after the last `/`.

## Tests (offline, no network)

`find . -name __pycache__ -exec rm -rf {} +; rm -rf .pytest_cache; /srv/workspace/Hotell/.venv/bin/python -m pytest tests/ -q`

```
30 passed, 1 warning in 3.59s
EXIT=0
```

Coverage: ICA happy path, sanitizer (undefined + new Map), malformed/truncated page → empty feed, non-200 + network exception → empty feed, happy path through the `pull_grocer` contract (valid_from = ISO Monday); Lidl campaign-link dedup, escaped-JSON tile parse, missing-price tile dropped, index→campaign pull, non-200/exception fail-tolerance; legacy fallback preserved for chains without an adapter (willys).

## Open items

- Willys still on the legacy path (needs a devtools capture of the SPA's OCC calls — T2 §2); Coop needs the real APIM resource paths (T2 §3).
- Lidl pull fetches every campaign page on the index (incl. non-food campaigns); tiles without a price are dropped. Scope refinement is a later card if wanted.

# VERDICT: PASS
