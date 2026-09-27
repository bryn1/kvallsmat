# HANDOFF — T11 design (MC 1355.17, parent 1355)

**What:** Design for three owner-requested pieces on matapp: (a) a login/register toggle on
the Konto page wired to the EXISTING `POST /api/auth/register` (no new endpoint); (b)
`profile.num_children` (nullable int, guarded ALTER, absent-means-unchanged) — informational
only in this card, with the planner-feeding follow-up named T11b and justified; (c)
`recipes.kid_friendly` 0/1 (guarded ALTER + ORM column + seed values for 7 named dishes +
scraper passthrough + optimizer-roster mirror) with profile option `prefer_kid_friendly` and
a BOOST-as-tiebreak planner behaviour that structurally cannot break the menu when no
kid-friendly recipes exist.

**Deliverable:** `/srv/workspace/matapp/.audits/202609260913-e6190a72/T11-design.md`
(commits 4a37157 → cfa1662), last line `# VERDICT: SHIP`. Copy + verdicts + findings in this
out dir: `T11-design.md`, `SEC-findings.md`, `DA-verdict.md` (cycle 1, FIX),
`DA-verdict-c2.md` (SHIP, JUDGED 583daa4b…), `CYCLES.md`, `DONE.md`.

**Decisive check re-run by the orchestrator of this run:** the JUDGED hash
(`python3 /usr/local/bin/dod_judged_hash.py /home/svarkor/Matapp/.audits/202609262208-49ddd26e
--base 1664b9471b64acd293274edd04dc63e4d0f60b74`) printed
`# JUDGED: 583daa4b6f76b6d549381eb0ef2862523fcde2995857a3511e45e8c8b6ae375e`, written directly
above the cycle-2 verdict line; the design doc's last line is `# VERDICT: SHIP`.

**Process deviation (honest record):** the task gate mandated fan-out, but this session is a
depth-1 subagent — the `subagent` spawn was rejected by the harness (`subagent depth 2 exceeds
maxDepth 1`), the same blocker recorded in the parent run's CYCLES.md for T7a. Phases 2-3 ran
inline with the adversarial pass kept structurally separate (findings written before fixes;
cycle-1 FIX verdict preserved unedited; cycle-2 verdict on the amended, re-committed doc).

**Open items for the BUILD card (T11 next):**
1. Implement per the design; the test list (4 files / 12 tests) is the acceptance floor.
2. Create `docs/ARCHITECTURE.md` (does not exist — verified) in the build run; the ARCH
   closing verdict depends on it.
3. Follow-up card T11b: feed `num_children` into servings planning (design §b names the
   pool-starvation risk that kept it out of T11).
4. Known pre-existing bug the design fixes as a rider: `auth.js` targets nonexistent id
   `auth-login` (F0) — the login form is never hidden when logged in.
