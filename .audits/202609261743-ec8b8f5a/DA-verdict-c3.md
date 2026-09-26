# T10f — DA verdict cycle 3: re-gate over the CURRENT tree (final cycle)

Cycle 3 of the T10f adversarial gate — FINAL cycle (resume 3/3). Trigger: the
deliverable changed after cycle 2's judgment (the integrity hash moved from
`d38fcbda…` to `4c0c9ca6…`; `tests/test_store_scoping.py` changed since). This is a
FRESH verdict over the tree as it stands NOW; it does not edit cycles 1–2.

## State of the tree under judgment

HEAD `43a2b75` (audit artifacts) on top of `2f44683` (the T10f P2 fixes) on top of
`793f991` (the T10e build). The working tree additionally carries UNCOMMITTED,
FOREIGN in-flight work by a parallel session: `app/main.py`, `app/routers/menu.py`,
`src/scheduler/periodic.py` (+118 lines: `run_store_scoped_ingest`,
`collect_resolved_willys`, the storeflyer label join), `static/js/ui/{profile,
suggestions}.js`, `.gitignore`, and `tests/test_store_scoping.py` (+204 lines of new
tests for that wiring). This gate did not author, commit, or revert any of it.

## Decisive check re-run by THIS gate (VERIFIED this session)

Clean `__pycache__`/`.pytest_cache`, then
`/srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q` →

```
3 failed, 100 passed, 3 warnings in 9.06s
PYTEST_EXIT=1
```

The 3 failures are ALL in the foreign session's OWN new tests for its own new wiring:

1. `test_store_scoped_ingest_fail_tolerant_per_store` — `assert written == 1` got 0;
   log shows `WARNING src.scheduler.periodic:periodic.py:170 no willys grocer
   configured — store-scoped ingest skipped` (the test's PlannerConfig wiring does not
   reach the function's grocer lookup).
2. `test_store_scoped_ingest_label_falls_back_to_store_name` — same signature/wiring
   mismatch, same warning, `assert 0 == 1`.
3. `test_periodic_main_runs_store_scoped_pass` — test bug: misplaced parenthesis,
   `.fetchall()` called on the `TextClause` instead of the execute result
   (`'TextClause' object has no attribute 'fetchall'`).

## Verdict reasoning

- The COMMITTED deliverable (793f991 + 2f44683) remains SHIP-worthy: cycle 2 verified
  97 passed EXIT=0 on exactly that tree, the P0 invariant, migration, auth-gating and
  PUT semantics all held, and the cycle-1 P1 was corrected as design-sanctioned
  (T10b §6 step 5).
- The CURRENT tree cannot be SHIPped: its own newest tests are red (3 failed,
  PYTEST_EXIT=1). The red is entirely inside the parallel session's uncommitted
  wiring — the producing work for the store-scoped ingest this gate flagged in
  cycle 1. This gate cannot fix, commit, or revert another session's in-flight work,
  and a verdict over a moving tree would be stale on arrival.
- This is resume 3/3 of the mechanical loop: per the task gate the loop now ends
  BLOCKED, with one DONE.md row per claim that could not be verified, reported to the
  owner via the orchestrator. The blocked condition is concrete: the parallel
  session's store-scoped-ingest wiring is unfinished (its own 3 new tests fail) and
  uncommitted; no gate can certify the tree until that session lands or drops it.

## What the finishing session must do before the next gate

1. Make its 3 new tests green (fix the PlannerConfig/grocer wiring the two ingest
   tests exercise; fix the `.fetchall()` parenthesis in
   `test_periodic_main_runs_store_scoped_pass`).
2. Update the `offer_sources` shape assertion it already half-touched (the endpoint
   now returns `store_name` too).
3. Commit the whole wiring as ONE commit with the mandated attribution form, then
   request a fresh DA cycle over that commit.

# JUDGED: 041f48a7f33f3f10606ccbb6292eed7ad5fc63cc254bc18da719ee057d043ec7
# VERDICT: FIX
