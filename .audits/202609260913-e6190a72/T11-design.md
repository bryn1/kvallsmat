# T11 design — register UI + antal barn + barnvänligt (MC 1355.17, parent 1355)

Owner request (verbatim): "Jag ser inte möjlighet att välja registrera konto. Jag skulle också
vilja lägga till antal barn och ha barnvänligt som ett alternativ på recept."

Repo: `/srv/workspace/matapp` (main). Investigated this session at HEAD `1664b947`.

## 0. Grounding — what exists (VERIFIED this session)

* `POST /api/auth/register` **already exists** (`app/routers/auth.py:73-84`): open registration
  (MC 1355.7, owner-ratified), argon2id via `app.security`, auto-login with the SAME session
  cookie, `409` duplicate username, `422` weak/short password. **No new endpoint is needed.**
* The Konto page (`templates/index.html:40-53`) has ONLY the login form; the `Endpoints`
  registry (`static/js/utils/api.js:71-76`) has no `register` entry — that is the whole gap.
* **Existing seam bug F0 (must be fixed by this card):** `auth.js` `showLogin`/`showLoggedIn`
  target `document.getElementById('auth-login')` (`static/js/ui/auth.js:33,42`) — an id that
  exists NOWHERE in the markup (the form is `id="auth-form"`, `index.html:41`). Consequence:
  the login form is never hidden when a user is logged in. The register toggle lives in the
  same DOM region, so T11 fixes this seam as part of the toggle work.
* Absent-means-unchanged PUT precedent: `ProfileBody.postal_code` + `model_fields_set`
  (`app/routers/profile.py:44-48, 90-104`). New profile fields MUST follow the same rule.
* Guarded-ALTER migration precedent: `app/db.py` `_NEW_COLUMNS` + `ensure_columns()`
  (`app/db.py:75-108`) — idempotent, concurrent-boot tolerant. New columns reuse it.
* The planner consumes `app/optimizer/recipes.py` `ROSTER` (`app/routers/menu.py:159`), NOT the
  recipes DB. The optimizer `Recipe` dataclass already mirrors the DB `Recipe` fields
  (`vegetarian`, `budget_tier`) — that two-representation precedent is how `kid_friendly`
  must be added too (one field, two carriers of the same entity — not two mechanisms).
* `plan_menu` ranks eligible recipes by offer-hit count with a seeded tiebreak
  (`src/planner/menu.py:144-148`); when the eligible pool empties it breaks the day loop and
  emits fewer days (`src/planner/menu.py:160-162`) — it never crashes. This is the failure
  mode a FILTER-based kid-friendly design would hit; see §c.

---

## a) Register UI — login/register toggle on the Konto page

**Wired to the EXISTING endpoint. No new endpoint, no new mechanism.**

Files and seams:

1. `templates/index.html` (auth view, lines 40-53):
   * Wrap the ENTIRE auth choice region — the toggle row AND both forms — in
     `<div id="auth-login">`. This makes the EXISTING `auth.js` `showLogin`/`showLoggedIn`
     code work unchanged (fixes F0 by supplying the id the JS already looks for; zero JS id
     churn) and, critically, makes the logged-in hide cover the register form too: the
     register form `<div id="auth-register" hidden>` lives INSIDE `#auth-login`, never as a
     sibling — `showLoggedIn()` hides only `#auth-login` (`static/js/ui/auth.js:41-48`), so a
     sibling would stay visible after login. `setMode` toggles the two inner forms.
     Register form: username (`autocomplete="username"`) + password
     (`autocomplete="new-password"`), submit button "Skapa konto". Same
     `form-field`/`form-input`/`btn btn-primary` classes — no new CSS components.
   * Toggle row (first element inside `#auth-login`): two buttons
     (`<button type="button" id="auth-mode-login">Logga in</button>`,
     `<button type="button" id="auth-mode-register">Registrera konto</button>`) with
     `aria-pressed` state; the active mode's form is shown, the other `hidden`.
2. `static/js/utils/api.js`:
   * `Endpoints.register = '/api/auth/register'` (one registry line — the existing pattern).
   * Additive error-detail fix: `apiGet`/`apiPost`/`apiPut` attach the `Response` to the thrown
     `Error` (`err.response = res`) before throwing. No behaviour change for existing callers;
     it lets auth.js distinguish 409 from 422 without a second fetch mechanism.
3. `static/js/ui/auth.js`:
   * `submitRegister()` — reads the register inputs, client-side empty check (same idiom as
     `submitLogin` line 65-68), `apiPost(Endpoints.register, {username, password})`, then
     `refreshAuth()` (the backend sets the session cookie exactly like login — auto-login).
   * Error handling reuses the EXISTING `#auth-error` banner via the EXISTING `showError()`:
     `409` → "Användarnamnet är upptaget — välj ett annat.", `422` → "Lösenordet är för kort
     eller svagt.", `429`/other → "Kunde inte skapa kontot. Försök igen." (read
     `err.response?.status`; the banner text is set with `textContent` — no HTML injection).
   * `setMode('login'|'register')` toggles the two forms + `aria-pressed`; both mode buttons
     and both submits bound in `init()`.

Rejected alternative: a dedicated register page/route — duplicates the Konto view for no gain;
the owner asked for the *choice* on the existing page.

## b) Antal barn — `profile.num_children`

**Schema/migration:** `profile.num_children INTEGER NULL` — guarded ALTER via
`app/db.py` `_NEW_COLUMNS` entry `("profile", "num_children", "Integer")`. Nullable: absent =
the user has not saved a value (same semantics as `postal_code`, T10b §2).

* `app/models/profile.py`: `num_children = Column(Integer, nullable=True)` + doc comment.
* `app/profile_service.py`: `ProfileData` gains slot + ctor param `num_children: int | None`,
  `as_dict()` echoes it; `save_profile`/`load_profile` passthrough (no new validation here —
  the router owns wire validation, the service owns persistence, as today).
* `app/routers/profile.py`: `ProfileBody.num_children: int | None = Field(default=None, ge=0)`.
  Semantics EXACTLY the postal_code rule: field absent from the PUT body (`model_fields_set`)
  = leave persisted value unchanged; explicit `null` = clear (store NULL); value = validate
  `ge=0` (422 otherwise) and store. GET echoes it.
* `static/js/ui/profile.js` + `templates/index.html`: number field
  `<input type="number" id="profile-num-children" min="0" max="20">` labelled "Antal barn",
  with an edit-tracking flag `childrenEdited` mirroring `postalEdited` (absent = unchanged;
  an edit to empty sends `null` = explicit clear).

**Planner effect — recommendation: INFORMATIONAL ONLY in this card.** The field is stored,
echoed, and rendered; it does NOT change planning in T11. The UI help text says so plainly:
"Sparas för hushållet — påverkar förslagen än så länge inte."

Justification: the obvious alternative (feed `persons + num_children` into
`FamilyPrefs.persons`) is a one-line change, but it silently alters EVERY existing plan:
`_allowed` filters recipes with `servings < persons` (`src/planner/menu.py:114`), and the
roster's servings span 2-6 — a household of 2+3 shrinks the eligible pool to the two
servings-6 dishes, and pool exhaustion truncates the week (`menu.py:160-162`). A behaviour
change of that size needs its own design + tests, not a rider on a UI card. A stored-but-silent
field is honest exactly because the UI labels it; an unlabelled dead field would be the
CONTRADICTED-claim trap. Named follow-up: **T11b — feed num_children into servings planning**
(with pool-starvation tests).

## c) Barnvänligt — `recipes.kid_friendly` + `prefer_kid_friendly`

**Schema/migration (2 columns):**

| Table | Column | Type | Migration |
|---|---|---|---|
| `recipes` | `kid_friendly` | `INTEGER` default 0 (0/1) | guarded ALTER via `_NEW_COLUMNS` `("recipes", "kid_friendly", "Integer")` |
| `profile` | `num_children` | `INTEGER` NULL | guarded ALTER `("profile", "num_children", "Integer")` |
| `profile` | `prefer_kid_friendly` | `INTEGER` NULL (0/1) | guarded ALTER `("profile", "prefer_kid_friendly", "Integer")` |

`ensure_columns` already re-inspects after each ALTER and tolerates the concurrent-boot
duplicate-column race — the three entries ride that mechanism unchanged.

**Seed values** (`src/recipes/seed.py` — `kid_friendly: 1` on kid-typical dishes, `0` elsewhere):

**ORM declaration (F-DA2):** `src/recipes/store.py` `Recipe` gains
`kid_friendly = Column(Integer, default=0)  # 0/1` — without the model column, `create_all`
on a FRESH database omits it and the seed upsert would fail; the guarded ALTER only covers
existing databases. Both sides are needed, exactly like the T10e columns.

* `1`: Köttbullar med gräddsås och potatis · Pannkakor med sylt · Korv stroganoff · Tacopaj ·
  Köttfärssås och spagetti · Pasta med tomaatsås och basilika · Quesadillas med bönor.
  Rationale: the classic Swedish children's roster — mild, familiar, hand-held or
  tomato-based dishes (köttbullar/pannkakor/falukorv/tacopaj/pasta-tomatsås are the canonical
  barnmat set); quesadillas are mild cheese-bean finger food.
* `0`: Fiskgratäng, Ugnsbakad lax, Vegetarisk lasagne, Linssallad, Kikärtsgryta,
  Rostade grönsaker med hummus, Kyckling med ris och currysås, Grönsakssoppa, Pytt i panna,
  Pasta carbonara — fish/curry/lentil/adult-palate dishes.

**Scraper passthrough** (`src/recipes/scraper.py` `_normalize_spec`): add
`"kid_friendly": 1 if _int(spec.get("kid_friendly"), 0) else 0` — same 0/1 normalisation idiom
as `vegetarian` (line 81). Seed stays authoritative (additive-vs-seed rule unchanged).

**Optimizer roster** (`app/optimizer/recipes.py`): the `Recipe` dataclass gains
`kid_friendly: int = 0`; roster entries carry the same values as their seed counterparts
(köttbullar 1, köttfärssås 1, korv stroganoff 1, pannkakor 1; lax 0, kyckling 0). This mirrors
the existing vegetarian/budget_tier two-representation precedent — the planner's actual input
is this roster (`menu.py:159`), so the flag must exist here for planning to see it at all.

**Profile option:** `profile.prefer_kid_friendly` (0/1, nullable), same
absent-means-unchanged PUT semantics as num_children; UI checkbox
`<input type="checkbox" id="profile-kid-friendly">` labelled "Barnvänligt" with help text
"Barnvänliga rätter prioriteras i förslagen." Edit tracking like the other fields.

**Planner behaviour — recommendation: BOOST (tiebreak), not FILTER.**
`FamilyPrefs` gains `prefer_kid_friendly: bool = False`; `plan_menu`'s rank key becomes
`(-offer_hit_count, -(kid_friendly if family.prefer_kid_friendly else 0), rng.random())`
(`src/planner/menu.py:146-148` — one key tuple, no new mechanism). Kid-friendly dishes win
TIES on offer-hits; offer-hit maximisation stays the primary objective.

Justification vs filter: a filter shrinks the eligible pool, and pool exhaustion is exactly
the "menu must not break" failure — `plan_menu` breaks the day loop and emits FEWER DAYS than
`meal_days` (`menu.py:160-162`). The boost degrades gracefully by construction: when no
kid-friendly recipe exists (or the flag is off) the rank key is byte-identical to today's —
the regression guard is structural, not a special case. Rejected: hard filter with fallback
re-query — a second selection mechanism beside the existing `_allowed`/rank seam.

**Menu view rendering:** `MenuDay` gains an additive field `kid_friendly: bool = False`
(same additive-field precedent as `offer_sources`, MC 1355.16); `menu.py` fills it from the
existing `by_title` lookup. `static/js/ui/suggestions.js` renders a plain-text badge
"Barnvänligt" next to the dish title when true — `textContent` only (T10f DA P3-1 XSS idiom),
no new CSS component beyond a `form-help`-class span. When the flag is absent/false nothing
renders — old responses stay valid.

## Endpoint contract changes (summary)

* `POST /api/auth/register` — UNCHANGED (UI wiring only).
* `GET/PUT /api/profile` — body/response gain `num_children: int|null (ge=0)` and
  `prefer_kid_friendly: 0|1|null`; absent = unchanged, explicit null = clear (both fields).
* `GET /api/menu` — `MenuDay` gains additive `kid_friendly: bool = False`; planning honours
  `prefer_kid_friendly` as a rank tiebreak. No breaking shape change.

## UI file list

`templates/index.html` (auth toggle + register form; profile num-children field + kid-friendly
checkbox) · `static/js/utils/api.js` (Endpoints.register, err.response) ·
`static/js/ui/auth.js` (setMode, submitRegister, error mapping) · `static/js/ui/profile.js`
(two new fields, edit tracking) · `static/js/ui/suggestions.js` (kid-friendly badge) ·
`static/css/app.css` only if a badge class is genuinely needed (prefer existing classes).

## Test list (offline fixture tests, `tests/conftest.py` temp-DB `client` idiom)

* `tests/test_profile_children.py`
  * `test_num_children_absent_means_unchanged` — PUT with 2, PUT without the field, GET still 2
  * `test_num_children_explicit_null_clears` — PUT null → GET null
  * `test_num_children_negative_422`
  * `test_prefer_kid_friendly_absent_means_unchanged` and `_roundtrip`
  * `test_profile_get_echoes_new_fields`
* `tests/test_menu_kid_friendly.py`
  * `test_menu_day_carries_kid_friendly_flag`
  * `test_prefer_kid_friendly_boosts_kid_dishes_on_ties` — same offers, prefer=1 vs prefer=0
    produce different, deterministic day orders with a kid-friendly dish promoted
  * `test_menu_without_kid_friendly_recipes_still_200_full_week` — all-roster-0 plan is
    identical to today's plan (regression guard)
  * `test_menu_plan_deterministic_same_seed`
* `tests/test_migration_t11.py`
  * `test_ensure_columns_adds_t11_columns_on_legacy_db` — engine created with the pre-T11
    schema, `boot()`, assert the three columns exist; re-boot idempotent
* `tests/test_recipe_kid_friendly.py`
  * `test_seed_marks_kid_recipes` — the seven named titles have `kid_friendly=1`
  * `test_scraper_persists_kid_friendly` — `file://` source fixture with the flag

## Explicit non-goals

* No new auth endpoint, no password-reset, no e-mail verification, no login-lockout change.
* No per-child profiles or child-specific allergen handling.
* num_children does NOT change planning in this card (follow-up T11b owns that decision).
* No switch of the planner's recipe data source from the optimizer roster to the recipes DB.
* No JS test framework; UI behaviour is verified by the runtime/browser gate, API by pytest.
* No new CSS component system; existing `form-field`/`btn`/`state-banner` classes only.

## Architecture-doc note

`docs/ARCHITECTURE.md` does not exist yet in this repo. The BUILD card that implements this
design must create it (workspace-convention layout v2) covering modules, entrypoints, ports,
deps and the sqlite data store — the ARCH closing verdict of that run depends on it.

# VERDICT: SHIP
