# T11 DA verdict — register UI + num_children + kid_friendly (MC 1355.18)

Attacked `.audits/202609260913-e6190a72/T11-design.md` (last line SHIP) against the real tree at
HEAD `4a371578` (design cites `1664b947`; every line reference it makes was re-verified and still
holds). Findings ranked P0 > P1 > P2 > P3 > P4.

## P1 — "FamilyPrefs gains prefer_kid_friendly" names the WRONG-ambiguous class; literal implementation 500s GET /api/menu

There are TWO same-named `FamilyPrefs` classes: `src/planner/menu.py:38` (defines `plan_menu`'s
rank key) and `app/optimizer/optimizer.py:38`. The menu router imports the OPTIMIZER one
(`app/routers/menu.py:39`), instantiates it (`menu.py:138`), and passes that instance into
`src.planner.menu.plan_menu` (`menu.py:42,161`). The design (§c) says "`FamilyPrefs` gains
`prefer_kid_friendly: bool = False`" without naming the module. The natural reading — edit the
planner's own dataclass where the rank key lives — leaves the router-built instance without the
attribute, and the proposed rank key `-(kid_friendly if family.prefer_kid_friendly else 0)` reads
it on EVERY call → `AttributeError` → 500 on every `GET /api/menu`, not just for prefer=1 users.
The design must name `app/optimizer/optimizer.py:38` (the class actually instantiated by the
router) — or both, with a stated reason. This is exactly the "no guessing" bar the design sets
for itself.

## P2 — Register success leaves the register form visible: showLoggedIn only hides #auth-login

`showLoggedIn` (`static/js/ui/auth.js:41-48`) hides only `auth-login`; `showLogin`
(`auth.js:31-39`) shows only `auth-login`. The design adds a sibling `#auth-register` form but
never says either function hides/shows it, and never says the mode resets. Consequence as
specified: submit register → success → `refreshAuth()` → `showLoggedIn` → the logged-in view
renders WITH the register form still visible beneath it. Likewise a 401 refresh while in register
mode shows the login form with stale `aria-pressed` on the mode buttons. The design must state:
`showLoggedIn` hides BOTH forms (or `submitRegister` success calls `setMode('login')` before
refresh), and `refreshAuth` resets the mode to login.

## P2 — Badge "textContent only" is unimplementable in the file as it renders

§c says the "Barnvänligt" badge is rendered "textContent only (T10f DA P3-1 XSS idiom)". But
`suggestions.js` renders the whole card through one innerHTML template string
(`renderSuggestion`, `static/js/ui/suggestions.js:24-44`, joined at `:67`) — `d.dish_id` is
interpolated unescaped there today. A badge inside that template CANNOT be textContent without
restructuring the renderer. The design must specify the actual mechanism: an `escapeHtml` helper
applied to `dish_id`/store labels in the template, or DOM-node construction for the badge. Not
exploitable today (dish titles come from the hand-coded roster, `app/optimizer/recipes.py`), so
P2 not P1 — but the stated idiom does not match the file's mechanism, and a coder following the
letter of the design will either ship the inconsistency or improvise.

## P3 — 422 error text mislabels a username failure as a password failure

`auth_service.register` raises `WeakPassword("username must be 1-64 characters")`
(`app/auth_service.py:218`) — the SAME exception class the design maps to the fixed string
"Lösenordet är för kort eller svagt." A too-long/empty username would show a lying message. The
design already attaches `err.response` (§a-2); it should surface `detail` from the 422 body (or
map on the detail text), not hardcode one string for the whole 422 class.

## P3 — Register form ids unnamed; coder must guess

The design names `auth-register`, `auth-mode-login`, `auth-mode-register` but NOT the register
inputs' ids or the register form's id — yet `submitRegister` must read them and `init()` must
bind the form's submit, mirroring `auth-input-user`/`auth-input-pass`/`auth-form`
(`templates/index.html:41-47`, `auth.js:104-110`). Against the design's own "names every file
and id" bar, these are missing.

## P3 — prefer_kid_friendly wire type and checkbox-clear semantics unspecified

The contract summary says `0|1|null` but no Field constraint is named (`ge=0, le=1`? `bool`?).
And a checkbox has no "empty" state: the design says "edit tracking like the other fields" but
never says whether unchecking sends `0` (actively not prefer) or `null` (clear). The two mean
different things under absent-means-unchanged. One sentence fixes it; as written the coder
guesses.

## P3 — "INTEGER default 0" is not what the migration produces

The guarded ALTER is `ADD COLUMN kid_friendly Integer` (`app/db.py:96-99` — col_type only, no
DEFAULT clause), so EXISTING recipes rows get NULL, not 0. Harmless today (the planner reads the
roster, not the DB), but the design's table claims "default 0" and no test covers a NULL row.
Either state "existing rows become NULL and every reader must tolerate it" or add the DEFAULT to
the migration entry.

## P4 — Seed kid_friendly values are planning-dead; say so

`seed_starter` runs only from `run_motor.py:91`, never at app boot, and `plan_menu` consumes the
optimizer ROSTER (`app/routers/menu.py:159-163`). The DB column's values therefore never
influence planning — the design's two-representation precedent covers this, but it should state
plainly that the seed assignment is bookkeeping/consistency only, so nobody later "fixes" a
planner bug by editing seed rows.

## Could not break (honest negatives)

* Register reuses the existing endpoint, no second mechanism — verified
  (`app/routers/auth.py:73-84`, `auth_service.register` at `:208`); 409/422 paths exist as
  claimed; the `err.response` attachment is additive and the single mechanism for status
  discrimination.
* num_children absent-means-unchanged matches the `postal_code` precedent exactly
  (`app/routers/profile.py:44-48,90-104`); the INFORMATIONAL-ONLY recommendation is honest and
  the pool-starvation justification checks out (`src/planner/menu.py:114` servings filter,
  `:160-162` truncation).
* Boost-not-filter is structurally sound: with the flag off the rank key orders identically
  (constant middle term, same rng draw count), so the regression-guard claim holds.
* Migration rides `ensure_columns` correctly; `recipes` is on the shared `Base`
  (`src/recipes/store.py:13`) so `create_all` precedes the inspect and `get_columns` cannot hit
  a missing table.
* Roster coverage is complete: all six roster titles (`app/optimizer/recipes.py:38-88`) are
  assigned a value by the design.
* No new defect found in the num_children UI contract; no testability loss in the listed pytest
  plan; no TODO/FIXME or hygiene issue introduced by the design document itself.

## Required fixes before build (all cheap, none structural)

1. Name the module of the `FamilyPrefs` that gains `prefer_kid_friendly` (P1).
2. Specify register-form visibility on `showLoggedIn`/`showLogin` and mode reset (P2).
3. Specify the badge's real rendering mechanism (escapeHtml or DOM nodes) (P2).
4. Add the register input/form ids; state the 422 detail-surfacing; state the
   checkbox 0-vs-null rule; correct the "default 0" migration claim (P3s).

# JUDGED: 44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a
# VERDICT: FIX
