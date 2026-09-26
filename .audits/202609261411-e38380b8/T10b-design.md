# T10b — Design: store-level selection per postnummer (MC 1355.13, parent 1355)

Designed 2026-09-26 against HEAD 1b641a5. Inputs: T10a (VERIFIED locator research),
T7b (store-gating of offers), and the existing seams read this session:
`app/models/profile.py`, `app/models/store_selection.py`, `app/routers/profile.py`,
`app/routers/stores.py`, `app/routers/menu.py`, `app/config.py`,
`src/fetcher/adapters/tjek.py`, `src/fetcher/grocer.py`, `src/offers_db/store.py`,
`app/profile_service.py`, `static/js/ui/profile.js`.

**Bottom line:** resolve-once at profile save; one new `src/locator/` package reusing the
adapter session-injection idiom; a nullable `offers.store_id` column added by a guarded
ALTER; the menu filter extended by one clause; no new endpoint family. Chain-level
ingestion stays the fallback (`store_id IS NULL` = valid everywhere).

---

## 1. Decision: resolve at profile-save time (RECOMMENDED), not menu-time

**Resolve-once, store the resolved list.** `PUT /api/profile` with a `postal_code` runs
the locator, persists the resolved store list on the profile row, and echoes it back.

Why save-time wins:

- **Menu is the hot, auth-gated read path.** Menu-time resolution adds 2–5 network calls
  (Nominatim + ICA token + ICA search + Willys list + Coop list) to every `GET /api/menu`,
  on a lane-shared POC host. A slow/blocked locator would degrade or stall the headline
  endpoint — the exact "silent total failure" class the T5 DA gate flagged.
- **A postnummer is a stable input.** It changes only when the user edits the profile —
  precisely the moment save-time resolution fires. Staleness risk is bounded to "user
  moved and did not re-save", which the UI surfaces by always showing the resolved list
  next to the input.
- **Failure becomes visible and per-chain.** At save time the response can say "ICA
  resolved 3 stores, Coop locator failed" and the user can retry; at menu time the same
  failure would silently fall back to chain-level offers with no user-visible signal.
- **Offline-testability is identical** either way (session injection), so testability is
  not a differentiator — latency and failure visibility are.

Rejected: menu-time resolution with a TTL cache — a second cache mechanism beside the
geocode cache, more moving parts, and still puts network I/O on the menu path.

## 2. Store resolution service — `src/locator/` (new package, reuse-first)

**Why a new package and not an extension of `src/fetcher/adapters/`:** the adapters own
the RawFeed offer-parsing contract (C2); store location is a different concern with a
different output shape. Bolting locators onto the adapters would make one file serve two
contracts. What IS reused: the `_common.get_text` fail-tolerant GET helper, the
session-injection testability idiom (`session=None` → own `httpx.Client`, per
`src/fetcher/grocer.py`), and the fail-tolerant-per-chain rule (a chain's locator error
yields an error entry, never a raise).

| File | Responsibility | Extends / replaces |
|---|---|---|
| `src/locator/__init__.py` | `resolve_stores(postal_code, chains, session=None) -> ResolveResult`; registry `CHAIN_LOCATORS = {"ica": ..., "willys": ..., "coop": ..., "lidl": ...}`; runs each chain's locator inside try/except, collecting per-chain results AND per-chain errors (fail-tolerant). Chains not in the registry (or failing) are reported, never fatal. | New. Replaces nothing (no locator exists today). |
| `src/locator/geocode.py` | `geocode_postal(postal_code, session=None) -> (lat, lon)` via Nominatim (`postalcode=…&country=Sweden&format=json&limit=1`), descriptive User-Agent, 1 req/s honored by the cache below. In-process dict cache keyed by postal_code (postnummer is stable; process restarts are rare relative to profile saves). Returns `None` on failure — caller reports "unresolved". | New helper; no second geocode mechanism exists. |
| `src/locator/models.py` | `ResolvedStore` dataclass: `chain, store_id, store_name, lat, lon, distance_km`; `to_dict()/from_dict()` for JSON persistence. Single shared shape for all chains. | New. |
| `src/locator/ica.py` | `locate(lat, lon, session)`: GET public-access-token → `apim-pub.gw.ica.se/.../storesearch/v1/searchbyquery?query=*&lon&lat&take=3&maxdistance=15000` (Bearer token). Maps `id`/`marketingName`/`visitingZipCode`/lat/lon. Token fetched per run (short-lived, per T10a). | New. |
| `src/locator/willys.py` | `locate(lat, lon, session)`: GET `www.willys.se/axfood/rest/v2/store` (258 stores), filter `onlineStore`/zero-coord dummies, haversine over `geoPoint`, nearest 3. | New. |
| `src/locator/coop.py` | `locate(lat, lon, session)`: GET `proxy.api.coop.se/external/store/stores?api-version=v1` (787 basic rows, `Ocp-Apim-Subscription-Key` from the page-sourced key), then detail-fetch lat/lon for the haversine-shortlisted candidates only (not all 787), nearest 3. | New. |
| `src/locator/lidl.py` | `locate(lat, lon, session)`: GET `live.api.schwarz/.../stores-frontend/stores?...&nearby=lat,lon:15` with the static public `x-apikey`; maps `objectNumber`/`storeName`/server `distance`. | New. |
| `src/locator/geo.py` | `haversine_km(lat1, lon1, lat2, lon2)` — the one distance function, shared by willys/coop (stdlib math only). | New; prevents two haversine copies. |

Size check: each file well under the 250-line target; one concern per file.

**Persistence of the resolved list:** a nullable `resolved_stores` TEXT column on
`profile` holding a JSON list of `ResolvedStore.to_dict()`. No new table — the profile
row is already the per-user store context, and a second table would duplicate the
profile→stores relationship that `selected_stores` (chain level) already models.

## 3. Offers `store_id` — schema change + migration

**Change (in `src/offers_db/store.py`, the SINGLE canonical definition):** add
`store_id = Column(String, nullable=True)` to `Offer`. NULL = chain-level, valid
everywhere (Lidl by design; Coop until the dke path is captured; ICA/Willys before their
store-scoped ingest lands).

**Identity stays `(grocer_id, external_id, week_key)`.** `store_id` is informational for
filtering, NOT part of the unique key. Justification: SQLite cannot ALTER a UNIQUE
constraint — adding it to `uq_offer` would force a table recreate, and a UNIQUE over a
nullable column breaks idempotency anyway (SQLite treats NULLs as distinct, so repeated
chain-level upserts would duplicate). Store-scoped payloads carry their own external ids
(ICA store-page `weeklyOffers[].id`, Tjek per-store catalog hotspot ids), so collisions
with chain-level rows are not expected; if one occurs, `upsert_week`'s existing
last-writer-wins update is the accepted POC behavior — noted as a known limitation, not
silently ignored.

**Migration: guarded `ALTER TABLE offers ADD COLUMN store_id VARCHAR` at boot.**
`Base.metadata.create_all` does not add columns to existing tables, so `app/db.py`
boot() gains a small idempotent step: inspect the `offers` table; if `store_id` is
absent, run the ALTER. Chosen over drop-and-recreate because the live DB holds 279 real
offers (MC 1355.10) and recreate would discard them and force a re-ingest for a
one-statement change. The guard makes it a no-op on fresh databases and on the already-
migrated live copy. (Same guarded-ALTER pattern is reused if `profile.resolved_stores`
needs backfill — it does not: new column, `create_all` covers fresh tables, ALTER covers
existing ones.)

**Population (per T10a §5, staged):**
- Tjek adapter (`src/fetcher/adapters/tjek.py`): `fetch()` gains an optional
  `store_id`/store-label parameter so a per-store catalog pull stamps its rows; the
  chain-level pull keeps stamping NULL. Willys store-scoped ingest = match resolved store
  name → catalog `label` (string join — log unmatched stores, never silently drop).
- ICA: per-store erbjudanden page ingest reuses the existing `parse_ica_offers` parser;
  `stores[].BMSStoreId` → `store_id`. (Follow-up card; the schema and filter land now.)
- Coop/Lidl: stay NULL (Coop blocked on the dke resource path; Lidl national by design).

## 4. API changes

| Endpoint | Change |
|---|---|
| `PUT /api/profile` | `ProfileBody` gains optional `postal_code: str \| None` (validated `^\d{3}\s?\d{2}$`, normalized to digits-only). On save with a postal_code the router calls `src.locator.resolve_stores`, persists the JSON on the profile row, and the response echoes `postal_code` + `resolved_stores` (each entry carrying a per-chain `error` field when that chain's locator failed). A save WITHOUT postal_code clears both fields. Locator failure never 500s — it is reported per chain in the response. |
| `GET /api/profile` | Returns `postal_code` and the persisted `resolved_stores` (parsed JSON; `[]` when unset). |
| `GET /api/stores` | Gains optional `?postal_code=` query param: when present, the response gains a `nearby` block = `resolve_stores` output (resolve-preview for the UI before saving). Without the param, behavior is byte-identical to today. No new route, no new router file. |
| `GET /api/menu` | Filter extension only: after the existing `grocer_id in selected` filter, keep an offer when `o.store_id is None` OR `o.store_id` is among the profile's resolved store ids for that offer's chain. No resolved stores (or no postal_code) → the store clause is a no-op and behavior is exactly today's. Response: `MenuResponse` gains optional `offer_sources: list[{offer_id, grocer_id, store_id}]` so the UI can show which store each used offer came from; `used_offer_ids` is kept unchanged for response-shape compatibility. |

No new endpoints beyond the `?postal_code=` param — resolve-on-save makes a dedicated
resolve endpoint a second mechanism answering the same question.

## 5. UI (minimal)

| File | Change |
|---|---|
| `templates/index.html` | Profile section gains one `postnummer` text input (placeholder "t.ex. 414 51") inside the existing profile form. |
| `static/js/ui/profile.js` | Reads `postal_code`/`resolved_stores` from the GET payload, includes `postal_code` in the PUT body, renders the resolved store list ("ICA Nära Heden · 0,8 km") under the input, and renders per-chain resolve errors as inline text. Render-only, per the file's own header contract. |
| `static/js/app.js` | Menu rendering: when `offer_sources` is present, append the store name to the offer tooltip/line (display only; no logic). |

No new JS module, no framework, no second state mechanism.

## 6. Data flow (happy path)

1. User enters postnummer in the profile form → `PUT /api/profile {postal_code: "41451", ...}`.
2. Router geocodes once (`locator/geocode.py`, cached) → lat/lon.
3. `resolve_stores` runs each chain locator with the injected session; per-chain results
   and errors collected.
4. Router persists `resolved_stores` JSON on the profile row; response echoes it.
5. Next ingest (boot or later store-scoped cards) stamps `offers.store_id` where known.
6. `GET /api/menu`: offers filtered by selected chains (existing) + store clause
   (`store_id IN resolved-for-chain OR store_id IS NULL`); planner unchanged; response
   carries `offer_sources`.

## 7. Rejected alternatives (and why)

- **Menu-time resolution** — puts 2–5 network calls on the hot read path; failure mode
  invisible to the user (§1).
- **Separate `resolved_store` table** — duplicates the profile→stores relationship
  `selected_stores` already models; JSON on the profile row is one mechanism.
- **`store_id` in the UNIQUE constraint** — SQLite can't ALTER a constraint; a nullable
  UNIQUE breaks chain-level idempotency (NULLs distinct). Identity stays
  `(grocer_id, external_id, week_key)`.
- **Drop-and-recreate offers migration** — discards 279 live offers for a one-statement
  ALTER; recreate buys nothing.
- **Dedicated `POST /api/stores/resolve` endpoint** — `GET /api/stores?postal_code=` +
  resolve-on-save already answer preview and persistence; a third route is a second
  mechanism beside an existing one.
- **Extending `src/fetcher/adapters/` with locators** — mixes the RawFeed offer contract
  with a locator contract in one package; the shared parts (get_text, session injection,
  fail-tolerance) are imported, not duplicated.

## 8. Offline-test strategy

All locator tests inject a fake `session` (httpx-like: `get(url, headers)` →
status_code/text/json), exactly the idiom `src/fetcher/grocer.py` documents:

- `tests/test_locator.py`: per-chain locate() against recorded fixture payloads (ICA
  search JSON, Willys 258-store list, Coop stores+detail, Lidl nearby) — assert nearest-3
  ordering, dummy-store filtering (Willys zero-coord row), and mapping of ids/names.
- Fail-tolerance: one chain's locator raising/returning garbage → `resolve_stores` still
  returns the other chains' results plus the error entry; never raises.
- Geocode: Nominatim 200/404/network-error paths; cache hit issues no second request
  (counting fake session).
- Migration: boot against a pre-change DB fixture (offers table without `store_id`) →
  column added, rows intact; boot again → idempotent no-op; fresh DB → column present.
- Menu filter: offers with `store_id` matching/not-matching resolved stores, NULL
  store_id, and no-resolved-stores profile — the last must be byte-identical to today's
  behavior (regression guard).
- API: PUT profile with/without postal_code (422 on malformed; per-chain error echoed,
  never 500); GET /api/stores?postal_code= preview; GET /api/profile roundtrip.

## 9. Known limitations (stated, not hidden)

- Willys catalog↔store matching is a string join on the store name (T10a §2b caveat) —
  unmatched stores are logged, stores without a Tjek catalog fall back to chain-level.
- Coop store-scoped offers remain blocked on the dke resource path (devtools capture);
  Coop stays `store_id IS NULL` this card.
- Resolved stores go stale if the user moves without re-saving the profile; the UI
  always shows the resolved list so the state is visible.

# VERDICT: SHIP
