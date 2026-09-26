# T6 — Fixround: T5 DA verdict fixes (MC 1355.7)

Parent: MC 1355 · Repo: `/srv/workspace/svarkor-matapp-audit-2026` (main).
Fixes the four findings in `audit/T5-DA-verdict.md` (VERDICT: FIX). Finished the
interrupted predecessor's uncommitted work; root-caused the 3 failing registration
tests instead of restarting.

## Per-finding fix summary

1. **P1 — silent total failure (T5 attack 2).** `src/scheduler/periodic.py`: a grocer
   whose feed degrades to 0 entries now logs a WARNING naming the grocer and week.
   `app/main.py`: `/health` carries `offers_week`, `offers_current_week` and
   `offers_by_grocer` (one grouped query) — a dead feed is visible, not green-silent.
   TESTED: `test_periodic_warns_when_grocer_yields_zero_entries`,
   `test_health_offers_signal_empty_then_populated`.
2. **P1 — extrapris ratio rule dead (T5 attack 3).** `src/fetcher/adapters/lidl.py`
   parses `price.discount.deletedPrice` into `regular_price`;
   `src/normalizer/chain_mapper.py` carries it through as `regular_price_cents` and
   derives `savings_cents` only when regular > sale. ICA emits **no** regular price:
   the page's only reference field `comparisonPrice` is the SALE price per kg/l
   (predecessor verified live: 119 kr/st @ 420 g = 283.33 kr/kg) — using it would
   invent a discount on every item, so ICA rows stay NULL per the fixround rule.
   TESTED: `test_regular_price_populated_from_lidl_fixture`,
   `test_ica_entry_without_regular_price_stays_null`,
   `test_andel_extrapris_nonzero_after_ingest`.
3. **P2 — double external_id prefix (T5 attack 5).** Adapters now emit bare ids
   (`5004009053`, `66000056`); `chain_mapper` alone owns the CHAIN_MAP prefix, so the
   stored id carries exactly one (`ica-…` / `lidl-…`). TESTED:
   `test_external_id_carries_exactly_one_prefix`.
4. **P1 — open registration (T5 attack 4, owner-ratified).** `app/auth_service.py`
   `register()`: same users table, argon2id via `app/security.py`, same SessionStore —
   no second mechanism. `app/routers/auth.py` `POST /api/auth/register`: 200 + the
   SAME session cookie as login (auto-login), 409 duplicate username, 422 weak
   password / blank or >64-char username. TESTED: `tests/test_registration.py` (6 tests).

## Root cause of the 3 failing tests (predecessor's leftovers)

* `tests/test_fixround_offers.py:128` — `recipes` is a **function** (`app/optimizer/
  recipes.py:93`), the test iterated it directly → `TypeError: 'function' object is
  not iterable`. Fixed: `recipes()`.
* `tests/test_registration.py` (2 tests) — the session cookie is `Secure`
  (`app/security.py SESSION_SECURE=True`, correct for the HTTPS deploy), and
  TestClient's httpx jar drops Secure cookies over its `http://testserver` base —
  the exact harness artifact T5 attack 4 already documented for login. The app was
  correct; the tests relied on the jar. Fixed: replay the `Set-Cookie` value as an
  explicit cookie on `/api/auth/me`, with a comment citing the T5 artifact.

## Test evidence (fresh suite, caches cleaned)

```
$ find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache
$ /srv/workspace/Hotell/.venv/bin/python -m pytest tests/ -q
53 passed, 3 warnings in 6.62s
EXIT=0
```

Junk dir `tmp_does_not_exist/` (contained only a stray test-artifact sqlite db,
untracked) deleted.

## TestClient probe evidence (`.tmp/probe_fixround.py`, PROBE_EXIT=0)

```
register: 200 {'ok': True, 'username': 'probe1'}
set-cookie: matapp_session=…; HttpOnly; Path=/; SameSite=lax; Secure
me(auto-login): 200 {'user_id': 1, 'username': 'probe1'}
duplicate: 409 {'detail': 'username already taken'}
weak: 422 {'detail': 'password must be at least 8 characters'}
health empty: {'offers_week': '2026-W39', 'offers_current_week': 0, 'offers_by_grocer': {}}
normalized external_id: lidl-66000056 regular: 5990 savings: 3000
andel_extrapris after Lidl ingest: 0.3333333333333333
stored external_ids: ['lidl-66000056']
hash prefix: ['argon2id', 'v=19']
```

Populated `/health` signal is additionally covered by
`test_health_offers_signal_empty_then_populated` (2 rows → `offers_current_week == 2`,
`offers_by_grocer == {"ica": 1, "lidl": 1}`); the 0-entry warning by
`test_periodic_warns_when_grocer_yields_zero_entries`.

## Commits (main, not pushed)

* `77ff2ad` matapp: DA fixround — health offers signal + regular prices + single prefix (MC 1355.7)
* `966ddaa` matapp: open registration endpoint (MC 1355.7, owner-ratified)

## Open items (not in this fixround's scope)

* T5 P2 week semantics (non-current weeks silently degrade to recipe-only) — still open.
* T5 P3 boot ingest does real network I/O in the lifespan — still open (periodic-refresh card).

# VERDICT: PASS
