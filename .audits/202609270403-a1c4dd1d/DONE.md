# DONE.md — T11 build (MC 1355.18), run 202609270403-a1c4dd1d

ID | claim | STATUS | evidence
--- | --- | --- | ---
D1 | Commit on main implementing the pinned design (register toggle + F0 fix, num_children informational, kid_friendly column+seed+planner boost+UI badge) | PASS | commits 9a5b299 + a742cb3 on main (`git log --oneline -2`); diff summary in .audits/202609260913-e6190a72/T11-build.md
D2 | docs/ARCHITECTURE.md created and matches reality | PASS | docs/ARCHITECTURE.md; table/port/endpoint claims re-derived this session (see ARCH-verdict.md)
D3 | 12 design-specified fixture tests present and passing | PASS | 13 tests across tests/test_profile_children.py (6), test_menu_kid_friendly.py (4), test_migration_t11.py (1), test_recipe_kid_friendly.py (2); all green in fresh-suite.log
D4 | Fresh suite (clean __pycache__/.pytest_cache) ALL pass, EXIT=0 | PASS | `PYTEST_EXIT=0`, "116 passed" in .audits/202609270403-a1c4dd1d/.tmp/fresh-suite.log (after fixround a742cb3 made the ingest fixtures date-independent)
D5 | Live sanity ONCE against a LOCAL server (register via UI endpoint, PUT profile num_children=2 + prefer_kid_friendly=1, GET menu, badge presence) | PASS | HTTP 200/200/200 with echoed fields and kid_friendly:true on kid dishes; transcript .audits/202609270403-a1c4dd1d/.tmp/live/ (server 127.0.0.1:8971, temp DB, stopped after)
D6 | T11-build.md artifact exists with last line `# VERDICT: PASS|FAIL|BLOCKED` | PASS | .audits/202609260913-e6190a72/T11-build.md, last line `# VERDICT: PASS`
D7 | Git tree holds the out dir with no untracked run files; no TODO/FIXME added | PASS | `git status --short` empty after bookkeeping commit; `grep -rn "TODO\|FIXME" app/ src/ static/ templates/ tests/` = 0 hits
D8 | File hygiene: source <= 400 lines, one concern per file | PASS | largest changed source app/routers/menu.py 273 lines (`wc -l`); no TODO/FIXME
D9 | pytest in the out dir calls into every .py source file there | N/A | the out dir contains no .py source files (verdicts/bookkeeping only); the repo suite covers the repo's .py files
N1 | XSS via the suggestions innerHTML template (unescaped dish_id/store labels) is impossible | PASS | escapeHtml applied to dish_id, date and store labels in static/js/ui/suggestions.js; badge is static text; `node --check` clean on all ui/utils JS
S1 | surface backend | PASS | app/ changes covered by 116-test suite incl. 13 new T11 tests; live sanity exercised register/profile/menu over real HTTP
S2 | surface db | PASS | guarded ALTERs + ORM columns; tests/test_migration_t11.py proves legacy-DB migration + idempotence
S3 | surface frontend | PASS | templates/index.html + auth.js/profile.js/suggestions.js/api.js; `node --check` clean; register toggle + badge wired to existing endpoints
S4 | surface api contract | PASS | GET/PUT /api/profile echo new fields (absent=unchanged, null=clear); GET /api/menu additive kid_friendly; no breaking shape change (old fields untouched)
S5 | surface tests | PASS | fresh suite 116 passed EXIT=0 (.tmp/fresh-suite.log)
S6 | surface docs | PASS | docs/ARCHITECTURE.md created; ARCH-verdict.md PASS
S7 | surface deploy | N/A | no deploy change in this card (server.py/DEPLOY.md untouched; port 8141 unchanged); not pushed per task
