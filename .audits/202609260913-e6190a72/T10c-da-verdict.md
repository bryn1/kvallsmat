# T10c — Devil's advocate: adversarial gate on T10b-design.md (MC 1355.14, parent 1355)

Attacked 2026-09-26 against HEAD 1b641a5. Inputs: T10b-design.md (the design under
attack), T10a-store-locators.md, T7b-geographic-scope.md, and the real code:
`app/models/profile.py`, `app/models/store_selection.py`, `app/routers/profile.py`,
`app/routers/stores.py`, `app/routers/menu.py`, `app/main.py`, `app/db.py`,
`app/profile_service.py`, `src/offers_db/store.py`, `src/fetcher/adapters/tjek.py`,
`src/fetcher/grocer.py`, `database.py`. Live schema verified this session via
`PRAGMA table_info` on a checkout DB: `offers` has NO `store_id`, `profile` has NO
`postal_code`/`resolved_stores` — both migrations are real, not theoretical.

**Bottom line: FIX.** The resolve-once-at-save decision, the reuse-first package split
and the no-new-endpoint stance are sound and survive attack. But the design contains one
P0 (store-scoped upsert silently RETRACTS chain-level offers from every other user), two
P1s in the filter/migration semantics, one P1 that makes the Coop locator as specified
unimplementable, and one P1 unauthenticated network-amplification endpoint. None are
hard to fix, but all must be fixed in the design before build.

---

## P0 — Store-scoped upsert RETRACTS chain-level offers fleet-wide (identity collision + last-writer-wins)

**Design under attack:** T10b §3 ("Identity stays `(grocer_id, external_id, week_key)`
… collisions with chain-level rows are not expected; if one occurs, `upsert_week`'s
existing last-writer-wins update is the accepted POC behavior").

**Refutation: the collision is not hypothetical — the design's own ingest plan creates it.**
T10a §2b (VERIFIED) establishes that Willys' Tjek dealer listing `c371GA` holds ONLY
per-store catalogs (24 catalogs, each labeled per store, `store_id: null` on every
catalog row). The existing chain-level Willys pull (`src/fetcher/adapters/tjek.py`,
`pick_catalog`) therefore already ingests ONE STORE's catalog and stamps its rows
`store_id = NULL` — "valid everywhere". When the design's store-scoped ingest (§3,
"Tjek adapter gains an optional store_id parameter") later pulls the SAME catalog for
the resolved store, `upsert_week` (`src/offers_db/store.py`, the `setattr(existing, k, v)`
loop) matches on `(grocer_id, external_id, week_key)` — identical, because the hotspot
ids are the same — and **overwrites `store_id NULL → '2103'`**. Under the design's own
filter (`store_id IN resolved OR store_id IS NULL`), every user whose resolved Willys
store is NOT 2103 instantly loses those offers. One store-scoped ingest silently narrows
the whole chain's menu. The design's "collisions are not expected" is contradicted by
its own population plan; "last-writer-wins is accepted POC behavior" names the mechanism
but not the damage (a retraction, not a duplicate).

**Fix:** one of (a) scope the external id at ingest: store-scoped rows are written as
`external_id = f"{store_id}:{hotspot_id}"` so they never collide with chain-level rows;
(b) add `store_id` to the upsert match key (keep the UNIQUE constraint as-is; the match
is in `upsert_week`, not the constraint); and in all cases (c) never overwrite an
existing `store_id IS NULL` row with a store-scoped value — insert a new row instead.
Add a regression test: chain-level pull then store-scoped pull of the same catalog →
the NULL rows must survive.

## P1 — Filter double-counts a product that exists both chain-level and store-level

**Design under attack:** T10b §4 menu row ("keep an offer when `o.store_id is None` OR
`o.store_id` is among the resolved store ids").

**Refutation:** the OR-clause keeps BOTH rows when the same product exists as a
chain-level row (NULL) and a store-level row (different external id — which §3 itself
predicts: "store-scoped payloads carry their own external ids"). `plan_menu`
(`src/planner/menu.py` §"rank candidates by descending offer-hit count") counts offer
hits per dish; both rows hit, `used_offer_ids` can carry both, and `andel_extrapris`
(`app/routers/menu.py`, computed over the filtered `offers` list) sums the savings of
the same physical product twice. The design never states a dedup or precedence rule.

**Fix:** after the store filter, dedup by `(grocer_id, normalized name)` preferring the
store-level row when the profile has resolved stores for that chain (chain-level row is
the fallback only when no store-level row matched). One helper in the menu router or
`src/offers_db/`; test: same product as NULL row + resolved-store row → exactly one
survives, and it is the store-level one.

## P1 — Profile-column migration is waved off; live PUT /api/profile will 500

**Design under attack:** T10b §3 parenthetical ("Same guarded-ALTER pattern is reused if
`profile.resolved_stores` needs backfill — it does not: new column, `create_all` covers
fresh tables, ALTER covers existing ones") and §2's "a nullable `resolved_stores` TEXT
column on `profile`".

**Refutation:** the design's own §3 states the correct fact for `offers` —
"`Base.metadata.create_all` does not add columns to existing tables" — and then exempts
`profile` from the same rule with no mechanism. The `profile` table already exists in
any deployed DB (verified: `PRAGMA table_info(profile)` returns the seven current
columns, no `postal_code`, no `resolved_stores`). After this change,
`profile_service.save_profile` assigns `row.postal_code` → `OperationalError: no such
column` → **PUT /api/profile 500s on the live DB** until someone hand-runs an ALTER the
design never specifies. The sentence as written is self-contradictory ("create_all
covers fresh tables, ALTER covers existing ones" — but no ALTER for profile is specified
anywhere).

**Fix:** the boot migration step in `app/db.py` performs guarded ALTERs for ALL THREE
columns: `offers.store_id`, `profile.postal_code`, `profile.resolved_stores`. Test
§8's migration case must boot against a pre-change fixture containing BOTH tables and
assert both survive with rows intact.

## P1 — Coop locator as specified is circular (cannot shortlist before it has coordinates)

**Design under attack:** T10b §2 `coop.py` ("then detail-fetch lat/lon for the
haversine-shortlisted candidates only (not all 787)").

**Refutation:** per T10a §3a (VERIFIED), the basic 787-row list carries
`storeId/ledgerAccountNumber/name/conceptId/url` — **no latitude/longitude**; coordinates
come only from the per-store detail fetch (`/stores/{ledgerAccountNumber}`). Haversine
shortlisting REQUIRES the coordinates, so "shortlist, then detail-fetch the shortlist"
is circular: the shortlist cannot be computed before the detail fetches it is supposed
to avoid. As written, the Coop locator returns nothing. T10a's own risk note ("787
detail fetches should be cached, not per-request") points at the only working shape.

**Fix:** fetch all 787 details once into a daily cache (file or DB-backed, not just
in-process — a cold boot must not re-issue 787 requests), haversine over the cached
coordinates, nearest 3. State the cold-start cost explicitly (one-time ~787 requests,
then 0/day).

## P1 — `GET /api/stores?postal_code=` is unauthenticated outbound-call amplification

**Design under attack:** T10b §4 stores row ("resolve-preview for the UI before
saving… behavior byte-identical without the param").

**Refutation:** `app/routers/stores.py` has **no auth dependency** on any route
(verified: `list_stores` takes only `session`). Adding a query param that fires the full
locator pipeline (Nominatim + ICA token + ICA search + Willys list + Coop list + Lidl)
per request puts 2–5 unauthenticated outbound HTTP calls behind one anonymous GET.
Nominatim's usage policy is max 1 req/s with a descriptive UA (T10a §0) — a scripted
client hammering `?postal_code=` gets the shared host IP rate-limited or blocked, taking
down geocoding for the whole app (profile saves included). This is the same
"silent total failure" class the design itself invokes in §1, introduced by the design.

**Fix:** require the authenticated user for the `postal_code` param (401 when absent —
consistent with the profile/menu gates), plus reuse the geocode cache and add a small
per-process resolve-result cache keyed by postal_code. State the auth expectation in §4.

## P2 — "Save WITHOUT postal_code clears both fields" breaks in-flight frontend sessions

**Design under attack:** T10b §4 profile row ("A save WITHOUT postal_code clears both
fields").

**Refutation:** the deployed frontend (`static/js/ui/profile.js`) does not send
`postal_code` today. A user with the page already open across the deploy saves their
profile (persons/budget edit) → the PUT body has no `postal_code` → their saved
postnummer and resolved stores are silently wiped. Additive-field compatibility is
correctly claimed for GET, but the clear-on-absent rule makes PUT destructive for the
existing client.

**Fix:** absent field = leave persisted value unchanged; only an explicit
`postal_code: null` (or `""`) clears. One line in `ProfileBody` semantics, one test.

## P2 — Stale/partial resolved_stores persist forever with no status, no re-resolve path

**Design under attack:** T10b §1 ("Failure becomes visible and per-chain") and §9
(staleness acknowledged only for "user moved").

**Refutation:** the design does not say whether a failed chain's error entry is
PERSISTED or only echoed. If only echoed: a transient ICA outage during save persists a
resolved list missing ICA, and nothing ever re-resolves — the failure is visible for one
response, then invisible forever, which is exactly the silent-fallback behavior §1
rejects menu-time resolution for. If persisted: error entries must be distinguishable
from stores in the menu filter. Also the geocode dict cache never expires, so a bad
cached geocode outlives the data it came from.

**Fix:** persist `resolved_at` + per-chain status (`ok`/`error: <reason>`) alongside the
stores; the menu filter treats an errored chain as "chain-level rows only" explicitly;
UI shows resolved_at so staleness is visible. Give the geocode cache a TTL (or clear it
on save failure).

## P2 — Guarded ALTER is check-then-act; concurrent boot crashes

**Design under attack:** T10b §3 ("inspect the `offers` table; if `store_id` is absent,
run the ALTER").

**Refutation:** two processes booting concurrently (multi-worker deploy, or boot ingest
overlapping a web boot) both inspect-absent, both ALTER; the second gets
`OperationalError: duplicate column name` and — since `boot()` runs inside `lifespan`
before `yield` (`app/main.py`) — the app fails to start. SQLite DDL is transactional so
partial migration is not the risk; the race is.

**Fix:** wrap the ALTER in try/except OperationalError and treat "duplicate column
name" as success (re-inspect to confirm). Cheap, removes the race entirely.

## P3 — Coop APIM key sourcing is ambiguous; Willys label-join can be strengthened

- §2 `coop.py` says "the page-sourced key" — if that means a constant copied from the
  page, it rots silently (rotates → per-chain error, visible, but permanently until a
  code change). Fix: fetch `coopSettings` from `www.coop.se/butiker-erbjudanden/` at
  resolve time (one extra GET, cacheable) exactly as T10a did, or name the config owner
  of the key.
- §3 Willys matching is a name string join ("Willys " + store.name). T10a shows the
  store list carries `flyerURL`/`storeId` and the storeflyer endpoint returns the
  catalog name — prefer joining on `flyerURL` store number → Tjek label, keep the name
  join as fallback. (Design already logs unmatched; keep that.)

## P4 — What I could NOT break (honest negatives)

- **Resolve-once-at-save vs menu-time (§1):** the latency/failure-visibility argument
  holds; I found no failure mode of save-time resolution that menu-time would have
  avoided (the staleness case is symmetric and the UI-surfacing fix above covers it).
- **No-new-endpoint stance (§4, §7):** `?postal_code=` preview + resolve-on-save do
  answer both needs; the P1 above is about auth, not about the route decision.
- **Offline-testability (§8):** the `session=None` injection idiom is real and
  sufficient (`src/fetcher/grocer.py` documents it; `tjek.py` uses it) — per-chain
  fixtures + counting fake session cover everything except the geocode-cache isolation
  noted in P2. No network needed.
- **`?week=` / planner / auth paths:** untouched by the design; no coupling found.
- **`offer_sources` response addition:** additive, `used_offer_ids` kept — no contract
  break found beyond the P2 clear-on-absent rule.

## Summary table

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| 1 | P0 | Store-scoped upsert overwrites NULL rows → retracts offers fleet-wide | scope external_id / match key / never overwrite NULL |
| 2 | P1 | Filter double-counts product in chain-level + store-level rows | dedup preferring store-level |
| 3 | P1 | profile.postal_code/resolved_stores migration unspecified → PUT 500 on live DB | guarded ALTERs for all 3 columns |
| 4 | P1 | Coop shortlist-before-detail is circular | cache all 787 details daily |
| 5 | P1 | Unauthenticated `?postal_code=` = outbound-call amplification (Nominatim ban risk) | auth-gate param + caches |
| 6 | P2 | PUT without postal_code wipes saved fields from stale clients | absent = unchanged |
| 7 | P2 | Failed-chain resolution persisted without status; no re-resolve; geocode cache immortal | persist status+resolved_at, TTL |
| 8 | P2 | Concurrent boot ALTER race | tolerate duplicate-column |
| 9 | P3 | Coop key sourcing ambiguous; Willys name-join fragile | fetch key at runtime; join on flyerURL |

# VERDICT: FIX
