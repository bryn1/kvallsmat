# HANDOFF — T11 build (MC 1355.18), run 202609270403-a1c4dd1d

WHAT: matapp T11 implemented end to end on main — register/login toggle on the
Konto page (reusing the existing POST /api/auth/register, F0 id fix),
profile.num_children + prefer_kid_friendly (absent-means-unchanged PUT,
INFORMATIONAL only), recipes.kid_friendly (ORM column + guarded ALTER + seed
values + scraper passthrough), planner boost-as-tiebreak via the optimizer
FamilyPrefs, additive MenuDay.kid_friendly + escaped UI badge, and a new
docs/ARCHITECTURE.md.

COMMITS: 9a5b299 (implementation) + a742cb3 (date-independent ingest fixtures)
on main, NOT pushed. Bookkeeping commits by the parent loop: a92d88b, d4deb54,
ca97aa5, 987c336, 160afe0.

EVIDENCE:
- Build artifact: .audits/202609260913-e6190a72/T11-build.md (last line
  `# VERDICT: PASS`)
- This run: .audits/202609270403-a1c4dd1d/ — ARCH-opening.md, TEST-verdict.md
  (PASS), DA-verdict.md (SHIP), ARCH-verdict.md (PASS), DONE.md, CYCLES.md,
  .tmp/fresh-suite.log (116 passed, EXIT=0), .tmp/live/ (sanity transcript)
- Independent DA gate over the design/in-progress tree:
  .audits/202609270325-e12479d6/ (cycles 1-4, final SHIP)

OPEN ITEMS:
- T11b (named in the design): feed num_children into servings planning, with
  pool-starvation tests — deliberately NOT done here.
- Push of main to origin is the parent's call (task says do NOT push).
- MECHANICS DEVIATION: fan-out was impossible in this session (subagent
  maxDepth 1); all phases ran inline with the verdict discipline preserved.
  The independent DA gate over the design DID run as separate children in the
  parent's own run dir.
