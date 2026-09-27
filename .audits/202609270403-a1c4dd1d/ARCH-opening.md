# ARCH OPENING — placement plan, MC 1355.18 (T11 build), matapp

Run dir: `/srv/workspace/matapp/.audits/202609270403-a1c4dd1d/`. Repo: `/srv/workspace/matapp`
(branch main, HEAD 05c0a3e). Layout v2 (workspace-convention) verified against the live tree.

NOTE (mechanics): this session cannot spawn subagents (`subagent depth 2 exceeds maxDepth 1`,
approval prompts disabled) — the phases run INLINE in the orchestrating child, with this opening
plan still gating every write. Recorded in CYCLES.md.

## Gate

Nothing is written before this plan. Every file below lands at an existing layout-v2 path;
no sibling dirs (`svarkor-matapp-*`, `matapp-audit-*`) are created.

## Placement plan

Project tree (build phase edits/creates — all existing paths except one):
- `templates/index.html` — edit: auth toggle + register form (inside `#auth-login`), profile
  num-children field + kid-friendly checkbox.
- `static/js/utils/api.js` — edit: `Endpoints.register`, `err.response` attachment.
- `static/js/ui/auth.js` — edit: `setMode`, `submitRegister`, error mapping, mode reset.
- `static/js/ui/profile.js` — edit: num_children field + prefer_kid_friendly checkbox, edit tracking.
- `static/js/ui/suggestions.js` — edit: kid-friendly badge (escaped/DOM-safe), escape `dish_id`.
- `app/models/profile.py`, `app/profile_service.py`, `app/routers/profile.py` — edit: num_children
  + prefer_kid_friendly (model, persistence, wire).
- `app/db.py` — edit: three `_NEW_COLUMNS` entries (guarded ALTER).
- `app/optimizer/optimizer.py` — edit: `FamilyPrefs.prefer_kid_friendly` (the class the menu
  router instantiates — DA P1 binding correction).
- `app/optimizer/recipes.py` — edit: `Recipe.kid_friendly` + roster values.
- `app/routers/menu.py` — edit: `MenuDay.kid_friendly` additive field.
- `src/planner/menu.py` — edit: rank-key tiebreak (reads the router-built prefs).
- `src/recipes/store.py`, `src/recipes/seed.py`, `src/recipes/scraper.py` — edit: kid_friendly
  column, seed values, scraper passthrough.
- `docs/ARCHITECTURE.md` — CREATE (does not exist today: `test -e` fails, verified). ~150 lines.
- `tests/test_profile_children.py`, `tests/test_menu_kid_friendly.py`,
  `tests/test_migration_t11.py`, `tests/test_recipe_kid_friendly.py` — CREATE (12 fixture tests).

Run dir `.audits/202609270403-a1c4dd1d/` (this run's verdicts/bookkeeping):
- `ARCH-opening.md` (this file) · `TEST-verdict.md` · `DA-verdict.md` · `ARCH-verdict.md`
  (later cycles: `-c2`, `-c3`) · `CYCLES.md` · `DONE.md` · `HANDOFF.md` · `.tmp/` scratch.
- Build artifact stays where the task names it: `.audits/202609260913-e6190a72/T11-build.md`.

Scratch (live-sanity server logs, browser shots): run dir `.tmp/` only — never the repo root.

## Layout-v2 conflicts

None found: the repo already follows one-dir-per-project with `docs/` absent (to be created),
`.audits/<run>/` per run, `.tmp/` at repo root for pre-existing scratch. No action.

# VERDICT: PASS
