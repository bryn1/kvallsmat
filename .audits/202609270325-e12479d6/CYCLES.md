# CYCLES — 202609270325-e12479d6

| cycle | trigger | action | outcome |
|---|---|---|---|
| 1 | T11 DA gate (MC 1355.18) | devils-advocate child attacked T11-design.md against HEAD 4a371578; verdict at .audits/202609260913-e6190a72/T11-da-verdict.md (copy: DA-verdict.md here) | FIX — P1 FamilyPrefs ambiguity (two classes; literal build 500s GET /api/menu), 2×P2 (register form visibility on showLoggedIn; badge textContent-vs-innerHTML mismatch), 4×P3 |
| 2 | resume loop: DA-c2 on the in-flight build tree | fresh DA pass over HEAD a92d88b + uncommitted build diff; executed pytest (10 failed/93 passed, all one root cause) | FIX — P0: ("recipes","kid_friendly") in _NEW_COLUMNS crashes boot() (NoSuchTableError; recipes ORM never imported in app path); cycle-1 P1 verified resolved |
| 3 | final resume: DA-c3 on the settled build tree | full pytest (8F/108P), per-finding verification of all cycle-1/c2 findings, pre-existing ingest failures isolated via throwaway worktree at 4a371578 | FIX — P1-A ensure_columns legacy-DB crash (3 T10d-F8 tests), P1-B build own new tests red (boost fixture, NameError, recipe fixtures); D2/D3 BLOCKED on spawn limitation |
