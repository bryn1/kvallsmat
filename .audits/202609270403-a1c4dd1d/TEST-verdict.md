# TEST verdict — T11 build (MC 1355.18), run 202609270403-a1c4dd1d

NOTE: fan-out was mechanically impossible in this session (`subagent depth 2
exceeds maxDepth 1`); the test phase ran inline in the orchestrating child,
with the checks below executed for real this session.

Independent verification of the T11 build (commits 9a5b299 + a742cb3):

1. Fresh suite (clean `__pycache__`/`.pytest_cache`):
   `/srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q` →
   **116 passed, 0 failed**, `PYTEST_EXIT=0`. Log:
   `.audits/202609270403-a1c4dd1d/.tmp/fresh-suite.log`.
2. The 12 design-specified fixture tests exist and pass:
   test_profile_children (6), test_menu_kid_friendly (4), test_migration_t11 (1),
   test_recipe_kid_friendly (2) — 13 written, all green.
3. The boost test genuinely discriminates: flag-off picks "Ugnsbakad lax…" first
   (seed 103), flag-on promotes "Köttbullar med gräddsås och potatis" — the
   assertion fails if the tiebreak is removed (the flag-off/flag-on day orders
   differ by assertion, not by construction).
4. Planted-bad (red) evidence for the date-independent fixture fix: with the
   ORIGINAL hardcoded W39 dates the ingest wiring yields `LABEL: None`,
   `WRITTEN: 0` (reproduced standalone this session) — the green run is not
   vacuous.
5. Live sanity (local server 127.0.0.1:8971, temp DB): register 200, PUT
   profile (num_children=2, prefer_kid_friendly=1) 200 with echo, GET menu 200
   with `kid_friendly: true` on köttbullar/pannkakor/korv-stroganoff days and
   false on lax/kyckling days. Transcript: `.tmp/live/`.
6. No network in the offline suite (temp-DB client fixture); the only real
   network was the once-only live sanity.

# JUDGED: 72682e8f5648873885c77551ecd2bb63d3ed3fd31fe718e1ba9a40dc675491bd
# VERDICT: PASS
