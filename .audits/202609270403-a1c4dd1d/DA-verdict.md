# DA verdict — T11 build (MC 1355.18), run 202609270403-a1c4dd1d

NOTE: fan-out was mechanically impossible in this session (`subagent depth 2
exceeds maxDepth 1`); the DA phase ran inline in the orchestrating child. The
INDEPENDENT DA gate over the design + in-progress tree already ran as separate
children in run `.audits/202609270325-e12479d6/` (cycles 1-4, final SHIP);
this verdict covers the SETTLED build tree adversarially.

Attacks attempted against commits 9a5b299 + a742cb3:

1. P1 class from DA c1 (wrong FamilyPrefs): VERIFIED RESOLVED —
   `prefer_kid_friendly` lives on `app/optimizer/optimizer.py::FamilyPrefs`
   (the class `app/routers/menu.py` instantiates and passes into `plan_menu`);
   `src/planner/menu.py` reads it via `getattr` with a False default, so even a
   plain planner-FamilyPrefs caller cannot 500. Live GET /api/menu returned
   200 (no AttributeError).
2. Register visibility (DA c1 P2a): the register form lives INSIDE
   `#auth-login`; `showLoggedIn` hides the wrapper (both forms disappear);
   `refreshAuth`'s fallback calls `setMode('login')` before `showLogin`, so no
   stale `aria-pressed` survives. VERIFIED in code + the F0 id now exists in
   the markup (`grep 'id="auth-login"' templates/index.html` hits the wrapper).
3. XSS idiom (DA c1 P2b): `suggestions.js` interpolates `dish_id`, date and
   store labels through `escapeHtml`; the badge is static text. `node --check`
   passes on all ui/utils JS; auth.js sets the error banner via `textContent`
   (its single "innerHTML" hit is a comment).
4. NULL tolerance (DA c1 P3): every reader of `kid_friendly` uses `or 0`
   (`menu.py` day fill, planner rank key); the guarded ALTER adds no DEFAULT,
   and `tests/test_migration_t11.py` proves legacy rows/columns migrate.
5. Boot crash class (DA c2 P0): `app/models/__init__.py` imports
   `src.recipes.store.Recipe` (create_all makes `recipes` on fresh DBs) AND
   `ensure_columns` has a `has_table` guard (legacy partial DBs skip). The
   full suite — including the T10d-F8 migration contract tests — is green.
6. Checkbox semantics (DA c1 P3): an edit always sends 1/0 (explicit
   preference); num_children edit-to-empty sends null. Covered by
   test_prefer_kid_friendly_absent_means_unchanged_and_roundtrip.
7. Date-dependence hunt (parent steering): grepped every test fixture for
   hardcoded dates compared to the real clock — only the two Tjek-path
   fixtures had it; both fixed in a742cb3; store_scoping/locator dates are
   stored strings only.
8. Honest negatives: no new endpoint (register reuses POST /api/auth/register,
   `git diff` touches no auth router); no TODO/FIXME added (grep 0); no
   untracked file left in the tree; num_children does not feed servings
   planning (grep: `num_children` absent from optimizer/planner paths).

Nothing left standing. The build matches the pinned design as amended by the
DA cycles.

# JUDGED: 72682e8f5648873885c77551ecd2bb63d3ed3fd31fe718e1ba9a40dc675491bd
# VERDICT: SHIP
