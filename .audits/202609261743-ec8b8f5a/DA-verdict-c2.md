# T10f — DA verdict cycle 2: re-gate after the FIX cycle (store-level selection)

Cycle 2 of the T10f adversarial gate. Trigger: `DA-verdict.md` (cycle 1) ended
**VERDICT: FIX** (1×P1, 2×P2, 3×P3, 2×P4). This verdict is a FRESH judgment over the
tree AFTER the fix cycle — it does not edit cycle 1.

## What happened this cycle

- **Structural note:** this gate runs as a leaf child (subagent maxDepth 1); the
  re-spawn of a `code` child was attempted and rejected by the harness
  (`subagent depth 2 exceeds maxDepth 1`), the same structural limit the T10e build
  child recorded in its CYCLES. Per the mechanical loop's resume instruction the two
  P2 fixes were therefore applied inline by this gate, committed as **`2f44683`**
  ("matapp: T10f DA fixes — endpoint-level menu store-clause test + preview param
  validation (MC 1355.17)", 2 files, +61/−1).
- **Suite re-run by this gate after the fix commit** (clean `__pycache__`/
  `.pytest_cache`): `/srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q` →
  `97 passed, 3 warnings in 8.40s` — **EXIT=0** (VERIFIED this session; 95 → 97 with
  the two new tests).

## Disposition of cycle-1 findings

### P1-1 (store-scoped ingest not wired) — PREMISE CORRECTED, downgraded to P2, design-sanctioned
Cycle 1 claimed T10b §3 "explicitly puts the Willys store-scoped ingest inside THIS
card's scope". Re-reading the pinned design refutes that reading: §6 step 5 says
"Next ingest (**boot or later store-scoped cards**) stamps `offers.store_id`" — the
design itself sanctions the population landing in a later card, and §3's Tjek bullet
requires only the ADAPTER change (`pull_store_scoped` with RULE-1 stamping), which
793f991 delivers and the live sanity proved on a real catalog (Willys Alingsås
Hagaplan, 111 stamped entries). The build record disclosed the deferral; the staged
rollout is the design's own wording, not a deviation. Remaining substance, now P2:
`pull_store_scoped` is dead code until a wiring card lands — the menu store clause
cannot fire on live-ingested store-scoped rows yet. This is a roadmap fact, recorded
in the build record and the design; it does not block THIS card's DoD.

### P2-1 (no endpoint-level menu test) — FIXED in 2f44683
`tests/test_store_scoping.py::test_menu_endpoint_applies_store_clause_and_dedup` now
drives `GET /api/menu` through the real endpoint with a profile whose fake resolve
holds store "2103", upserts a chain-level row AND a store-scoped row for UNRESOLVED
store "9999", and asserts the "9999" row is absent from `offer_sources` while the
chain-level row survives. Removing the `_apply_store_clause`/`_dedup_by_name` calls
from `app/routers/menu.py:141-142` now goes RED.

### P2-2 (preview param unvalidated/unnormalized) — FIXED in 2f44683
`app/routers/stores.py` now applies the SAME `POSTAL_CODE_RE` + digits-only
normalization as `PUT /api/profile` (one postnummer rule, imported from
`app/routers/profile.py` — no second regex): malformed → 422 (auth gate still first,
so anonymous malformed stays 401), valid spaced input normalized before the resolve.
`test_stores_preview_rejects_malformed_and_normalizes_postal` proves both the 422 and
that `"414 51"` reaches the resolver as `"41451"`.

### P3-1/P3-2/P3-3 (innerHTML of third-party strings; raw store_id shown; Coop cold warm inside first PUT) — recorded, non-blocking
All three are hardening/UX items on a POC-class app, classified per the scope rules;
none is a correctness or data-loss defect. They stay on the record for a hardening
card; fixing them here would be scope creep on a gated build.

### P4-1/P4-2 — unchanged, non-actionable (uuid-collision IntegrityError path; `.tmp/` gitignore nit).

## New observation this cycle (recorded, outside this gate's scope)

`git status` shows an UNCOMMITTED, foreign modification to `src/scheduler/periodic.py`
(an unused `pull_store_scoped` import + a `_WILLYS_STOREFLYER` constant — a half-done
start at exactly the P1-1 wiring). It is NOT authored by this run, is incomplete, and
this gate neither commits nor reverts another session's in-flight work. Flagged to the
orchestrator: either that session finishes and commits the wiring card, or the stray
diff must be dropped before the next gate. (The cycle-2 integrity hash therefore covers
those two foreign in-flight diffs as well — they are part of the tree this verdict
was taken over.)

## Per-attack-area re-verdict (all seven areas)

1. P0 invariant — HOLD (unchanged from cycle 1; no new write path added).
2. Migration — HOLD (unchanged).
3. Menu filter + dedup — HOLD, now proven at ENDPOINT level (P2-1 closed).
4. Auth-gating — HOLD (401-anonymous-with-param preserved; malformed-authenticated
   now 422, tested).
5. Absent-means-unchanged PUT — HOLD (unchanged).
6. Test quality — the cycle-1 false-green window is closed; 97 tests, EXIT=0.
7. Recorded deviations — all three honest; the ingest deferral is design-sanctioned
   (§6 step 5 wording), now correctly characterized.

## Bottom line

Every finding that blocked cycle 1 is either fixed with a red-capable test (P2-1,
P2-2) or corrected as a misreading of the pinned design (P1-1, with the residual
dead-code fact recorded as P2). The build's guarantees — P0 no-retraction, migration,
auth-gating, PUT semantics — are test-backed and re-verified this session.

# JUDGED: d38fcbda8108a05281458a76d1a0e0f19dc049f5f9f452a9409a32f069005e4d
# VERDICT: SHIP
