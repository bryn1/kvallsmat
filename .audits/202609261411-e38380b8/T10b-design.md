# T10b — Design: store-level selection per postnummer (MC 1355.13, parent 1355)

Designed 2026-09-26 against HEAD 1b641a5; **Revision 2** after the devils-advocate gate
(T10c-da-verdict.md, VERDICT FIX — 1×P0, 4×P1, 3×P2, 1×P3; all addressed in §10).
Inputs: T10a (VERIFIED locator research), T7b (store-gating of offers), and the existing
seams read this session: `app/models/profile.py`, `app/models/store_selection.py`,
`app/routers/profile.py`, `app/routers/stores.py`, `app/routers/menu.py`,
`app/config.py`, `src/fetcher/adapters/tjek.py`, `src/fetcher/grocer.py`,
`src/offers_db/store.py`, `app/profile_service.py`, `app/db.py`, `database.py`,
`static/js/ui/profile.js`, `templates/index.html`.

**Bottom line:** resolve-once at profile save; one new `src/locator/` package reusing the
adapter session-injection idiom; nullable `store_id` on offers plus `postal_code` +
`resolved_stores` on profile, ALL added by guarded ALTERs at boot; store-scoped rows are
identity-distinct from chain-level rows and never overwrite them; the menu filter
dedups preferring store-level rows; the preview param is auth-gated. Chain-level
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
  precisely the moment save-time resolution fires. Staleness is bounded and made VISIBLE:
  the persisted resolution carries `resolved_at` and per-chain status, and the UI shows
  both (§4, §10-F7).
- **Failure becomes visible and per-chain — and stays visible.** At save time the
  response reports which chains resolved and which errored; the per-chain status is
  PERSISTED with the resolution (not just echoed), so a chain that failed during a
  transient outage is visibly `error` in every later GET until a successful re-save
  re-resolves it. The menu filter treats an errored chain as "chain-level rows only"
  (§4) — never a silent narrowing.
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
| `src/locator/__init__.py` | `resolve_stores(postal_code, chains, session=None) -> ResolveResult`; registry `CHAIN_LOCATORS = {"ica": ..., "willys": ..., "coop": ..., "lidl": ...}`; runs each chain's locator inside try/except, collecting per-chain results AND per-chain status (`ok` / `error: <reason>`) — fail-tolerant, never fatal. Chains not in the registry are reported, never fatal. | New. Replaces nothing (no locator exists today). |
| `src/locator/geocode.py` | `geocode_postal(postal_code, session=None) -> (lat, lon)` via Nominatim (`postalcode=…&country=Sweden&format=json&limit=1`), descriptive User-Agent. In-process dict cache keyed by postal_code **with a TTL (24 h)** — a bad cached geocode must not outlive the data (§10-F7); cache is also clearable for tests. Returns `None` on failure — caller reports "unresolved". | New helper; no second geocode mechanism exists. |
| `src/locator/models.py` | `ResolvedStore` dataclass: `chain, store_id, store_name, lat, lon, distance_km`; `ChainStatus` (`chain, status, error`); `to_dict()/from_dict()` for JSON persistence. Single shared shape for all chains. | New. |
| `src/locator/ica.py` | `locate(lat, lon, session)`: GET public-access-token → `apim-pub.gw.ica.se/.../storesearch/v1/searchbyquery?query=*&lon&lat&take=3&maxdistance=15000` (Bearer token). Maps `id`/`marketingName`/`visitingZipCode`/lat/lon. Token fetched per run (short-lived, per T10a). | New. |
| `src/locator/willys.py` | `locate(lat, lon, session)`: GET `www.willys.se/axfood/rest/v2/store` (258 stores), filter `onlineStore`/zero-coord dummies, haversine over `geoPoint`, nearest 3. | New. |
| `src/locator/coop.py` | `locate(lat, lon, session)`: **daily cache of ALL 787 store details** (basic list + per-store detail for lat/lon), then haversine over the cached coordinates, nearest 3. The basic list carries NO coordinates (T10a §3a), so shortlisting before detail-fetch is impossible — the cache is the design, not an optimization (§10-F4). Cold start: one-time ~787 requests, then 0/day; cache is file/DB-backed app state, NOT in-process only, so a cold boot does not re-issue 787 requests. The APIM key is fetched at resolve time from `www.coop.se/butiker-erbjudanden/` `coopSettings` (one extra GET, cached with the store cache) — never a copied constant that rots silently (§10-F9). | New. |
| `src/locator/lidl.py` | `locate(lat, lon, session)`: GET `live.api.schwarz/.../stores-frontend/stores?...&nearby=lat,lon:15` with the static public `x-apikey`; maps `objectNumber`/`storeName`/server `distance`. | New. |
| `src/locator/geo.py` | `haversine_km(lat1, lon1, lat2, lon2)` — the one distance function, shared by willys/coop (stdlib math only). | New; prevents two haversine copies. |

Size check: each file well under the 250-line target; one concern per file.

**Persistence of the resolved list:** nullable `resolved_stores` TEXT column on
`profile` holding a JSON object `{"resolved_at": iso, "chains": {chain: {"status":
"ok"|"error", "error": str?, "stores": [ResolvedStore...]}}}`. No new table — the
profile row is already the per-user store context, and a second table would duplicate
the profile→stores relationship that `selected_stores` (chain level) already models.
The per-chain status and `resolved_at` are PERSISTED so staleness and partial failure
are visible in every later GET and in the UI (§10-F7).

## 3. Offers `store_id` — schema change + migration

**Change (in `src/offers_db/store.py`, the SINGLE canonical definition):** add
`store_id = Column(String, nullable=True)` to `Offer`. NULL = chain-level, valid
everywhere (Lidl by design; Coop until the dke path is captured; Willys chain-level
pull before store-scoped ingest lands).

**Identity and the P0 fix (§10-F1).** The UNIQUE constraint stays
`(grocer_id, external_id, week_key)` — SQLite cannot ALTER a constraint, and a nullable
UNIQUE breaks chain-level idempotency (NULLs distinct). But `store_id` is NOT merely
informational: the upsert MATCH KEY in `upsert_week` becomes
`(grocer_id, external_id, week_key, store_id or "")` — a store-scoped row never matches
a chain-level row. Two rules make retraction impossible:

1. **Store-scoped external ids are prefixed at ingest**: store-scoped rows are written
   as `external_id = f"{store_id}:{hotspot_id}"`. They can never collide with a
   chain-level row's bare id, so the Willys case the DA proved (same Tjek catalog
   ingested chain-level with `store_id NULL`, then store-scoped) writes a SECOND row
   instead of overwriting.
2. **Never overwrite a `store_id IS NULL` row with a store-scoped value**: even if a
   future payload reuses a bare id, `upsert_week`'s match key (rule above) sends the
   store-scoped write to its own row. Regression test (§8): chain-level pull then
   store-scoped pull of the same catalog → the NULL rows survive unchanged.

**Migration: guarded ALTERs at boot for ALL THREE new columns** — `offers.store_id`,
`profile.postal_code`, `profile.resolved_stores` (§10-F3). `Base.metadata.create_all`
does not add columns to existing tables, and the live DB already has both tables
(DA-verified via `PRAGMA table_info`: no `store_id`, no `postal_code`,
no `resolved_stores`), so without the profile ALTERs `save_profile` would 500 on the
live DB. `app/db.py` boot() gains one idempotent step: for each (table, column, type),
inspect; if absent, `ALTER TABLE ... ADD COLUMN`; **catch `OperationalError` and treat
"duplicate column name" as success** (re-inspect to confirm) so concurrent boots don't
crash in `lifespan` (§10-F8). Chosen over drop-and-recreate because the live DB holds
279 real offers and recreate would discard them for a one-statement change.

**Population (per T10a §5, staged):**
- Tjek adapter (`src/fetcher/adapters/tjek.py`): `fetch()` gains an optional
  `store_id`/store-label parameter; store-scoped pulls stamp
  `external_id = f"{store_id}:{hotspot_id}"` + `store_id` per rule 1. The chain-level
  pull keeps bare ids and NULL. Willys store-scoped ingest joins resolved store →
  catalog **on `flyerURL` store number → Tjek label first** (the store list carries
  `flyerURL`/`storeId`; the storeflyer endpoint returns the catalog name), with the
  name string join as fallback — unmatched stores are logged, never silently dropped
  (§10-F9).
- ICA: per-store erbjudanden page ingest reuses the existing `parse_ica_offers` parser;
  `stores[].BMSStoreId` → `store_id`, prefixed external id per rule 1. (Follow-up card;
  the schema and filter land now.)
- Coop/Lidl: stay NULL (Coop blocked on the dke resource path; Lidl national by design).

## 4. API changes

| Endpoint | Change |
|---|---|
| `PUT /api/profile` | `ProfileBody` gains optional `postal_code: str \| None` (validated `^\d{3}\s?\d{2}$`, normalized to digits-only). **Absent field = leave the persisted value unchanged** — the deployed frontend does not send `postal_code` today, and clear-on-absent would wipe a saved postnummer on a stale-client save (§10-F6). Only an explicit `postal_code: null` or `""` clears it (and then also clears `resolved_stores`). On save WITH a postal_code the router calls `src.locator.resolve_stores`, persists the JSON (with `resolved_at` + per-chain status) on the profile row, and the response echoes `postal_code` + `resolved_stores`. Locator failure never 500s — it is persisted and echoed per chain. |
| `GET /api/profile` | Returns `postal_code` and the persisted `resolved_stores` object (parsed JSON; `null` when unset) including `resolved_at` and per-chain status. |
| `GET /api/stores` | Gains optional `?postal_code=` query param: **auth-gated — the param is only honored for an authenticated user (401 when absent, same gate as profile/menu)**; anonymous calls without the param keep today's byte-identical behavior. With the param: response gains a `nearby` block = `resolve_stores` output (resolve-preview for the UI before saving). This closes the unauthenticated outbound-call amplification the DA flagged (§10-F5): the locator pipeline (Nominatim 1 req/s policy included) is never reachable anonymously. The geocode cache (TTL) plus a small per-process resolve-result cache keyed by postal_code bound repeat cost for a hammering authenticated client. |
| `GET /api/menu` | Filter extension only, in two steps after the existing `grocer_id in selected` filter: (1) **store clause** — keep an offer when `o.store_id is None` OR `o.store_id` is among the profile's resolved store ids for that offer's chain; a chain whose persisted status is `error` contributes chain-level rows only. No resolved stores (or no postal_code) → the store clause is a no-op and behavior is exactly today's. (2) **dedup** — after the store clause, dedup by `(grocer_id, normalized name)` preferring the store-level row when the profile has resolved stores for that chain; the chain-level row is the fallback only when no store-level row matched (§10-F2). This prevents `plan_menu`'s offer-hit counting and `andel_extrapris` from double-counting the same physical product that exists both chain-level and store-level. Response: `MenuResponse` gains optional `offer_sources: list[{offer_id, grocer_id, store_id}]`; `used_offer_ids` is kept unchanged for response-shape compatibility. |

No new endpoints beyond the `?postal_code=` param — resolve-on-save makes a dedicated
resolve endpoint a second mechanism answering the same question.

## 5. UI (minimal)

| File | Change |
|---|---|
| `templates/index.html` | Profile section gains one `postnummer` text input (placeholder "t.ex. 414 51") inside the existing profile form. |
| `static/js/ui/profile.js` | Reads `postal_code`/`resolved_stores` from the GET payload, includes `postal_code` in the PUT body only when the user edited it (absent = unchanged semantics), renders the resolved store list ("ICA Nära Heden · 0,8 km") with per-chain status, renders `resolved_at` so staleness is visible, and renders per-chain resolve errors as inline text with a re-save hint. Render-only, per the file's own header contract. |
| `static/js/app.js` | Menu rendering: when `offer_sources` is present, append the store name to the offer tooltip/line (display only; no logic). |

No new JS module, no framework, no second state mechanism.

## 6. Data flow (happy path)

1. User enters postnummer in the profile form → `PUT /api/profile {postal_code: "41451", ...}`.
2. Router geocodes once (`locator/geocode.py`, TTL-cached) → lat/lon.
3. `resolve_stores` runs each chain locator with the injected session; per-chain results
   and statuses collected (Coop reads its daily detail cache; key fetched at resolve time).
4. Router persists the `resolved_stores` JSON (`resolved_at` + statuses) on the profile
   row; response echoes it.
5. Next ingest (boot or later store-scoped cards) stamps `offers.store_id` with
   prefixed external ids — never overwriting chain-level NULL rows.
6. `GET /api/menu`: offers filtered by selected chains (existing) → store clause
   (`store_id IN resolved-for-chain OR store_id IS NULL`; errored chain = chain-level
   only) → dedup preferring store-level rows; planner unchanged; response carries
   `offer_sources`.

## 7. Rejected alternatives (and why)

- **Menu-time resolution** — puts 2–5 network calls on the hot read path; failure mode
  invisible to the user (§1).
- **Separate `resolved_store` table** — duplicates the profile→stores relationship
  `selected_stores` already models; JSON on the profile row is one mechanism.
- **`store_id` in the UNIQUE constraint** — SQLite can't ALTER a constraint; a nullable
  UNIQUE breaks chain-level idempotency (NULLs distinct). Identity stays
  `(grocer_id, external_id, week_key)`; the store scoping lives in the upsert MATCH KEY
  and the prefixed external id instead (§3).
- **Drop-and-recreate offers migration** — discards 279 live offers for a one-statement
  ALTER; recreate buys nothing.
- **Dedicated `POST /api/stores/resolve` endpoint** — `GET /api/stores?postal_code=` +
  resolve-on-save already answer preview and persistence; a third route is a second
  mechanism beside an existing one.
- **Extending `src/fetcher/adapters/` with locators** — mixes the RawFeed offer contract
  with a locator contract in one package; the shared parts (get_text, session injection,
  fail-tolerance) are imported, not duplicated.
- **Coop shortlist-then-detail** — impossible: the basic list has no coordinates
  (T10a §3a). Rejected in favor of the daily all-787 detail cache (§2, §10-F4).
- **Copied Coop APIM key constant** — rots silently on rotation; runtime fetch from
  `coopSettings` instead (§10-F9).

## 8. Offline-test strategy

All locator tests inject a fake `session` (httpx-like: `get(url, headers)` →
status_code/text/json), exactly the idiom `src/fetcher/grocer.py` documents:

- `tests/test_locator.py`: per-chain locate() against recorded fixture payloads (ICA
  search JSON, Willys 258-store list, Coop stores+details, Lidl nearby) — assert nearest-3
  ordering, dummy-store filtering (Willys zero-coord row), and mapping of ids/names.
- Fail-tolerance: one chain's locator raising/returning garbage → `resolve_stores` still
  returns the other chains' results plus the persisted `error` status; never raises.
- Geocode: Nominatim 200/404/network-error paths; cache hit issues no second request
  (counting fake session); **TTL expiry re-requests**; cache isolation between tests.
- Coop cache: cold start fetches all details once and persists the cache; second resolve
  issues 0 detail requests; cache survives a "reboot" (new process reading the file).
- Migration: boot against a pre-change DB fixture containing BOTH `offers` and `profile`
  with rows → all three columns added, rows intact; boot again → idempotent no-op;
  **concurrent-boot simulation: pre-create the column, boot → "duplicate column name"
  tolerated, app starts**; fresh DB → columns present.
- Upsert P0 regression: chain-level pull then store-scoped pull of the same catalog →
  the NULL `store_id` rows survive unchanged and the store-scoped rows are separate
  (prefixed external ids); reverse order too.
- Menu filter: offers with `store_id` matching/not-matching resolved stores, NULL
  store_id, no-resolved-stores profile (byte-identical to today — regression guard),
  errored-chain status (chain-level rows only), and the dedup case: same product as NULL
  row + resolved-store row → exactly one survives and it is the store-level one;
  `andel_extrapris` not double-counted.
- API: PUT profile with/without postal_code (422 on malformed; **absent postal_code
  leaves persisted value unchanged** — stale-client regression test; explicit null
  clears; per-chain error persisted + echoed, never 500); GET /api/stores?postal_code=
  **401 unauthenticated, 200 authenticated**; GET /api/profile roundtrip.

## 9. Known limitations (stated, not hidden)

- Willys catalog↔store matching joins on `flyerURL` store number with a name-string
  fallback (T10a §2b caveat) — unmatched stores are logged, stores without a Tjek
  catalog fall back to chain-level.
- Coop store-scoped offers remain blocked on the dke resource path (devtools capture);
  Coop stays `store_id IS NULL` this card. Coop locator cold start costs ~787 one-time
  detail requests (then cached daily).
- Resolved stores go stale if the user moves without re-saving; `resolved_at` is
  persisted and shown in the UI so the state is visible, and an errored chain degrades
  to chain-level rows explicitly rather than silently.

## 10. Revision 2 (DA cycle 1) — what changed per finding

Addressed from `/srv/workspace/matapp/.audits/202609260913-e6190a72/T10c-da-verdict.md`
(VERDICT FIX). Every P0/P1/P2/P3 addressed; none rejected.

- **F1 (P0, upsert retraction):** §3 rewritten. Store-scoped rows get
  `external_id = f"{store_id}:{hotspot_id}"` at ingest AND the `upsert_week` match key
  gains `store_id or ""`; a store-scoped write can never match/overwrite a
  `store_id IS NULL` row. The old "collisions are not expected / last-writer-wins
  accepted" claim is retracted — the DA showed the design's own Willys ingest plan
  creates the collision. Regression test added (§8).
- **F2 (P1, filter double-count):** §4 menu row now specifies a dedup step after the
  store clause: `(grocer_id, normalized name)`, preferring the store-level row;
  chain-level is the fallback only when no store-level row matched. Test added (§8).
- **F3 (P1, profile migration):** §3 now specifies guarded ALTERs for ALL THREE columns
  (`offers.store_id`, `profile.postal_code`, `profile.resolved_stores`); the
  self-contradictory "create_all covers profile" parenthetical is deleted. Migration
  test boots against a fixture with BOTH tables (§8).
- **F4 (P1, Coop circularity):** §2 `coop.py` redesigned: daily persisted cache of all
  787 store details, haversine over cached coordinates; cold-start cost stated (§9).
  Cache tests added (§8).
- **F5 (P1, unauthenticated amplification):** §4 stores row: `?postal_code=` is
  auth-gated (401 when anonymous); geocode TTL cache + per-process resolve cache bound
  repeat cost. Test added (§8).
- **F6 (P2, clear-on-absent):** §4 profile row: absent `postal_code` = unchanged;
  explicit null/"" clears. Stale-client regression test added (§8); UI sends the field
  only when edited (§5).
- **F7 (P2, status/resolved_at/TTL):** §2 persistence shape now carries `resolved_at`
  and per-chain `status`/`error`; menu filter treats an errored chain as chain-level
  rows only (§4); UI shows `resolved_at` (§5); geocode cache given a 24 h TTL (§2).
- **F8 (P2, ALTER race):** §3 migration step tolerates `OperationalError: duplicate
  column name` as success (re-inspect to confirm); concurrent-boot test added (§8).
- **F9 (P3, key sourcing + label join):** §2 `coop.py` fetches the APIM key from
  `coopSettings` at resolve time (cached); §3 Willys join prefers `flyerURL` store
  number → Tjek label, name join demoted to fallback.

# VERDICT: SHIP
