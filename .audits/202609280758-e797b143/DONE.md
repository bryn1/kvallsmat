# DONE.md — MC 1355.19 T11 test gate (out dir /home/svarkor/Matapp/.audits/202609280758-e797b143)

| ID | claim | STATUS | evidence |
|----|-------|--------|----------|
| D1 | Fresh suite green: clean `__pycache__`/`.pytest_cache`, `pytest tests/ -q` = 116 passed, EXIT=0 | PASS | Executed this session, output in TEST-verdict.md Check 1: `116 passed, 3 warnings in 12.59s`, EXIT=0; re-run after mutations `116 passed ... 13.32s`, EXIT=0 |
| D2 | T11 tests reach the real implementation, not mocks | PASS | TEST-verdict.md Check 2: real endpoints via TestClient, real `plan_menu`, real `seed_starter`/`scrape_recipes`, real `ensure_columns` on a legacy-schema DB |
| D3 | Suite goes RED when the implementation breaks (2 mutations), then tree restored clean | PASS | TEST-verdict.md Check 3: mutation A (boost tiebreak removed) → `1 failed, 3 passed`; mutation B (register auto-login removed) → `7 failed, 5 passed`; `git status --short` empty + `git diff --stat` empty after restore |
| D4 | P0 invariant: store-scoped write cannot overwrite a NULL chain-level row | PASS | `pytest tests/test_store_scoping.py::test_p0_store_scoped_write_never_overwrites_chain_level_row` passed (TEST-verdict.md Check 4); test body asserts NULL-row survival in both orders |
| D5 | Absent-means-unchanged: PUT without num_children/prefer_kid_friendly does not clear saved values | PASS | `test_num_children_absent_means_unchanged` + `test_prefer_kid_friendly_absent_means_unchanged_and_roundtrip` passed (TEST-verdict.md Check 5) |
| D6 | TEST-verdict.md exists with JUDGED pin | PASS | /home/svarkor/Matapp/.audits/202609280758-e797b143/TEST-verdict.md, last lines `# JUDGED: 44136fa3…` / `# VERDICT: PASS` |
| D7 | devils-advocate phase verdict (DA-verdict.md) written by a DA child | BLOCKED | This session is a depth-1 subagent; every `subagent` call is rejected by the harness (`Error: subagent depth 2 exceeds maxDepth 1`, two attempts, resume 1 and 2), and the gate forbids writing a verdict file myself. Parent (session-4609f600) notified with the full spawn recipe. |
| D8 | arch phase verdict (ARCH-verdict.md) written by a design child | BLOCKED | Same blocker as D7: maxDepth 1 prevents spawning the verifying child from this session; parent notified. |
| D9 | No untracked file created during the run in the git tree | PASS | Only audit artifacts created (`.audits/.../TEST-verdict.md`, this out dir); no source files touched; `git status --short` shows only the two audit paths, left for the orchestrator to commit per its gate rules |
| N1 | Forbidden behaviour — a store-scoped offer write silently overwriting a chain-level NULL row — is impossible | PASS | Executed regression `test_p0_store_scoped_write_never_overwrites_chain_level_row` (both pull orders asserted, 2 rows always) — passed; see TEST-verdict.md Check 4 |
| S1 | surface backend | PASS | T11 backend (profile fields, register endpoint, planner tiebreak) exercised via real TestClient endpoints in the 116-test suite; D1–D5 |
| S2 | surface db | PASS | `test_migration_t11.py` + `test_store_scoping.py` migration tests pass: three T11 columns added idempotently on a legacy DB |
| S3 | surface frontend | N/A | Register UI JS/HTML (templates/index.html, static/js/ui/auth.js) has no pytest coverage; UI-level verification is the frontend/DA phase's surface, which is BLOCKED (D7) — not verifiable from the test profile's harness scope |
| S4 | surface api contract | PASS | Profile PUT/GET contract (absent-means-unchanged, explicit-null, 422 bounds, GET echo) verified end-to-end through the real router (D5, TEST-verdict.md Check 5) |
| S5 | surface tests | PASS | 116 passed EXIT=0 fresh (D1); mutation red-proofs prove the tests can fail (D3) |
| S6 | surface docs | BLOCKED | docs/ARCHITECTURE.md truth-vs-tree check is the arch phase's deliverable; the arch child could not be spawned (D8) |
| S7 | surface deploy | N/A | No deploy surface in this card's scope (local repo build + tests only; no hosting.yaml change in T11) |
