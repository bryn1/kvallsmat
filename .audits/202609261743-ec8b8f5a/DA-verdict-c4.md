# T10f — DA verdict cycle 4: re-gate over the settled tree (store-scoped ingest wired)

Cycle 4 of the T10f adversarial gate. Trigger: the deliverable changed after cycle 3's
judgment — the parallel session finished its store-scoped-ingest wiring and its suite
went green. This is a FRESH verdict over the tree as it stands NOW; cycles 1–3 stand
as written.

## State of the tree under judgment

HEAD `48848d6` (audit artifacts) on `2f44683` (T10f P2 fixes) on `793f991` (T10e
build). The working tree carries the parallel session's COMPLETED-but-UNCOMMITTED
wiring: `src/scheduler/periodic.py` (+118: `run_store_scoped_ingest`,
`collect_resolved_willys`, `_willys_catalog_label` storeflyer join, `main(...,
resolved_stores=)`), `app/main.py` (`_saved_resolved_stores()` feeding the boot
ingest), `app/routers/menu.py` (`store_name` in `OfferSource` + `_resolved_store_names`),
`static/js/ui/profile.js` (textContent-built resolved list — the P3-1 XSS fix),
`static/js/ui/suggestions.js`, `.gitignore` (+`.tmp/` — the P4-2 nit), and NEW test
file `tests/test_ingest_wiring.py` (208 lines, untracked).

## Decisive check re-run by THIS gate (VERIFIED this session)

`/srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q` →

```
103 passed, 3 warnings in 11.55s
PYTEST_EXIT=0
```

(97 → 103: the wiring tests moved to `test_ingest_wiring.py` plus the store_name test.)

## Attack results on the NEW code

1. **P0 invariant through the new write path — HOLD.**
   `run_store_scoped_ingest` is now the PRODUCTION caller of `pull_store_scoped`
   (closing cycle-1 P1-1's dead-code fact): resolved store → storeflyer label join
   (the design's flyerURL store-number join) → store's own name as fallback →
   store-scoped pull → normalize → upsert WITH `store_id`.
   `test_store_scoped_ingest_wires_pull_store_scoped` proves on the real
   implementation: RULE-1 prefix intact (`2149:off1`), the storeflyer request fired,
   and the chain-level NULL row survived unchanged. `collect_resolved_willys` dedups
   on store_id, skips errored chains and non-willys chains (tested).
2. **Fail-tolerance — HOLD.** A failed label join or pull is logged and skipped per
   store, never fatal (`except Exception` around the pull; `written` counts only
   successes); no willys grocer configured → logged skip, return 0.
3. **Layering — HOLD.** `src/` never imports `app/`: `app/main.py` owns the profile
   read and passes the plain resolved list down — the same seam idiom as the boot
   ingest.
4. **P3-1 (innerHTML XSS vector) — FIXED.** `profile.js` now builds `<p>` nodes with
   `textContent`; no third-party string reaches innerHTML.
5. **P3-2 (raw store_id shown) — FIXED.** `OfferSource.store_name` populated from the
   persisted resolution (`_resolved_store_names`), UI shows the name; fallback to the
   raw id when absent. Additive field, `used_offer_ids` untouched.
6. **P4-2 — FIXED.** `.tmp/` gitignored.
7. **Menu store clause/dedup — unchanged and still endpoint-tested** (cycle-2 tests
   still green).

## Conditions attached to this SHIP

- **The wiring is UNCOMMITTED.** `src/scheduler/periodic.py`, `app/main.py`,
  `app/routers/menu.py`, the UI files, `.gitignore` are modified-tracked and
  `tests/test_ingest_wiring.py` is UNTRACKED. This gate does not commit another
  session's work: the author session MUST land it as ONE commit with the mandated
  attribution form (`git -c user.name="code (MC 1355.17)" -c user.email=code@agent-town.local commit ...`),
  including the new test file — until then the green suite lives only in this
  working tree, not in any commit.
- Cycle-1's residual note is now closed: the store clause is no longer dead code —
  the boot ingest stamps `offers.store_id` for resolved Willys stores with a Tjek
  catalog (design T10b §3/§6 step 5 now fires end-to-end).
- Remaining recorded (non-blocking): Coop cold-start warm inside the first profile
  save (P3-3, stated design limitation); suggestions.js still falls back to the raw
  id when a store has no name.

## Bottom line

Every finding from cycles 1–3 is now fixed, design-corrected, or closed by the
parallel session's wiring: P1-1 wired and tested, P2-1/P2-2 fixed in 2f44683, P3-1/
P3-2/P4-2 fixed in the working tree, P3-3 stated. The suite is green on the real
implementation (103 passed, EXIT=0), and the P0 no-retraction invariant holds through
every write path including the new one. SHIP — conditional only on the author session
committing its own work, which is bookkeeping, not code risk.

# JUDGED: 44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a
# VERDICT: SHIP
