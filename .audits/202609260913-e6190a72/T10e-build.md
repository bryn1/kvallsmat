# T10e — Build: store-level selection per postnummer (MC 1355.16, parent 1355)

Built 2026-09-26 by the `code` profile against T10b-design.md **REVISION 2**
(pinned SHIP by T10d-da-verdict-c2.md). One build commit on main, not pushed:

**Commit: `793f991fda6cc0f761d01936765f72900f5acce6`** —
`matapp: store-level selection per postnummer (MC 1355.16)`
(23 files changed, 1769 insertions(+), 16 deletions(-); parent a501929)

## 1. Diff summary

| Area | Files | Change |
|---|---|---|
| New locator package | `src/locator/{__init__,geo,models,geocode,ica,willys,coop,lidl}.py` | `resolve_stores(postal_code, chains, session=None)` + `CHAIN_LOCATORS` registry; Nominatim geocode with 24 h TTL cache; per-chain locators reusing `_common.get_text/get_json` and the session-injection idiom; fail-tolerant per chain; bounded resolve-result cache (TTL 24 h, max 128) |
| Schema + migration | `src/offers_db/store.py`, `app/models/profile.py`, `app/db.py` | `offers.store_id` (nullable), `profile.postal_code`, `profile.resolved_stores` (Text/JSON); `ensure_columns()` guarded ALTERs for ALL THREE columns in `boot()`, duplicate-column race tolerated after re-inspect |
| Tjek ingest | `src/fetcher/adapters/tjek.py` | `pull_store_scoped()` stamps `external_id = "{store_id}:{hotspot_id}"` + `store_id`; catalog matched on label (casefold+strip); unmatched store logged, never silent |
| Upsert | `src/offers_db/store.py` | match key gains `store_id-or-empty`; bare-id reuse with a store scope raises `ValueError` LOUD |
| Menu | `app/routers/menu.py` | store clause (`store_id IN resolved OR NULL`), dedup keyed `(grocer_id, casefold+strip name)` preferring the store-level row, `offer_sources` in `MenuResponse` |
| Profile API | `app/routers/profile.py`, `app/profile_service.py`, `app/auth_service.py` | postal_code absent-means-unchanged PUT semantics, `^\d{3}\s?\d{2}$` validation → digits-only, resolve-on-save persisted with `resolved_at` + per-chain status, never a 500; shared `current_user_or_401` dependency |
| Stores API | `app/routers/stores.py` | `GET /api/stores?postal_code=` auth-gated preview (401 anonymous); anonymous no-param behavior byte-identical |
| UI | `templates/index.html`, `static/js/ui/profile.js`, `static/js/ui/suggestions.js` | postnummer field (sent only when edited), resolved-stores rendering with per-chain status + `resolved_at`, offer_sources store labels in the menu view |
| Tests | `tests/test_locator.py` (311 l), `tests/test_store_scoping.py` (427 l) | offline fixture tests, no network |

Note: the design §5 names `app.js` for the offer_sources display, but the day
rendering lives in `static/js/ui/suggestions.js` (`renderSuggestion`) — the
change went there (same concern, no new mechanism).

## 2. Per-DA-finding implementation notes

- **F1 (P0 retraction)** — closed by three mechanisms: prefixed store-scoped
  external ids at ingest (RULE 1, stated in `upsert_week` + `pull_store_scoped`
  docstrings as the ONLY sanctioned ingest path), match key
  `(grocer_id, external_id, week_key, store_id or "")`, and the P0 regression
  test `test_p0_store_scoped_write_never_overwrites_chain_level_row` (both
  orders; NULL rows survive unchanged).
- **F2 (P1 double-count)** — `_dedup_by_name` runs after the store clause,
  before `plan_menu`; key `(grocer_id, name.casefold().strip())` (N3);
  `test_dedup_prefers_store_level_row_and_counts_once` proves one survivor.
- **F3 (P1 migration)** — `app/db.py ensure_columns()` covers all three
  columns; tests: pre-change DB with rows (columns added, rows intact),
  idempotent re-run, concurrent-boot duplicate-column race, fresh DB.
- **F4 (P1 Coop circularity)** — `coop.py`: daily FILE-backed cache of ALL
  store details, haversine over cached coordinates, nearest 3;
  `test_coop_second_resolve_zero_detail_requests` + cache-survives-reboot test.
- **F5 (P1 anonymous preview)** — `GET /api/stores?postal_code=` raises 401
  via the shared `auth_service.current_user_or_401`; no-param anonymous calls
  unchanged; `test_stores_postal_code_preview_auth_gated`.
- **F6 (P2 clear-on-absent)** — absent `postal_code` = unchanged (stale-client
  test), explicit null/"" clears both fields; UI sends the field only when
  edited.
- **F7 (P2 status/resolved_at/TTL)** — `resolved_at` + per-chain
  `status`/`error` PERSISTED in `profile.resolved_stores`; errored chain =
  chain-level rows only (`test_store_clause_errored_chain_contributes_
  chain_level_only`); geocode cache 24 h TTL; UI shows `resolved_at`.
- **F8 (P2 ALTER race)** — `ensure_columns` tolerates `duplicate column name`
  after a confirming re-inspect; `test_migration_tolerates_concurrent_boot_
  duplicate_column`.
- **F9 (P3 key sourcing + label join)** — `coop.py` fetches the APIM key from
  the `coopSettings` page blob at resolve time (cached with the store cache,
  never a copied constant); Willys catalog match is label-first (the store
  name IS the Tjek label; the flyerURL store-number join is the ingest-wiring
  follow-up, ICA store-scoped ingest is a named follow-up card per design §3).
- **N1 (rule 1 + loud failure)** — RULE 1 stated in code; `pull_store_scoped`
  requires store_id+label (raises otherwise); `upsert_week._guard_bare_id_
  reuse` raises `ValueError("...rule 1 violated...")` on a bare-id
  reappearance — `test_upsert_bare_id_reuse_fails_loud`.
- **N2 (Coop cold-start semantics)** — stated in `coop.py` header: re-fetch
  from scratch on partial cache (partial run persists NOTHING —
  `test_coop_partial_run_persists_nothing`); warm is LAZY (inside the first
  resolve), NOT synchronous inside boot; the 787-fetch warm is never run
  inside `PUT /api/profile`'s boot path — it runs once per cache lifetime.
- **N3 (dedup key in code)** — `(grocer_id, name.casefold().strip())`,
  unit-ignoring, chain-separating — `test_dedup_key_ignores_unit_but_not_chain`.
- **N4 (bounded caches)** — geocode cache TTL 24 h; resolve-result cache TTL
  24 h + max 128 entries with oldest-eviction —
  `test_resolve_cache_bounded_ttl_and_size`.

## 3. Live sanity (real network, run ONCE — outputs in `.tmp/live_sanity_output.json`, `.tmp/live_menu_output.json`)

**Resolve 41451 → nearest store per chain (VERIFIED live):**
- ica: ICA Nära Effkå, ICA Supermarket Majorna, ICA Nära Toppen, Göteborg
- willys: Willys Hemma Göteborg Majorna (1.343 km), Vegastaden (2.029 km), Första Långg (2.284 km)
- coop: Coop Mariagatan (0.746 km), Coop Eriksberg (1.964 km), Coop Göteborg Andra Långgatan (2.164 km) — cold start fetched all details once, cache written
- lidl: Gbg Biskopsgården (2.8 km), Gbg Kungsgatan (3.1 km), Gbg Frölunda Marconimotet (3.7 km)

**Store-scoped Tjek feed:** the nearest Willys store (Majorna) has NO Tjek
catalog this week — the designed logged fallback fired (warning, empty feed).
Demonstrated on a catalog-labeled store: **Willys Alingsås Hagaplan (id 2149):
111 entries, all stamped `2149:<hotspot>` + `store_id: "2149"`**.

**Menu journey (scratch DB copy, real ingest + real resolve):** boot ingest ok;
register+login 200; `PUT /api/profile` with `postal_code: "41451"` → 200, all
four chains `ok` with the names above persisted; `GET /api/menu?week=2026-W39`
→ 200, **255 offer_sources**, 15/15 days carrying `used_offer_ids`
(`store_scoped_sources` empty — expected: the boot ingest is chain-level;
store-scoped rows appear only via the store-scoped ingest path, proven in the
feed pull and the offline tests).

## 4. Fresh test suite

Cleaned `__pycache__`/`.pytest_cache`, then:
`/srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q` →

```
95 passed, 3 warnings in 8.14s
EXIT=0
```

(95 = 71 pre-existing + 24 new; full output `.tmp/final_suite.txt`.)

## 5. DoD checklist

- Commit hash on main implementing revision 2 — PASS (`793f991`, locator package, three guarded ALTERs, store-scoped Tjek ingest, menu dedup+filter+offer_sources, auth-gated preview, UI)
- Offline fixture tests incl. the P0 regression test — PASS (24 new tests, both files listed above)
- Fresh suite EXIT=0 — PASS (95 passed, EXIT=0, quoted above)
- Live sanity recorded — PASS (§3, raw outputs in `.tmp/`)

Orchestrator re-run 2026-09-26: find . -name __pycache__ -exec rm -rf; /srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q -> "95 passed, 3 warnings in 7.70s"
VERIFY_EXIT=0

## Fixround (T10f cycle 1) — MC 1355.17

DA gate over the build: cycle 1 FIX (`DA-verdict.md`), cycle 2 SHIP after the
P2 fixes (`DA-verdict-c2.md`; P2-1 endpoint-level menu test + P2-2 preview
param validation landed in 2f44683 by the fix child). The cycle-2 verdict
flagged this session's in-flight wiring diff and ruled: finish and commit the
wiring card, or drop it — the orchestrator ordered the wiring. This fixround
lands it, plus the P3 items:

- **P1-1 (wired)** — `src/scheduler/periodic.py` gains the PRODUCTION caller
  of `pull_store_scoped`: `run_store_scoped_ingest` joins each resolved Willys
  store to its Tjek catalog label via the storeflyer endpoint (the design's
  flyerURL store-number join; the store's own name string is the fallback),
  pulls the store-scoped feed, normalizes and upserts WITH `store_id` (RULE 1
  prefixed ids; the chain-level NULL row is untouched — tested). Fail-tolerant
  per store. `periodic.main` gains an optional `resolved_stores` kwarg;
  `app/main.py run_boot_ingest` gathers every saved profile's persisted
  `resolved_stores` (app layer owns the profile read — no src→app import) and
  passes it, so T10b §6 step 5 ("next ingest stamps offers.store_id") now
  fires at boot. ICA store-scoped ingest remains the design's named follow-up
  card (stated here explicitly, per the orchestrator's instruction).
- **P2-1** — already fixed in 2f44683 (`test_menu_endpoint_applies_store_
  clause_and_dedup`, red-capable at endpoint level).
- **P2-2** — already fixed in 2f44683 (preview param uses the SAME
  `POSTAL_CODE_RE` + digits-only normalization; malformed → 422).
- **P3-1** — `profile.js renderResolved` builds `<p>` nodes with
  `textContent` (store names + error strings are third-party data; no
  `innerHTML`).
- **P3-2** — `MenuResponse.offer_sources` gains `store_name` (joined from the
  persisted resolution in `menu.py::_resolved_store_names`);
  `suggestions.js` renders `butik: <store name>` with the raw id as fallback.
- **P3-3** — `.tmp/` added to `.gitignore` (DA P4-2).
- **P4-1** — left as a recorded finding per the gate (unguarded reverse
  direction of rule 1; astronomically unlikely with Tjek uuid ids).

New tests: `tests/test_ingest_wiring.py` (208 lines — collect/dedupe, label
join + fallback, upsert-with-store_id + NULL-row survival, per-store
fail-tolerance, `periodic.main` end-to-end with the resolved_stores kwarg) and
`test_menu_offer_sources_carry_store_name` in `tests/test_store_scoping.py`
(kept under the 600-line ceiling by the split). Fresh suite, BOTH interpreters:

```
/srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q
  -> 103 passed, 3 warnings in 9.43s   EXIT=0
/usr/bin/python3 -m pytest -q -p no:cacheprovider tests/
  -> 103 passed, 3 warnings in 9.01s   EXIT=0
```

Fixround commit: see `git log --oneline -1` after this file lands (title
`matapp: T10f fixround — wire Willys store-scoped ingest (MC 1355.17)`).

# JUDGED: 44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a
# VERDICT: PASS
