# T11 build — register UI + antal barn + barnvänliga recept (MC 1355.18)

Repo `/srv/workspace/matapp`, branch main. Implements the pinned design
`.audits/202609260913-e6190a72/T11-design.md` (SHIP) with the DA cycle-2/3/4
binding corrections (verdicts in `.audits/202609270325-e12479d6/`).

**Mechanics note:** this session could not fan out (`subagent depth 2 exceeds
maxDepth 1` — the build child IS a depth-1 subagent). All phases ran inline in
this run with the verdict discipline preserved; recorded in CYCLES.md.

## Commit

`9a5b299` — `matapp: register UI + num_children + kid_friendly recipes (MC 1355.18)`
on main (not pushed), plus fixround `a742cb3` — `matapp: date-independent
ingest wiring fixtures (MC 1355.18)` (see Fresh suite below). Parent-loop
bookkeeping commits (a92d88b, d4deb54, ca97aa5, 987c336) landed the DA
verdicts and the four T11 test files mid-run; 9a5b299 carries the
implementation.

## Diff summary (17 files, +295/−26)

* `templates/index.html` — auth choice region wrapped in `<div id="auth-login">`
  (F0 fix: the id auth.js already targets now exists; hiding it covers BOTH
  forms), toggle row (`auth-mode-login`/`auth-mode-register`, `aria-pressed`),
  register form `auth-register-form` with `auth-reg-user`
  (`autocomplete="username"`) + `auth-reg-pass` (`autocomplete="new-password"`)
  + "Skapa konto" submit; profile gains `profile-num-children` (min 0, max 20,
  help text "Sparas för hushållet — påverkar förslagen än så länge inte.") and
  `profile-kid-friendly` checkbox ("Barnvänligt", help "Barnvänliga rätter
  prioriteras i förslagen.").
* `static/js/utils/api.js` — `Endpoints.register = '/api/auth/register'` (the
  EXISTING endpoint; no new endpoint); `apiGet/apiPost/apiPut` attach
  `err.response = res` (additive; enables status discrimination).
* `static/js/ui/auth.js` — `setMode('login'|'register')` toggles the two inner
  forms + `aria-pressed`; `submitRegister()` (client-side empty check, POST,
  `refreshAuth()` auto-login); error mapping 409 → "Användarnamnet är upptaget
  — välj ett annat.", 422 → detail-surfaced (username vs password — DA c1 P3),
  other → "Kunde inte skapa kontot. Försök igen."; `refreshAuth` fallback
  resets mode to login (DA c1 P2a); `showLoggedIn` also hides the error banner.
* `static/js/ui/profile.js` — `childrenEdited`/`kidEdited` edit tracking;
  edit-to-empty children sends `null` (explicit clear); checkbox edit always
  sends 1/0 (a checkbox has no empty state — DA c1 P3 rule).
* `static/js/ui/suggestions.js` — `escapeHtml` helper; `dish_id`, date and
  store labels escaped in the innerHTML template (DA c1 P2b); plain-text
  "(Barnvänligt)" badge (static text, `form-help` class) when
  `d.kid_friendly` is true; nothing renders when absent/false.
* `app/models/profile.py` — `num_children`, `prefer_kid_friendly` (nullable).
* `app/db.py` — three `_NEW_COLUMNS` entries; `ensure_columns` gains a
  `has_table` guard (DA c2 P0: a legacy/partial DB without the recipes table
  must skip, not raise).
* `app/models/__init__.py` — imports `src.recipes.store.Recipe` so `create_all`
  creates `recipes` on a FRESH database (DA c2 P0, the design's F-DA2).
* `app/profile_service.py` — `ProfileData` slots/ctor/`as_dict`/save/load
  passthrough for both fields.
* `app/routers/profile.py` — `ProfileBody.num_children` (ge=0),
  `prefer_kid_friendly` (ge=0, le=1); absent-means-unchanged via
  `model_fields_set`, explicit null clears, GET echoes.
* `app/optimizer/optimizer.py` — `FamilyPrefs.prefer_kid_friendly: bool = False`
  on the class the menu router instantiates (DA c1 P1 — NOT the same-named
  `src/planner/menu.py` dataclass).
* `app/optimizer/recipes.py` — `Recipe.kid_friendly: int = 0`; roster values:
  köttbullar 1, köttfärssås 1, korv stroganoff 1, pannkakor 1; lax 0, kyckling 0.
* `app/routers/menu.py` — `MenuDay.kid_friendly: bool = False` (additive);
  family built with `prefer_kid_friendly` from the persisted profile; day flag
  filled from the `by_title` roster lookup (NULL-tolerant `or 0`).
* `src/planner/menu.py` — rank key
  `(-offer_hits, -kid_if_preferred, rng.random())`; with the flag off (or no
  kid-friendly recipes) the key is byte-identical to the pre-T11 one
  (structural regression guard). `getattr` keeps it working for any
  FamilyPrefs carrier.
* `src/recipes/store.py` — ORM `kid_friendly = Column(Integer, default=0)`
  (guarded ALTER adds no DEFAULT: existing rows read NULL, readers treat as 0).
* `src/recipes/seed.py` — `kid_friendly: 1` on the design's seven kid-typical
  dishes, `0` on the other eleven (explicit 0 everywhere).
* `src/recipes/scraper.py` — `_normalize_spec` passthrough
  `"kid_friendly": 1 if _int(spec.get("kid_friendly"), 0) else 0`.
* `docs/ARCHITECTURE.md` — CREATED (~120 lines): module map (app/ web layer,
  src/ vendored motor fetcher→normalizer→offers DB→planner, src/locator/,
  src/recipes/), data flow, auth model, offer sources with verified endpoints,
  store-level selection flow, data store, tests.

## The 12 design fixture tests (13 written — one extra 422 boundary)

* `tests/test_profile_children.py` (6): absent-means-unchanged, explicit-null
  clear, negative 422, prefer absent/roundtrip + explicit 0/null, out-of-range
  422, GET echo.
* `tests/test_menu_kid_friendly.py` (4): MenuDay carries the flag; boost breaks
  ties (kid=1 vs kid=0 pair at equal offer-hits, seed 103: flag-off picks lax,
  flag-on promotes köttbullar; same-seed determinism); deterministic same-seed;
  all-roster-0 menu still 200 with a full 5-day week and a flag-off-identical
  plan.
* `tests/test_migration_t11.py` (1): legacy pre-T11 schema → `ensure_columns`
  adds the three columns, idempotent re-run.
* `tests/test_recipe_kid_friendly.py` (2): seed marks the seven titles 1 (0
  elsewhere, rerun-stable); scraper persists the flag from a `file://` fixture
  (absent → 0).

## Live sanity (ONCE, real network, LOCAL server 127.0.0.1:8971, temp DB)

```
== register ==  {"ok":true,"username":"sanity_t11"}          HTTP=200
== put profile == {"saved":true,...,"num_children":2,
                    "prefer_kid_friendly":1}                  HTTP=200
== get menu ?week=2026-W39 ==                                HTTP=200
  day 2026-09-22 Köttbullar med gräddsås och potatis  kid_friendly:true
  day 2026-09-23 Pannkakor med sylt                   kid_friendly:true
  day 2026-09-21 Ugnsbakad lax med kokt potatis       kid_friendly:false
```
Badge presence VERIFIED in the API payload; the UI renders it from that field
via the escaped template (suggestions.js). Full transcript:
`.audits/202609270403-a1c4dd1d/.tmp/live/`.

## Fresh suite

Cleaned `__pycache__`/`.pytest_cache`, then
`/srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q`:
**116 passed, 0 failed, EXIT=0.**
Log: `.audits/202609270403-a1c4dd1d/.tmp/fresh-suite.log`.

### Fixround note (date-dependent fixtures, parent steering)

The first fresh runs showed 3 failures in `tests/test_ingest_wiring.py`
(store-scoped ingest). Initially recorded as "pre-existing at the base commit"
(verified by `git stash -u` rerun at 05c0a3e) — the parent's DA pass found the
REAL cause: the fixtures were DATE-DEPENDENT. `_tjek_routes()` hardcoded the
W39 catalog window (run_from 2026-09-21, run_till 2026-09-27T00:00) and the
Tjek adapter's `pick_catalog` prefers the catalog COVERING NOW — once the real
clock passed 2026-09-27 the fixture catalog was expired and written==0. They
passed on 2026-09-26, fail today. RED evidence of the planted-bad case
(hardcoded dates): `WRITTEN: 0`, `LABEL: None` (reproduction transcript in the
run's .tmp/). Fix commit `a742cb3` "matapp: date-independent ingest wiring
fixtures (MC 1355.18)":
* `tests/test_ingest_wiring.py::_tjek_routes` — catalog + offer dates now
  dynamic (run_from = now-1d, run_till = now+6d, published = now-2d); WEEK
  stays a label key only (the adapter never compares it to the clock).
* `tests/test_tjek_adapter.py` — same disease: `test_pull_happy_path_through_
  pull_grocer` calls `pull_grocer` with the REAL clock, so `CATALOGS`' CUR
  window expired too; the happy path now uses `_current_catalogs()` (OLD
  expired / CUR covering now / FUT future, all relative to the real clock).
  The `pick_catalog` UNIT tests keep the fixed `NOW` constant and stay
  deterministic.
* `tests/test_store_scoping.py` / `tests/test_locator.py` — checked for the
  same pattern: their hardcoded dates are stored strings only, never compared
  to "now" — no change needed (44/44 pass).

After the fix: fresh suite **116 passed, 0 failed, EXIT=0** — green regardless
of calendar date.

## File hygiene

No TODO/FIXME added (grep count 0 across app/ src/ static/ templates/ tests/).
Largest changed source file: `app/routers/menu.py` 271 lines (< 400). One
concern per file preserved; no new CSS component system.

# VERDICT: PASS

Orchestrator re-run 2026-09-28: /srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q -> "116 passed, 3 warnings in 12.83s"
VERIFY_EXIT=0
