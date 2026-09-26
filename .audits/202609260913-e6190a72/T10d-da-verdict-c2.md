# T10d — Devil's advocate cycle 2: fresh adversarial gate on the REVISED store-level design (MC 1355.15, parent 1355)

Attacked 2026-09-26 against HEAD a501929. Inputs: T10b-design.md **Revision 2** (the
document under attack), T10c-da-verdict.md (the cycle-1 findings I must verify as
resolved), T10a-store-locators.md, T7b-geographic-scope.md, and the real code read this
session: `app/models/profile.py`, `app/models/store_selection.py`,
`app/routers/profile.py`, `app/routers/stores.py`, `app/routers/menu.py`, `app/main.py`,
`app/db.py`, `app/profile_service.py`, `src/offers_db/store.py`,
`src/fetcher/adapters/tjek.py`. Verified this session: `grep -rn "store_id|postal_code|
resolved_stores" app/ src/` returns **zero** hits — none of the three columns exists in
code yet, so the migration/upsert findings were real and the revision's changes are
design-only (nothing to contradict in code).

**Bottom line: SHIP.** All nine T10c findings are genuinely resolved by mechanism, not
acknowledgment. The revision is executable as written. Two new P2s and two P3s are
recorded below; none blocks a coder child, but the P2s must be honored during build.

---

## Part 1 — Per-finding resolution verdicts (T10c → Revision 2)

**F1 (P0, store-scoped upsert retracts chain-level rows) — RESOLVED.**
Revision §3 now carries all three of the DA's prescribed fixes: (a) store-scoped rows are
written with `external_id = f"{store_id}:{hotspot_id}"` at ingest, so they can never
collide with a chain-level bare id; (b) the `upsert_week` match key becomes
`(grocer_id, external_id, week_key, store_id or "")`, so a store-scoped write cannot
match a NULL row even if ids collide; (c) an explicit "never overwrite a
`store_id IS NULL` row" rule plus the §8 regression test (chain-level pull then
store-scoped pull, both orders, NULL rows survive). I checked the mechanism against the
real `upsert_week` (`src/offers_db/store.py`): the match-key change is a one-line
`filter_by` extension and the prefixed id makes the two row populations disjoint — the
P0 retraction path is closed. Residual gap → new finding N1 (P2) below.

**F2 (P1, filter double-count) — RESOLVED.**
§4 menu row now specifies an explicit dedup step after the store clause, keyed on
`(grocer_id, normalized name)`, preferring the store-level row, chain-level as fallback
only when no store-level row matched; §8 adds the exact test the DA asked for (one
survivor, the store-level one; `andel_extrapris` not double-counted). The dedup runs
before `plan_menu`, so the offer-hit counting the DA attacked operates on deduped input.
Residual: "normalized name" is unspecified → N3 (P3).

**F3 (P1, profile migration unspecified → live PUT 500) — RESOLVED.**
The self-contradictory "create_all covers profile" parenthetical is deleted; §3 now
specifies guarded ALTERs for ALL THREE columns (`offers.store_id`,
`profile.postal_code`, `profile.resolved_stores`) in the `app/db.py` boot step, and §8
boots the migration test against a fixture containing BOTH tables with rows. I verified
the premise against the live code: `app/models/profile.py` has seven columns, no
`postal_code`/`resolved_stores`; `src/offers_db/store.py` has no `store_id` — the
migration is real and now specified. RESOLVED.

**F4 (P1, Coop shortlist-before-detail circularity) — RESOLVED.**
§2 `coop.py` is redesigned to the only working shape: daily persisted (file/DB-backed,
not in-process) cache of ALL 787 store details, haversine over cached coordinates,
nearest 3; cold-start cost stated in §9; §8 tests cold-start-once, zero-detail-requests
on second resolve, and cache survival across a "reboot". The circular construction is
gone, not reworded. Residual: cold-start behavior on the PUT path → N2 (P2).

**F5 (P1, unauthenticated outbound-call amplification) — RESOLVED.**
§4 stores row now auth-gates the `?postal_code=` param (401 anonymous, same gate as
profile/menu — I verified `app/routers/stores.py` `list_stores` indeed has no auth
dependency today, so the gate is a real addition), anonymous no-param calls keep
byte-identical behavior, and both the geocode TTL cache and a per-process resolve-result
cache bound repeat cost. §8 tests 401/200. The Nominatim 1 req/s exposure is no longer
reachable anonymously. RESOLVED.

**F6 (P2, clear-on-absent wipes stale-client saves) — RESOLVED.**
§4: absent `postal_code` = persisted value unchanged; only explicit `null`/`""` clears
(and clears `resolved_stores` with it). §8 adds the stale-client regression test; §5
makes the UI send the field only when edited. Matches the real `ProfileBody` extension
point (`app/routers/profile.py`). RESOLVED.

**F7 (P2, status/resolved_at/TTL) — RESOLVED.**
§2 persistence shape now carries `resolved_at` + per-chain `status`/`error`, PERSISTED
(not echoed-only — the exact ambiguity the DA flagged); §4 menu filter treats an errored
chain as chain-level rows only; §5 UI renders `resolved_at`; geocode cache gets a 24 h
TTL and is test-clearable. RESOLVED.

**F8 (P2, concurrent-boot ALTER race) — RESOLVED.**
§3: catch `OperationalError`, treat "duplicate column name" as success with a
re-inspect confirmation; §8 adds the pre-created-column boot test. Since `boot()` runs
inside `lifespan` before `yield` (`app/main.py`), this was a real crash path; it is now
specified closed. RESOLVED.

**F9 (P3, Coop key sourcing + Willys label-join) — RESOLVED.**
§2 `coop.py` fetches the APIM key from `coopSettings` at resolve time (cached with the
store cache) — no copied constant; §3 Willys ingest joins on `flyerURL` store number →
Tjek label first, name-string join demoted to fallback, unmatched stores logged. Both
match T10a's VERIFIED facts (`flyerURL: .../willys/2103`; Coop detail needs
`ledgerAccountNumber`). RESOLVED.

## Part 2 — New findings (this cycle)

**N1 (P2) — Rule 2's "sends the store-scoped write to its own row" ends in an
IntegrityError, not a second row.** The UNIQUE constraint stays
`(grocer_id, external_id, week_key)` (correctly — SQLite cannot ALTER a constraint). If
a future payload ever reuses a bare external id with a store-scoped `store_id` (the
exact case rule 2 claims to cover), the revised match key finds no existing row and
`conn.add(Offer(**row))` INSERTs — and the unchanged `uq_offer` constraint rejects the
insert: `sqlalchemy.exc.IntegrityError`, raised out of `upsert_week` into the boot
ingest. The failure is LOUD (boot ingest is fail-tolerant and logs it, `app/main.py`),
not a silent retraction, so this is P2 not P0 — but the design text claims protection in
precisely the case where the code would raise. Fix at build: state that rule 1
(prefixing) is the ONLY sanctioned ingest path, and either catch IntegrityError per-row
in `upsert_week` or add a one-line assertion in the Tjek adapter that store-scoped ids
are always prefixed. Build-time must, not a redesign.

**N2 (P2) — Coop cold start runs ~787 detail GETs synchronously inside an authenticated
PUT /api/profile.** §9 states the one-time cost but not the behavior: the first user
save after a cache wipe blocks for the full 787-request run (minutes at polite
concurrency), and a mid-run Coop failure leaves a partially-populated cache whose status
the design does define (per-chain `error`) but whose resume semantics it does not
(partial cache + error → next save re-fetches all 787? or resumes?). Fix at build: state
that a failed/partial Coop cache run re-fetches from scratch on the next resolve (simple,
correct), and accept the one-time slow PUT as a stated POC limitation — or warm the
cache at boot alongside the existing boot ingest. No redesign needed; the omission would
otherwise be guessed at.

**N3 (P3) — "normalized name" in the dedup key is unspecified.** Lowercase+trim is the
obvious reading; a coder will guess it. One clause in §4 ("normalized = casefold +
strip") removes the guess. Also note the dedup key ignores `unit` — two rows with the
same name and different units collapse to the store-level row, which is the intended
precedence but worth one test case.

**N4 (P3) — The per-process resolve-result cache (`GET /api/stores?postal_code=`) has no
stated size bound or TTL.** Auth-gated, so abuse is bounded to real users; a simple
"same 24 h TTL as the geocode cache" sentence closes it.

## Part 3 — Executability check (could a coder child implement without guessing?)

Yes. Every change names its file, its seam, and its test: the locator package split maps
1:1 to T10a's VERIFIED endpoint shapes; the upsert match-key change lands in the one
canonical `upsert_week`; the migration lands in the one `boot()`; the filter/dedup lands
in the one menu router between `list_offers_in_week` and `plan_menu`; the API changes
extend existing pydantic bodies/routers with stated absent-field semantics; §8 enumerates
the test matrix including the byte-identical no-op regression guard. The two P2s above
are clarifications a coder can implement conservatively without a re-design round.

## Part 4 — What I could NOT break (honest negatives)

- **Resolve-once-at-save (§1):** still holds under attack; the persisted-status fix (F7)
  closed the only asymmetry I found in cycle 1's reasoning.
- **No-new-endpoint stance (§4/§7):** preview + resolve-on-save still answer both needs;
  the auth gate removed the amplification without adding a route.
- **JSON-on-profile persistence (§2):** one mechanism, no second table; per-chain status
  fits the shape; no contract break found in `ProfileData`/`as_dict` consumers.
- **`offer_sources` additive response field:** `used_offer_ids` kept; no client break.
- **Session-injection testability (§8):** real idiom (`src/fetcher/grocer.py`,
  `tjek.py`); the full matrix is offline-testable as specified.

# JUDGED: 44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a
# VERDICT: SHIP

Orchestrator re-run 2026-09-26: /srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q -> "103 passed, 3 warnings in 11.80s"
VERIFY_EXIT=0
