# T11 DA verdict cycle 4 — re-review of the fixed build tree (MC 1355.18)

Fresh devils-advocate pass over HEAD `ca97aa5` + the build child's current uncommitted diff
(backend, frontend, seed/scraper, four new test files, docs/ARCHITECTURE.md). Both cycle-3 P1s
are now resolved with executed evidence; nothing new broke. Ranked findings:

## Resolved since cycle 3 (executed evidence this session)

* **P1-A (migration contract regression)** — `ensure_columns` now guards with
  `inspector.has_table(table)` / `continue` (app/db.py, diff verified) so a legacy DB without a
  `recipes` table no longer raises; `tests/test_store_scoping.py` passes again (all 4 migration
  tests green in the full run). The T10d F8 contract is restored.
* **P1-B (build's own red tests)** — `python3 -m pytest tests/ -q` → **3 failed, 113 passed**;
  the 3 failures are EXACTLY the pre-existing `tests/test_ingest_wiring.py` ones, verified
  PRE-EXISTING at the pre-build HEAD `4a371578` in a throwaway worktree last cycle (same 3
  failed there; worktree removed). Every T11 test file passes:
  test_profile_children (6), test_menu_kid_friendly (4), test_migration_t11, test_recipe_kid_friendly.
  The boost test was fixed PROPERLY, not weakened: it now asserts a real promotion
  (`on["days"][0]["dish_id"] == KID_TITLE`), a determinism guard (same seed → byte-identical),
  and the no-kid-recipes test uses the explicit cookie-token idiom — the NameError is gone.

## Honest scope notes (not T11 defects)

* The 3 remaining failures are the pre-existing ingest-wiring ones — out of T11 scope (scope
  control), but the owner should know they were red before this card started.
* The runtime/browser gate for the new UI (register toggle, badge) has NOT been executed from
  this session — no frontend child could be spawned from this depth-1 session. The code was
  reviewed line-by-line (escapeHtml applied to every backend-sourced string in the innerHTML
  template; both auth forms inside #auth-login; named ids; 422 detail surfacing), but
  "code reviewed" is not "browser-verified". The build card owns that gate.

## Could not break

* Register reuses the ONE existing endpoint; no second mechanism (grep: single
  `@router.post("/register")`, app/routers/auth.py:73).
* Absent-means-unchanged holds for both new fields end-to-end (router model_fields_set →
  service passthrough → UI edit-tracking), matching the postal_code precedent exactly.
* Boost-not-filter: flag-off rank key orders identically to pre-T11; pool exhaustion impossible
  via the boost by construction; the all-roster-0 regression test proves the menu does not break.
* Migration: fresh-DB path (model import, FIX-2 idiom) + legacy-DB path (has_table guard) both
  green; NULL-tolerance documented at both sites.
* docs/ARCHITECTURE.md exists and matches the tree (module map, entrypoints, port 8141,
  /matapp/ prefix, sqlite store).
* File hygiene: no TODO/FIXME added; new files are at layout-v2 paths; the four new test files
  are committed with this run's audit trail.

# JUDGED: 8059ea0db8669463351110a31bb925b4a0a9bb71ec5176aeb90236f7573a14ad
# VERDICT: SHIP
