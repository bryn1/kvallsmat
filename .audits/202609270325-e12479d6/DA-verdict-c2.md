# T11 DA verdict cycle 2 — review of the in-flight build tree (MC 1355.18)

Fresh devils-advocate pass over the CURRENT tree state: HEAD `a92d88b` plus the build child's
uncommitted working-tree diff (app/db.py, app/models/profile.py, app/optimizer/optimizer.py,
app/optimizer/recipes.py, app/profile_service.py, app/routers/menu.py, app/routers/profile.py,
src/planner/menu.py). The build appears MID-FLIGHT (no frontend, no seed/scraper, no new tests
yet); this verdict judges what exists now. Ranked P0 > P1 > P2 > P3 > P4.

## P0 — the build's `("recipes", "kid_friendly", "Integer")` migration entry crashes boot(): NoSuchTableError on every DB the app itself created

`app/db.py:83` adds `("recipes", "kid_friendly", "Integer")` to `_NEW_COLUMNS`.
`ensure_columns` inspects each table (`app/db.py:96-99`) — but the `recipes` table is NEVER
created in the app boot path: `app/models/__init__.py` imports only users/profile/offers_db/
store_selection, and NOTHING under `app/` or `server.py` imports `src.recipes.store` (grep:
only `app/optimizer/recipes.py` mentions it, and that is the roster dataclass, not the ORM
model). `create_all` therefore never creates `recipes`, and `inspector.get_columns("recipes")`
raises `NoSuchTableError` inside `boot()` → **the app cannot boot at all** on any DB that
run_motor did not create.

Evidence (executed this session, working tree as described):
`python3 -m pytest tests/ -q` → **10 failed, 93 passed**; every failure is the same root cause,
e.g. `tests/test_store_scoping.py::test_fresh_db_boot_has_all_columns` →
`sqlalchemy.exc.NoSuchTableError: recipes`; also test_auth_fixround2 (2), test_ingest_wiring (3),
test_menu_wiring (1), test_store_scoping (4). Direct repro on a legacy DB confirms the
inspect-crash mechanism.

Fix (pick ONE, name it in the design): (a) import the recipes ORM model in the boot path —
`from src.recipes.store import Recipe` in `app/models/__init__.py` (or app/db.py before
init_db) so create_all creates the table; or (b) guard `ensure_columns` with
`inspector.has_table(table)` and skip absent tables. (a) is the reuse-first choice: the FIX-2
idiom already exists for exactly this.

**Correction of my own cycle-1 verdict:** I wrote "recipes is on the shared Base so create_all
precedes the inspect and get_columns cannot hit a missing table" — that was OVERSTATED. The
class is declared on the shared Base but never IMPORTED in the app path, so create_all does not
know it. CONTRADICTED by the executed tests above; the cycle-1 SHIP-side negative is withdrawn.

## Verified good in the current diff (could not break)

* **P1 (cycle 1) correctly resolved:** `prefer_kid_friendly: bool = False` lands on
  `app/optimizer/optimizer.py:38`'s FamilyPrefs — the class the router actually instantiates —
  with a comment naming the DA finding, AND `src/planner/menu.py` reads it via
  `getattr(family, "prefer_kid_friendly", False)`. Crash-free under both carriers; with the flag
  off the rank key orders identically to pre-T11 (constant middle term, same rng draw count).
* Absent-means-unchanged implemented exactly per the postal_code precedent:
  `model_fields_set` checks for both new fields (`app/routers/profile.py:111-117`), explicit
  null clears, `ge=0` / `ge=0,le=1` constraints present.
* NULL-tolerance is now stated where the migration happens (`app/db.py:79-81` comment) — the
  cycle-1 P3 "default 0" inaccuracy is resolved in the build.
* `MenuDay.kid_friendly` is additive with a `getattr` guard (`app/routers/menu.py:186-188`) —
  old responses stay valid.

## Still required for SHIP (cycle-1 findings not yet visible in the tree — build mid-flight)

1. Frontend: register toggle + form (with NAMED ids), `showLoggedIn`/`showLogin` hiding BOTH
   forms, mode reset on refreshAuth, `Endpoints.register`, `err.response` attachment.
2. Badge rendering mechanism in `suggestions.js`: escapeHtml (or DOM nodes) — "textContent only"
   is unimplementable inside the existing innerHTML template.
3. `src/recipes/seed.py` + `src/recipes/scraper.py` kid_friendly passthrough.
4. The design's test list (test_profile_children.py, test_menu_kid_friendly.py,
   test_migration_t11.py, test_recipe_kid_friendly.py) — none exist yet.
5. 422 detail surfacing (WeakPassword also covers username length, `app/auth_service.py:218`).

# JUDGED: 92bd6544acec4ccd0eac4fd53b5e041bdb10a085c6ddb5286e487248b517569e
# VERDICT: FIX
