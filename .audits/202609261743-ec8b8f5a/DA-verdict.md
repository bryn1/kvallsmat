# T10f — DA verdict: adversarial gate over the T10e BUILD (store-level selection)

Reviewed 2026-09-26 by the `devils-advocate` profile against build commit `793f991`
(23 files, +1769/−16) on main, parent a501929. Design pinned: `.audits/202609260913-e6190a72/T10b-design.md`
REVISION 2 (SHIP by T10d-da-verdict-c2.md). Attack the code, not the design.

Suite re-run by THIS gate (clean `__pycache__`/`.pytest_cache` first):
`/srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q` →
`95 passed, 3 warnings in 7.81s` — **EXIT=0** (VERIFIED this session).

## Ranked findings

### P1-1 — `pull_store_scoped` has NO production caller: the pinned design's Willys population step is not wired (disclosed, but it is a scope reduction)
Evidence: `grep -rn "pull_store_scoped" src/ app/` hits only `src/fetcher/adapters/tjek.py:183`
(definition) and the tests. The ONLY production `upsert_week` caller is
`src/scheduler/periodic.py:80`, which ingests chain-level rows exclusively — no path
stamps `offers.store_id` from a live pull. T10b §3 ("Population") explicitly puts the
Willys store-scoped ingest ("joins resolved store → catalog on `flyerURL` store number →
Tjek label first") inside THIS card's scope; only ICA is named a follow-up card. T10b §6
step 5 ("Next ingest … stamps `offers.store_id`") therefore never fires in the running
product: a user who saves a postnummer gets resolved stores rendered, but the menu store
clause and dedup operate on an empty store-scoped set forever until a future card wires
the ingest. The build record discloses the deferral (§2 F9 note) and the live sanity
honestly shows `store_scoped_sources` empty — the disclosure is honest, but the
deviation from the pinned design is material: the headline feature has no live data
path. FIX = either wire the Willys store-scoped ingest (periodic/boot pass resolving
the profile's stores → `pull_store_scoped`), or land an explicit owner ruling that the
population step moves to a follow-up card, recorded in the design/build record.

### P2-1 — No endpoint-level test proves the store clause/dedup run inside `GET /api/menu`
Evidence: `tests/test_store_scoping.py` exercises `_apply_store_clause`/`_dedup_by_name`
directly (lines 226–277); the only HTTP menu test, `test_menu_response_carries_offer_sources`
(line 407), asserts the `offer_sources` SHAPE only — it upserts a chain-level row and
never asserts that a non-matching store-scoped row is EXCLUDED, or that dedup collapses,
through the endpoint. If `app/routers/menu.py:141-142` stopped calling the two helpers,
the entire suite stays green. The wiring is correct today (read and confirmed), but the
regression guard the design promised (§8 "byte-identical … regression guard") exists only
at helper level. FIX: one endpoint test — upsert a store-scoped row for an UNRESOLVED
store id + a chain-level row, GET /api/menu with the FAKE_RESOLVE profile, assert the
unresolved row is absent and the store-level survivor wins.

### P2-2 — `GET /api/stores?postal_code=` does not validate or normalize the param
Evidence: `app/routers/stores.py:59,72-73` passes the raw query string straight into
`resolve_stores_cached` → `geocode_postal`, which interpolates it into the Nominatim URL
(`src/locator/geocode.py:47-48`, `f"...postalcode={postal_code}&country=Sweden..."`).
PUT /api/profile validates `^\d{3}\s?\d{2}$` and normalizes to digits
(`app/routers/profile.py:36,93-98`); the preview does neither. Consequences: (a) an
authenticated client can issue arbitrary-string Nominatim queries (auth-gated, so not
the F5 amplification class, but unbounded in *variety* — the 128-entry resolve cache is
keyed on the raw string, so every distinct junk string is a fresh outbound call);
(b) `"414 51"` is NOT normalized on the preview path, so the URL carries a raw space and
the preview can resolve differently from the saved profile for the same input. No
injection into the path (query-string only, httpx encodes), so P2 not P1. FIX: reuse the
same regex+normalize on the preview param (422 or empty-result on malformed).

### P3-1 — `profile.js` injects third-party strings via `innerHTML` unescaped
Evidence: `static/js/ui/profile.js:66` — `el.innerHTML = lines.map((l) => `<p>${l}</p>`).join('')`
where `lines` embed `s.store_name` (line 57) and the raw per-chain `entry.error`
exception text (line 60). Store names come from ICA/Willys/Coop APIs and error strings
from exception messages; neither is escaped. Exposure is the authenticated user's own
page (self-contained), hence P3, but a hostile upstream response becomes HTML in the
user's session. FIX: textContent-per-`<p>` construction or an escape helper.

### P3-2 — `suggestions.js` renders the raw store_id, not the store name the design promised
Evidence: `static/js/ui/suggestions.js:54-57,34` maps `offer_id → s.store_id` and renders
`butik: 2103`. T10b §5 says "append the store name to the offer tooltip/line"; the build
record calls these "store labels". The data to do better (`offer_sources` could carry the
name, or the profile's resolved stores could be joined client-side) exists. Cosmetic,
disclosed-adjacent, P3.

### P3-3 — Coop cold start (~787 sequential requests) runs inside the first `PUT /api/profile` request
Evidence: `app/routers/profile.py:124` calls `resolve_stores` (uncached) synchronously in
the request handler; `src/locator/coop.py:63` warms the detail cache lazily inside
`locate` on a cold cache. The build record's N2 note ("the 787-fetch warm is never run
inside `PUT /api/profile`'s boot path") is literally true for *boot* but misleading: the
warm DOES run inside the first profile-save HTTP request after a cache wipe — minutes of
latency or a client/proxy timeout on a POC host. The design states the cold-start cost
(§9), so this is a stated limitation, not a hidden one; P3. FIX (optional): warm the Coop
cache in a background task at boot, or bound the warm per request.

### P4-1 — Unguarded reverse direction of rule 1
`_guard_bare_id_reuse` (`src/offers_db/store.py:99-113`) fires only on store-scoped
INSERTs. A chain-level write whose bare external_id collides with an EXISTING prefixed
store-scoped id (e.g. a Tjek offer literally named `2103:hs1`) finds no NULL match,
passes no guard, and dies on `uq_offer` as an IntegrityError inside
`periodic.run_weekly` (caught only at the boot-ingest boundary, `app/main.py:48`).
Astronomically unlikely with Tjek uuid ids — recorded, not actionable.

### P4-2 — `.tmp/` is untracked and not gitignored in the repo
`git status --short` → `?? .tmp/`. Scratch lives in the sanctioned place, but adding
`.tmp/` to `.gitignore` would silence the noise. Hygiene nit only.

## Per-attack-area verdicts

1. **P0 invariant (no write path overwrites a `store_id IS NULL` row)** — HOLD. Every
   `upsert_week` caller enumerated: only `src/scheduler/periodic.py:80` (chain-level,
   rows carry no `store_id` key → `row.get("store_id") or None` → NULL → `_match`
   filters `store_id IS NULL` only, `src/offers_db/store.py:91-96`). No other
   `Offer(...)` construction or direct offers INSERT exists (grepped). The match-key
   split + prefixed ids + loud bare-id guard + both-orders regression test
   (`test_p0_store_scoped_write_never_overwrites_chain_level_row`) close the T10c F1
   hole. I could not break it.
2. **Migration** — HOLD. `app/db.py:75-108` covers all three columns; `ensure_columns`
   runs inside `boot()` (line 68) BEFORE `get_db` serves any session, and every DB-touching
   service (`profile_service._ensure_db`, `auth_service`) funnels through `boot()`. The
   duplicate-column race is tolerated only after a confirming re-inspect (lines 101-107);
   tests cover pre-change-with-rows, idempotence, the race, and fresh DB.
3. **Menu filter + dedup** — HOLD at helper level (NULL handling, errored chain,
   chain-separated casefold+strip key, position-preserving store-level preference all
   verified by reading and by tests). Off-by-one: none found. Gap: see P2-1.
4. **Auth-gating** — HOLD. `?postal_code=` (including `""`) hits
   `auth_service.current_user_or_401` before any resolve (`stores.py:70-73`); anonymous
   no-param path returns the same catalog list construction as before (byte-identical
   claim supported by `test_stores_postal_code_preview_auth_gated` asserting a plain
   list). 401/200 both tested.
5. **Absent-means-unchanged PUT** — HOLD. `model_fields_set` discrimination
   (`profile.py:90-104`); stale-client, explicit-null-clears, and malformed-422 all
   tested. A stale client cannot wipe `postal_code`/`resolved_stores`.
6. **Test quality** — mostly real-implementation (upsert/migration/menu helpers run real
   code against real SQLite; locators run real parsers against fixture payloads; only
   the resolve boundary is monkeypatched, which is the right seam). One false-green
   window: P2-1.
7. **Recorded deviations** — suggestions.js-instead-of-app.js: honest and correct (the
   day rendering lives there). Coop `{"stores":[...]}` wrap: honest, code tolerates both
   shapes (`coop.py:92-93`). Boot-ingest deferral: honestly DISCLOSED but it deviates
   from the pinned design's in-scope population step — P1-1.

## Bottom line

The P0 invariant, migration, auth-gating and PUT semantics — the things this card exists
to guarantee — are solid and test-backed. The one material defect is that the feature's
data never flows: nothing in production ever produces a store-scoped row, so the menu
store clause is dead code until a follow-up wires the Willys ingest (or an owner ruling
accepts the deferral). That is a scope deviation from the pinned design, not a code bug
in what was built — hence FIX, not RECONSIDER, and a small fix: wire it or rule it.

# JUDGED: 44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a
# VERDICT: FIX
