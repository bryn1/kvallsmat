# matapp fixrunda 2 — evidence (MC 1233.1)

Card: 1233.1 (parent 1233), [type:code], branch `matapp-fixround` in
`/srv/workspace/hosting`. Fixes F2 + F3 from audit MC 1188.9
(`/srv/workspace/svarkor-matapp/audit/security.md`), plus the F1 commit that
fixround 1 (MC 1227.1) left uncommitted. BUG-1/2 are POC-scoped and explicitly
NOT this round (brief).

All commands run 2026-09-14 (UTC) on vm105 by henrik, fresh venv
`/home/henrik/matapp-fixround2-venv` (pins from apps/matapp/requirements.txt:
fastapi 0.141.1, uvicorn 0.52.4, sqlalchemy 2.0.52, pydantic 2.13.4,
argon2-cffi 25.1.0, argon2-cffi-bindings 21.2.0, httpx 0.28.1 + pytest).

## (a) git log on matapp-fixround — F1 commit + F2/F3 commits

VERIFIED — pasted from `git log --oneline -4` on branch matapp-fixround:

```
63818f9 matapp: make _mkuser idempotent (temp-DB reuse across tests)
57c5bd2 matapp: F2 login rate-limit/lockout + F3 timing-equalizer (audit 1188.9 F2/F3)
8e4aa9b matapp: F1 fix — MATAPP_DB_URL env-var (audit 1188.9 F1)
4d220cd matapp: publish framtidsversion — auth (argon2id+session) + profil + 3-förslags-meny (MC 1164 pkg 1164.8) — httpx-pin restored (1164.9, DA FIX-1)
```

- F1 commit = `8e4aa9b` (server.py + DEPLOY.md, exactly the verified fixround-1
  changes; committed FIRST, before any new work, per the brief).
- F2/F3 commit = `57c5bd2` (auth_service.py, security.py, routers/auth.py, tests/).
- `63818f9` = test-only follow-up (idempotent user insert; see note below).

## (b) Fresh pytest run — count + exit code

VERIFIED — caches cleaned (`find . -name __pycache__ -exec rm -rf`, `.pytest_cache`
removed) immediately before this run, on the committed tree:

```
$ /home/henrik/matapp-fixround2-venv/bin/python3 -m pytest tests/
======================== 9 passed, 2 warnings in 3.05s =========================
VERIFY_EXIT=0
```

9 tests, all green, exit code 0. (The 2 warnings are starlette/httpx deprecation
notices from TestClient, pre-existing upstream, not from this round's code.)

## (c) Lockout triggering + timing measurement

### F2 lockout (VERIFIED — test output + standalone probe)

`test_lockout_returns_429_via_router` (from the fresh run above): 5 bad logins
against username `ghost` all return 401; the 6th returns **429** with detail
`"too many failed logins; try again later"`. Supporting tests in the same run:
lockout refuses even the CORRECT password (`test_lockout_refuses_even_correct_password`),
a successful login resets the counter (`test_successful_login_resets_counter`),
lockout expires after the window (`test_lockout_expires_after_window`), failures
outside the 15-min window do not count (`test_failures_outside_window_do_not_count`),
and lockout is per-username (`test_lockout_is_per_username`).

Implementation: `LoginRateLimiter` in `app/auth_service.py` — in-memory,
per-username, `threading.Lock`-guarded (same scope/idiom as SessionStore);
5 failures within 15 min → 15-min lockout; `login()` raises `LoginLockedOut`
which `app/routers/auth.py` maps to HTTP 429 without touching the DB.

### F3 timing equalizer (VERIFIED — standalone measurement, n=10 medians)

```
$ /home/henrik/matapp-fixround2-venv/bin/python3 <timing probe, temp sqlite DB>
existing median: 49.6 ms (n=10)
non-existing median: 43.2 ms (n=10)
ratio: 1.15x  (<2x target: PASS)
TIMING_EXIT=0
```

Before this round (audit MC 1188.9 E2): existing 37.4 ms vs ghost 2.2 ms ≈ 17x.
After: 1.15x — well under the 2x DoD target. Implementation: for a non-existent
username `authenticate()` runs a real argon2 verify against
`app/security.DUMMY_HASH` (module-level, generated at import from a fixed dummy
string); `test_dummy_hash_is_real_argon2id` proves the dummy hash is a genuine
`$argon2id$` PHC string the verifier accepts/rejects correctly.

## Notes / caveats

- The pytest run above is the FRESH-cache run on the committed tree. An earlier
  run exposed a test-ordering bug (temp DB reused across tests → UNIQUE
  violation on re-insert); fixed in `63818f9` by making `_mkuser` idempotent,
  then re-run fresh — green.
- The suite runs against a temp sqlite DB (conftest binds `app.db._engine` to a
  `TemporaryDirectory` before `app.main` is imported); the repo's `.data/` DB is
  never touched. No secrets in any file written by this round.
- Language: Python — the repo's established stack (FastAPI/SQLAlchemy); Rust
  would be a rewrite, not a fix (coding-discipline: reuse wins).
- Vision: n/a — no UI rendered by this round (server-side auth logic + tests).
- Push to origin: NOT done — crew never pushes `repo/` (workspace-convention);
  integration/push is Svarkor's step. Branch `matapp-fixround` holds the commits.

VERIFY_EXIT=0
