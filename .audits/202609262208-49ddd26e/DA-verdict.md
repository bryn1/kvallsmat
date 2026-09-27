# DA-verdict — T11 design (MC 1355.17), cycle 1

Deliverable judged: `/srv/workspace/matapp/.audits/202609260913-e6190a72/T11-design.md`
(commit 4a37157) + SEC-findings.md in this out dir. Every claim below was re-checked against
the real code this session, not against the design's own text.

## Checks that held

* R1 Register endpoint exists, open, auto-login, 409/422 — VERIFIED (`app/routers/auth.py:73-84`,
  `app/auth_service.py:208-227`). Design correctly adds zero new endpoints.
* R3 absent-means-unchanged semantics for both new profile fields mirror the postal_code rule
  (`app/routers/profile.py:44-48,90-104`) — VERIFIED, including explicit-null-clears.
* R4 Boost-as-tiebreak is structurally safe: with `prefer_kid_friendly` off the rank key
  `(-hits, 0, rng)` orders identically to today's `(-hits, rng)` (0 compares equal for every
  recipe) — the no-kid-friendly-recipes regression guard holds by construction, and pool
  exhaustion (`src/planner/menu.py:160-162`) can never be triggered by a tiebreak. VERIFIED.
* R5 `MenuDay.kid_friendly` additive field is fillable from the existing `by_title` lookup
  (`app/routers/menu.py:160,176`) — VERIFIED.
* R7 Test list matches the real `tests/conftest.py` temp-DB `client` idiom — VERIFIED.
* R8 No mechanism duplication: Endpoints.register reuses apiPost; setMode has no existing
  counterpart; kid_friendly mirrors the existing vegetarian/budget_tier two-representation
  precedent. VERIFIED.
* R9 Security pass (SEC-findings.md): no CRITICAL/HIGH; S1 enumeration is pre-existing and
  owner-ratified. Concurred.

## Findings (why this is not SHIP yet)

* **F-DA1 (HIGH, design defect):** §a places `<div id="auth-register">` as a SIBLING of
  `<div id="auth-login">`. `showLoggedIn()` hides only `#auth-login`
  (`static/js/ui/auth.js:41-48`), so a logged-in user opening Konto would still see the
  register form and toggle. Repro: log in, switch to Konto — with the design as written the
  register form stays visible. Fix: the `#auth-login` wrapper must contain the toggle AND both
  forms; `#auth-register` lives inside it, so the existing hide/show covers everything.
* **F-DA2 (MEDIUM, spec gap):** the schema table names the `recipes.kid_friendly` column but
  the design never names the ORM declaration `src/recipes/store.py` `Recipe.kid_friendly =
  Column(Integer, default=0)` — without it, `create_all` on a FRESH database omits the column
  and the seed upsert would fail. A coder child should not have to guess this; name the file
  and the column explicitly.
* **F-DA3 (LOW, accepted trade-off, recorded not blocking):** a tiebreak-only boost promotes
  kid-friendly dishes only on equal offer-hit counts; with dense offer weeks the effect is
  mild. This is the correct trade-off (offer-hits are the product's headline objective), but
  the UI help text must not overpromise — "prioriteras" (as designed) is accurate, "visar
  barnvänliga rätter först" would not be.

## Verdict

F-DA1 and F-DA2 go back to the producer; the design is otherwise sound.

# VERDICT: FIX
