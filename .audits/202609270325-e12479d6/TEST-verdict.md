# TEST-verdict — MC 1355.19 T11 test gate (register UI + num_children + kid_friendly)

Tester profile, independent verification of the T11 build (9a5b299 + a742cb3) at HEAD
59295c0e, repo `/srv/workspace/matapp` (= `/home/svarkor/Matapp`, same tree, inode-verified).
All checks executed this session with `/srv/workspace/hotell/.venv/bin/python`.

## Check 1 — fresh suite (VERIFIED)

Cleaned every `__pycache__` and `.pytest_cache`, then:

```
$ find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache
$ /srv/workspace/hotell/.venv/bin/python -m pytest tests/ -q
116 passed, 3 warnings in 12.59s
EXIT=0
```

Re-run after the mutation round (restored tree): `116 passed, 3 warnings in 13.32s`, EXIT=0,
`git status --short` empty (tree clean, nothing committed).

## Check 2 — test quality: real implementation, not mocks (VERIFIED)

The four T11 test files and what each actually exercises:

* `tests/test_profile_children.py` — drives the REAL `PUT/GET /api/profile` endpoints through
  the temp-DB TestClient (no mocks): absent-means-unchanged, explicit-null clear, 422 bounds,
  GET echo for `num_children` / `prefer_kid_friendly`.
* `tests/test_menu_kid_friendly.py` — `test_menu_day_carries_kid_friendly_flag` seeds REAL
  offer rows via `upsert_week` and calls the REAL `/api/menu` endpoint;
  `test_prefer_kid_friendly_boosts_kid_dishes_on_ties` calls the REAL `plan_menu`
  (`src/planner/menu.py`) with a genuine 1-hit-vs-1-hit tie; the all-zero-roster test monkeypatches
  only the roster source (a legitimate fixture, and it asserts the flag-off/flag-on plans are
  identical — a structural guard, not a mock of the behaviour under test).
* `tests/test_recipe_kid_friendly.py` — REAL `seed_starter` and REAL `scrape_recipes` against a
  temp sqlite + `file://` fixture; asserts the seven kid titles are 1, everything else 0,
  idempotent reseed, absent-flag normalises to 0.
* `tests/test_migration_t11.py` — builds a REAL legacy-schema sqlite (raw SQL, pre-T11 columns)
  and runs the REAL `app.db.ensure_columns` twice (idempotency).

No test asserts on a mock of the behaviour under test. Could any stay green while the feature
is broken? The two mutation runs below answer that empirically: no.

## Check 3 — mutation red-proofs (VERIFIED, both RED, both restored)

**Mutation A — remove the kid-friendly boost tiebreak** (`src/planner/menu.py`:
`return (-_offer_hit_count(r, offers), -kid, rng.random())` → `(..., rng.random())`):

```
FAILED tests/test_menu_kid_friendly.py::test_prefer_kid_friendly_boosts_kid_dishes_on_ties
1 failed, 3 passed, 1 warning in 1.25s
```

The tie test goes RED exactly as designed — it proves the boost, not just that the field exists.

**Mutation B — break the register UI's backend wiring** (`app/routers/auth.py` register:
removed `_set_session_cookie(response, token)`, i.e. no auto-login after registration —
the behaviour the Konto-page register toggle depends on):

```
FAILED tests/test_registration.py::test_register_happy_path_sets_session - Ke...
FAILED tests/test_profile_children.py::test_num_children_absent_means_unchanged
FAILED tests/test_profile_children.py::test_num_children_explicit_null_clears
FAILED tests/test_profile_children.py::test_num_children_negative_422 - KeyEr...
FAILED tests/test_profile_children.py::test_prefer_kid_friendly_absent_means_unchanged_and_roundtrip
FAILED tests/test_profile_children.py::test_prefer_kid_friendly_out_of_range_422
FAILED tests/test_profile_children.py::test_profile_get_echoes_new_fields - Ke...
7 failed, 5 passed, 2 warnings in 2.80s
```

(The KeyErrors are `_login` failing on the missing Set-Cookie — the broken wiring propagates.)
Both mutations restored with `git checkout`-equivalent file restore; `git status --short`
empty and `git diff --stat` empty afterwards; full suite green again (Check 1 re-run).

## Check 4 — P0 invariant: store-scoped write cannot overwrite a NULL chain-level row (VERIFIED)

```
$ pytest tests/test_store_scoping.py::test_p0_store_scoped_write_never_overwrites_chain_level_row -q
3 passed (with the two absent-means-unchanged tests), 1 warning in 1.46s
```

Inspected the test body: it performs a chain-level pull (bare id, `store_id` NULL), then a
store-scoped pull of the SAME catalog (`2103:hs1`, `store_id="2103"`), asserts TWO rows exist,
the NULL row survived with its original price, then reverses the order and asserts the
chain-level row updates in place while the store row is untouched. This reaches the real
`upsert_week` store-clause logic — it is a genuine regression test, not a tautology.

## Check 5 — absent-means-unchanged (VERIFIED)

`tests/test_profile_children.py::test_num_children_absent_means_unchanged` and
`::test_prefer_kid_friendly_absent_means_unchanged_and_roundtrip` both pass (see Check 4 run).
They PUT the field, then PUT WITHOUT it, then GET and assert the persisted value survived
(`num_children == 2`, `prefer_kid_friendly == 1`), plus explicit-0 and explicit-null semantics.
This follows the postal_code `model_fields_set` precedent and would catch a PUT that clears
unsupplied fields.

## Notes

* Scratch (mutation backups) kept in `/tmp`, nothing untracked added to the repo.
* Nothing committed, nothing pushed (per task).

# JUDGED: 44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a
# VERDICT: PASS
