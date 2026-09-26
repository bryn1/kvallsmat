# T8 verification verdict — MC 1355.10 (Tjek adapters, commit c16d088)

Verifier note: this session runs at subagent depth 1 — spawning verifying
children is rejected by the harness (`subagent depth 2 exceeds maxDepth 1`),
so the test + devils-advocate verification was executed INLINE by the
producing `code` child, with every decisive check quoted below. The verdict
file carries exactly one verdict line.

## Checks run (all this session, real output)

1. **Commit on main**: `git show --stat c16d088` → "matapp: Willys+Coop offers
   via Tjek squid API (MC 1355.10)", 5 files (tjek.py new, dispatch + config +
   2 test files). Matches the artifact's diff summary.
2. **Fresh suite**: `rm -rf tests/__pycache__ src/fetcher/adapters/__pycache__
   .pytest_cache && /srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q`
   → `59 passed, 3 warnings in 6.35s`, `EXIT=0`.
3. **Planted-bad runs (every mutation went RED, then clean revert):**
   - MUT1 catalog pick broken (return first catalog unconditionally):
     `4 failed, 2 passed` (test_pick_catalog_grace_fallback,
     test_pull_happy_path_through_pull_grocer, +2).
   - MUT2 currency guard removed: `2 failed, 4 passed`
     (test_pull_happy_path..., test_pull_fail_tolerant).
   - MUT3 adapter-side id prefix (`"coop-" + ext_id`):
     `1 failed, 5 passed` (test_parse_hotspots_happy_and_drops — the
     single-prefix invariant assertion).
   - `git diff --stat` after reverts: empty (`REVERT_CLEAN=0`).
4. **Final green after reverts**: `59 passed, 3 warnings in 6.49s`, EXIT=0.
5. **Test quality**: tests import the real module (`src.fetcher.adapters.tjek`)
   and exercise it through `pull_grocer`; negative paths covered (non-200,
   network exception, bad JSON, missing price, non-SEK, no covering catalog,
   expired-only listing); the happy-path test asserts concrete field values,
   not just counts.
6. **File hygiene**: tjek.py ~180 lines (one concern: the Tjek adapter);
   test file ~170 lines; no monoliths.
7. **Live sanity** (recorded in the artifact, run this session through the
   real pipeline): willys 111 entries, coop 97 entries — raw JSON at
   `.audits/202609260913-e6190a72/T8-live-sanity.json`.

## Findings

- No P0/P1 found. The 48h grace fallback is an intentional, tested adaptation
  to the observed Coop listing rotation (documented in the artifact).
- Known limitation (P3, recorded): Tjek API terms of service UNVERIFIED
  (inherited from T7a); rate limits unknown — weekly pull volume is 2 requests
  per grocer.

# VERDICT: PASS
