# DONE — 202609270325-e12479d6 (MC 1355.18, T11 DA gate)

| ID | claim | STATUS | evidence |
|---|---|---|---|
| D1 | Cycle-2 design (T11-design-c2.md) resolves all 7 DA findings (P1 FamilyPrefs module naming; P2 register-form visibility; P2 badge rendering mechanism; 4×P3) | UNVERIFIED | the design producer child has NOT run: this session is a depth-1 subagent, `subagent` spawn rejected ("depth 2 exceeds maxDepth 1"); parent must spawn the design child with .audits/202609260913-e6190a72/T11-da-verdict.md as context |
| D2 | TEST-verdict.md from an independent test child (design claims re-verified against HEAD 4a371578) | UNVERIFIED | same depth-1 spawn rejection; parent must spawn the test child writing to this out dir |
| D3 | ARCH-verdict.md from a design-profile child (placement + architecture-vs-reality) | UNVERIFIED | same depth-1 spawn rejection; parent must spawn the arch child writing to this out dir |
| D4 | DA cycle-2 re-review (DA-verdict-c2.md) on the fixed design | UNVERIFIED | this session IS the devils-advocate and will write DA-verdict-c2.md once T11-design-c2.md exists; cycle-1 verdict stands FIX (.audits/202609260913-e6190a72/T11-da-verdict.md, last line `# VERDICT: FIX`) |
| N1 | A second register endpoint/mechanism beside POST /api/auth/register is impossible under the design | PASS | `grep -rn "post(\"/register\"" app/routers/` → exactly one hit, app/routers/auth.py:73; design §a wires `Endpoints.register = '/api/auth/register'` to that existing route (no new route in the design; api.js currently has no register entry — the gap the design fills) |
| S1 | surface backend | N/A | design-gate card: no backend file changed this run (git status shows only .audits/ additions); the build card owns implementation |
| S2 | surface db | N/A | migration is design content only (guarded ALTER via app/db.py ensure_columns); no schema change executed this run |
| S3 | surface frontend | N/A | no template/JS file changed this run; UI work belongs to the build card |
| S4 | surface api contract | PASS | design's contract summary re-verified against the code: register route exists and is unchanged (app/routers/auth.py:73-84, 409/422 paths at auth_service.py:208-227); profile PUT absent-means-unchanged precedent confirmed (app/routers/profile.py:44-48, 90-104); menu additive MenuDay field matches app/routers/menu.py:59-69,172-178 |
| S5 | surface tests | N/A | test list is design content; no test file changed this run; pytest-in-out-dir requirement vacuous (no .py in the out dir) |
| S6 | surface docs | PASS | design's architecture-doc note is true: `ls docs` → "No such file or directory" at HEAD 4a371578, so the build card must create docs/ARCHITECTURE.md exactly as the design states (§Architecture-doc note) |
| S7 | surface deploy | N/A | no deploy surface in a design-gate card; hosting/deploy untouched |
