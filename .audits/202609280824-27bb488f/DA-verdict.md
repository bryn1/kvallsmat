# DA-verdict — MC 1355.20 cycle 2: adversarial review of ARCH-verdict.md vs the artifacts

Reviewer: devils-advocate pass. NOTE (recorded honestly): this session runs at subagent
depth 1 (`maxDepth 1`) — the harness rejected every `subagent` spawn ("subagent depth 2
exceeds maxDepth 1"), so this review could NOT be an independent child. It was executed
inline as a fresh-eyes re-check: every load-bearing claim in ARCH-verdict.md was
re-verified against the files with NEW greps, not taken from the verdict text.

Re-checks performed this pass (all against HEAD 59295c0e):

- "3 suggestions": `app/routers/menu.py:47-48` `SUGGESTION_COUNT = 3`, "exactly three
  suggestions (the Phase 6 DEFAULT_SEEDS = 3 seeds)" — supports doc line 28. CONFIRMED.
- "no repeats / pool exhaustion truncates": `src/planner/menu.py:136` "repeating a dish
  within the week", `:157,163-165` `used_dish_ids` guard — CONFIRMED.
- Register auto-login: `app/routers/auth.py:11-12,76` — CONFIRMED.
- kid_friendly is a boost on ties, not a filter: `menu.py:145-154` (`_rank` adds kid
  weight on ties only; `_allowed_recipe` untouched by kid flag) — CONFIRMED.
- Endpoint table: re-grepped every URL in the post-fix doc (10 URLs, lines 90-95) against
  `app/config.py:47,51,54,56`, `src/locator/{willys,ica,coop,lidl,geocode}.py`,
  `src/fetcher/adapters/{ica,lidl}.py:3-4,18` — all match; the cycle-1 Lidl colon typo is
  gone. CONFIRMED.
- Limitations section now exists (doc lines 106-116) and matches `LEDGER.md:60` and
  `app/routers/profile.py:51-52`. CONFIRMED.
- Secrets: grep over app/ + src/ for hardcoded credential assignments — zero hits. CONFIRMED.
- Tests: `pytest tests/ -q` re-run after the doc edits → 116 passed. CONFIRMED.
- Adversarial probe for over-claim: the verdict labels check 2 PASS "after F5 fix" while
  conceding `src/config.py`/`src/database.py` stay unnamed. Agreed this is acceptable
  (motor-internal plumbing, not load-bearing) — the concession is explicit, not hidden.

No contradiction found between ARCH-verdict.md, the fixed `docs/ARCHITECTURE.md`, and the
tree. The cycle-1 FAIL findings were all addressed in cycle 2; nothing was papered over.

# JUDGED: 086fafeca6a569c82d769b76411dac64416f9662256dbb3366757dd6dc854431
# VERDICT: PASS
