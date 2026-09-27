# DA-verdict — T11 design (MC 1355.17), cycle 2

Deliverable judged: `/srv/workspace/matapp/.audits/202609260913-e6190a72/T11-design.md`
(commit cfa1662, the cycle-1 FIX amendments applied) + SEC-findings.md in this out dir.
Byte-identical copy of the design held in this out dir as `T11-design.md` (diff-verified).

## Cycle-1 findings — re-checked on the amended doc

* F-DA1 (register form sibling) — FIXED: §a now wraps the toggle row AND both forms inside
  `<div id="auth-login">`, with `#auth-register` explicitly inside it and the sibling case
  named as the defect it was. `showLoggedIn()` (`static/js/ui/auth.js:41-48`) now hides the
  whole choice region. Re-derived from the amended text + the JS — VERIFIED.
* F-DA2 (missing ORM declaration) — FIXED: §c now names
  `src/recipes/store.py` `Recipe.kid_friendly = Column(Integer, default=0)` and states why
  both the model column (fresh DBs via create_all) and the guarded ALTER (existing DBs) are
  needed. VERIFIED.
* F-DA3 (tiebreak-boost mildness) — stands as an accepted, recorded trade-off; the UI help
  text says "prioriteras", which is accurate for a tiebreak. No action.

## Fresh adversarial pass over the amended sections

* The amended §a introduces no new seam: `setMode` toggles inner forms only; the existing
  `showLogin`/`showLoggedIn`/`showError` functions are reused unchanged; the toggle buttons
  are `type="button"` so they cannot submit the surrounding form. VERIFIED.
* The amended §c keeps one mechanism per concern: model column + guarded ALTER + seed values +
  scraper passthrough + roster mirror — the same five-point shape the T10e columns used.
  VERIFIED against `app/db.py:75-108` and `src/recipes/store.py:26-27` (vegetarian precedent).
* Doc integrity: one subject, ~220 lines, ends with the producer verdict line
  `# VERDICT: SHIP`; no TODO/FIXME added; the deliverable path is the layout-v2 `.audits/`
  run dir, no sibling-dir invention. VERIFIED.
* Security findings (SEC-findings.md) unchanged by the amendments — S1..S5 all still accurate.

## Verdict basis

Both cycle-1 findings are fixed in the committed design; no new defect found in the amended
sections; every grounding claim in the design was re-checked against the real code this
session. The design is implementable without guessing: every file, seam, column, endpoint
field, UI id and test is named.

# JUDGED: 583daa4b6f76b6d549381eb0ef2862523fcde2995857a3511e45e8c8b6ae375e
# VERDICT: SHIP
