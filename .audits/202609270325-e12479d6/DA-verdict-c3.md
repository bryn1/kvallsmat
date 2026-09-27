# T11 DA verdict cycle 3 — review of the settled build tree (MC 1355.18)

Fresh devils-advocate pass over HEAD `d4deb54` + the build child's uncommitted diff (now covering
backend, frontend, seed/scraper, tests and docs/ARCHITECTURE.md). All 7 cycle-1 findings and the
cycle-2 P0 are resolved in code — but the build's OWN new tests are red, so this cannot ship.
Ranked P0 > P1 > P2 > P3 > P4.

## P1-A — `ensure_columns` still crashes on a legacy DB without a `recipes` table: 3 pre-existing T10d-F8 contract tests fail

The cycle-2 P0 fix (importing `src.recipes.store.Recipe` in `app/models/__init__.py:16-20`) makes
`boot()` safe — create_all now creates `recipes` before the inspect. But `ensure_columns` is also
a STANDALONE contract: `tests/test_store_scoping.py` calls it directly on a `_prechange_engine`
legacy DB (test_migration_idempotent:80-86, test_migration_tolerates_concurrent_boot_duplicate_column:89+,
test_migration_adds_all_three_columns_rows_intact) — and `inspector.get_columns("recipes")`
(`app/db.py:96-99`) still raises `NoSuchTableError: recipes` there. Executed evidence:
`python3 -m pytest tests/test_store_scoping.py -q` → 3 failed. The build REGRESSED the T10d F8
migration contract (idempotent, never-a-raise on legacy DBs). Fix: guard with
`inspector.has_table(table)` and skip absent tables (one line, inside the existing loop — no new
mechanism).

## P1-B — the build's own new tests are red: 8 failed / 108 passed overall

Executed this session: `python3 -m pytest tests/ -q` → **8 failed, 108 passed**.

* `tests/test_menu_kid_friendly.py` (3 of 4 fail):
  - `test_prefer_kid_friendly_boosts_kid_dishes_on_ties` (:60-72) asserts the flag promotes
    köttbullar over köttfärssås — but BOTH are `kid_friendly=1` in the roster
    (`app/optimizer/recipes.py:38-47`), so the tiebreak `-kid` cannot distinguish them; the
    fixture does not create the tie it claims to test. The test needs a kid=1 vs kid=0 pair at
    equal offer-hits.
  - `test_menu_day_carries_kid_friendly_flag` (:57) same fixture flaw: the offer gives
    köttfärssås at least as many hits as köttbullar, so day 1 is köttfärssås regardless of the
    flag.
  - `test_menu_without_kid_friendly_recipes_still_200_full_week` fails for the same fixture
    reason (asserts the pre-T11 day order; the roster now carries kid=1 dishes and the test's
    offers reorder ties).
  - Plus `NameError: name 'security' is not defined` at `tests/test_menu_kid_friendly.py:103` —
    an unimported name in the test file itself.
* `tests/test_recipe_kid_friendly.py` (2 of 2 fail): `test_seed_marks_kid_recipes` and
  `test_scraper_persists_kid_friendly` die in SQLAlchemy fixture setup (InvalidRequestError /
  ArgumentError — the fixture appears to build a `Recipe` ORM object against a metadata that
  already has the table registered, or creates the engine twice).

The DoD line "every test file you changed passes" is unmet. These are the producer's tests and
must go green (or be rewritten to test what they claim) before SHIP.

## Pre-existing, OUT of T11 scope (recorded, not a T11 finding)

`tests/test_ingest_wiring.py` 3 failures (`assert written == 1` got 0) — verified PRE-EXISTING at
the pre-build HEAD `4a371578` in a throwaway worktree (`git worktree add /tmp/matapp-pre
4a371578` → same 3 failed there; worktree removed after). Not caused by T11; scope control says
do not fix them on this card, but the owner should know the ingest tests were already red.

## Verified resolved — every cycle-1 and cycle-2 finding (per-finding, code evidence)

1. **P1 FamilyPrefs**: field on `app/optimizer/optimizer.py:44-47` (the class the router
   instantiates) + `getattr` fallback in `src/planner/menu.py:146-151` — crash-free under both
   carriers; flag-off key orders identically to pre-T11.
2. **P2a register visibility**: both forms live INSIDE `#auth-login`
   (`templates/index.html:40-79`), so `showLoggedIn` hiding the wrapper hides the register form;
   `refreshAuth` resets `setMode('login')` (`static/js/ui/auth.js:149-156`).
3. **P2b badge mechanism**: `escapeHtml` helper added and applied to `dish_id`, `date` and store
   labels in the innerHTML template (`static/js/ui/suggestions.js:22-29,44-55`); the badge itself
   is static text.
4. **P3 ids**: `auth-register-form`, `auth-reg-user`, `auth-reg-pass`, `auth-register-submit`,
   `auth-mode-login/register` all named in `templates/index.html:44-79`.
5. **P3 422 detail**: `registerErrorMessage` reads `err.response` body detail and distinguishes a
   username-length 422 from a password 422 (`static/js/ui/auth.js:107-125`).
6. **P3 checkbox semantics**: an edit always sends explicit 1/0 (a checkbox has no empty state),
   documented in `static/js/ui/profile.js:107-116`; num_children empty edit sends null = clear.
7. **P3 migration NULL**: documented at the migration site (`app/db.py:79-81`) and on the model
   (`src/recipes/store.py:27-30`); readers treat NULL as 0/absent.
8. **Cycle-2 P0**: fixed via the FIX-2 idiom import (`app/models/__init__.py:16-20`).
9. `docs/ARCHITECTURE.md` now exists (113 lines) and its module map matches the tree as I know it
   (routers, services, optimizer roster, planner seam, sqlite store, port 8141, /matapp/ prefix).
10. Seed/scraper passthrough landed with the vegetarian idiom (`src/recipes/scraper.py`,
    `src/recipes/seed.py` — 7 kid=1 titles as designed).

## Required before SHIP

1. `has_table` guard in `ensure_columns` (P1-A) — restores the T10d F8 contract tests.
2. Fix the build's own red tests (P1-B): correct the boost-test fixtures (kid=1 vs kid=0 at equal
   hits), import `security`, repair the two recipe-fixture setups.

# JUDGED: 1218f2efe9d96d08edb1f506d2cb0daa82d52848f8bfb5928b0975cb66663f31
# VERDICT: FIX
